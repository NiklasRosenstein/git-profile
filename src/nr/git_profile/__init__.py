# The MIT License (MIT)
#
# Copyright (c) 2018 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
A command-line tool to switch between several Git profiles. Switching to a
profile will load configuration options from a Git configuration file and
write them to the current repository.
"""

from __future__ import print_function
from ._vendor.gitconfigparser import GitConfigParser
from nr.types.record import Record
from six.moves import configparser

try: from shlex import quote
except ImportError: from pipes import quote

import argparse
import os
import subprocess
import sys
import json
import base64

__author__ = 'Niklas Rosenstein <rosensteinniklas@gmail.com>'
__version__ = '1.0.0'


def git(*args):
  command = 'git ' + ' '.join(map(quote, args))
  return subprocess.check_output(command, shell=True).decode().strip()


def find_git_dir():
  directory = os.getcwd()
  prev = None
  while not os.path.isdir(os.path.join(directory, '.git')):
    directory = os.path.dirname(directory)
    if directory == prev:
      return None
    prev = directory
  return os.path.join(directory, '.git')


class Changeset(object):

  class Change(Record):
    __slots__ = 'type,section,key,value'.split(',')

    def to_json(self):
      return {k: getattr(self, k) for k in self.__slots__}

  NEW = 'NEW'  # No value
  SET = 'SET'  # Contains previous value
  DEL = 'DEL'  # Contains previous value

  @classmethod
  def from_b64(cls, data):
    return cls.from_json(json.loads(base64.b64decode(data).decode('utf8')))

  @classmethod
  def from_json(cls, data):
    return cls([cls.Change(**x) for x in data])

  def __init__(self, changes=None):
    self.changes = changes or []

  def to_b64(self):
    return base64.b64encode(json.dumps(self.to_json()).encode('utf8'))

  def to_json(self):
    return [x.to_json() for x in self.changes]

  def revert(self, config):
    for change in reversed(self.changes):
      if change.type == self.NEW:
        if change.key is None:
          config.remove_section(change.section)
        else:
          config.remove_option(change.section, change.key)
      elif change.type == self.SET or change.type == self.DEL:
        config.set(change.section, change.key, change.value)
      else:
        raise RuntimeError('unexpected Change.type: {!r}'.format(change))

  def set(self, config, section, key, value):
    if not config.has_section(section):
      config.add_section(section)
      self.changes.append(self.Change(self.NEW, section, None, None))
    if not config.has_option(section, key):
      self.changes.append(self.Change(self.NEW, section, key, None))
    else:
      self.changes.append(self.Change(self.SET, section, key, config.get(section, key)))
    config.set(section, key, value)


class MergeReadConfig(object):

  def __init__(self, configs):
    self.configs = configs

  def __getattr__(self, name):
    return getattr(self.configs[0], name)

  def get(self, section, option, **kwargs):
    fallback = kwargs.pop('fallback', NotImplemented)
    for cfg in self.configs:
      try:
        return cfg.get(section, option, **kwargs)
      except configparser.NoOptionError:
        pass
    if fallback is not NotImplemented:
      return fallback
    raise configparser.NoOptionError((section, option))


def get_argument_parser(prog=None):
  parser = argparse.ArgumentParser(prog=prog)
  parser.add_argument('profile', nargs='?', help='The name of the profile to use.')
  return parser


def main(argv=None, prog=None):
  parser = get_argument_parser(prog)
  args = parser.parse_args(argv)

  global_config = GitConfigParser(os.path.expanduser('~/.gitconfig'))
  profiles = set(x.split('.')[0] for x in global_config.sections() if '.' in x)
  profiles.add('default')

  git_dir = find_git_dir()
  if not git_dir:
    print('fatal: GIT_DIR not found', file=sys.stderr)
    return 1

  local_config = GitConfigParser(os.path.join(git_dir, 'config'), read_only=False)
  current_profile = local_config.get_value('profile', 'current', 'default')

  if not args.profile:
    for x in sorted(profiles, key=str.lower):
      print('*' if x == current_profile else ' ', x)
    return 0
  else:
    if args.profile not in profiles:
      print('fatal: no such profile: "{}"'.format(args.profile), file=sys.stderr)
      return 1

    config = MergeReadConfig([local_config, global_config])
    changeset = local_config.get_value('profile', 'changeset', '')
    if changeset:
      changes = Changeset.from_b64(changeset)
      changes.revert(config)

    if args.profile != 'default':
      changes = Changeset()
      for section in global_config.sections():
        if section.startswith(args.profile + '.'):
          key = section.split('.', 1)[1]
          for opt in global_config.options(section):
            changes.set(config, key, opt, global_config.get(section, opt))
      changes.set(local_config, 'profile', 'current', args.profile)
      changes.set(local_config, 'profile', 'changeset', changes.to_b64())
    local_config.write()

    print('Switched to profile "{}".'.format(args.profile))
    return 0


if __name__ == '__main__':
  sys.exit(main())
