# The MIT License (MIT)
#
# Copyright (c) 2019 Niklas Rosenstein
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

import argparse
import base64
import configparser
import enum
import json
import os
import subprocess
import sys
import typing as t
from pathlib import Path
from shlex import quote

import nr.fs
from databind.core import datamodel, field
from databind.json import from_json, to_json

from ._vendor.gitconfigparser import GitConfigParser

__author__ = 'Niklas Rosenstein <rosensteinniklas@gmail.com>'
__version__ = '1.1.0'


def git(*args):
  command = 'git ' + ' '.join(map(quote, args))
  return subprocess.check_output(command, shell=True).decode().strip()


def find_git_dir():
  directory = os.getcwd()
  prev = None
  while True:
    path = os.path.join(directory, '.git')
    if os.path.exists(path):
      if os.path.isfile(path):
        with open(path) as fp:
          for line in fp:
            if line.startswith('gitdir:'):
              return line.replace('gitdir:', '').strip()
        raise RuntimeError('unable to find gitdir in "{}"'.format(path))
      return path
    directory = os.path.dirname(directory)
    if directory == prev:
      return None
    prev = directory
  return os.path.join(directory, '.git')


@datamodel
class Change:
  type: 'ChangeType'
  section: str
  key: t.Optional[str]
  value: t.Optional[str]


class ChangeType(enum.Enum):
  NEW = enum.auto()
  SET = enum.auto()
  DEL = enum.auto()


@datamodel
class Changeset:
  changes: t.List[Change] = field(default_factory=list)

  @classmethod
  def from_b64(cls, data: bytes) -> 'Changeset':
    return from_json(Changeset, json.loads(base64.b64decode(data).decode('utf8')))

  def to_b64(self) -> bytes:
    return base64.b64encode(json.dumps(to_json(self)).encode('utf8'))

  def revert(self, config: configparser.RawConfigParser) -> None:
    for change in reversed(self.changes):
      if change.type == ChangeType.NEW:
        if change.key is None:
          config.remove_section(change.section)
        else:
          config.remove_option(change.section, change.key)
      elif change.type == ChangeType.SET or change.type == ChangeType.DEL:
        assert change.section and change.key and change.value, change
        config.set(change.section, change.key, change.value)
      else:
        raise RuntimeError('unexpected Change.type: {!r}'.format(change))

  def set(self, config: configparser.RawConfigParser, section: str, key: str, value: str) -> None:
    if not config.has_section(section):
      config.add_section(section)
      self.changes.append(Change(ChangeType.NEW, section, None, None))
    if not config.has_option(section, key):
      self.changes.append(Change(ChangeType.NEW, section, key, None))
    else:
      self.changes.append(Change(ChangeType.SET, section, key, config.get(section, key)))
    config.set(section, key, value)


class MergeReadConfig:

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


def main(argv: t.Optional[t.List[str]] = None, prog: t.Optional[str] = None) -> int:
  parser = argparse.ArgumentParser(prog=prog)
  parser.add_argument('profile', nargs='?', help='The name of the profile to use.')
  parser.add_argument('-d', '--diff', action='store_true', help='Print the config diff.')
  args = parser.parse_args(argv)

  global_config = GitConfigParser(os.path.expanduser('~/.gitconfig'))
  profiles = set(x.split('.')[0] for x in global_config.sections() if '.' in x and ' ' not in x)
  profiles.add('default')

  git_dir = find_git_dir()
  if not git_dir:
    print('fatal: GIT_DIR not found', file=sys.stderr)
    return 1

  local_config_fn = os.path.join(git_dir, 'config')
  assert os.path.isfile(local_config_fn), local_config_fn
  local_config = GitConfigParser(local_config_fn, read_only=False)
  current_profile = local_config.get_value('profile', 'current', 'default')
  current_config_text = Path(local_config_fn).read_text()

  if not args.profile:
    for x in sorted(profiles, key=lambda x: x.lower()):
      print('*' if x == current_profile else ' ', x)
    return 0
  else:
    if args.profile not in profiles:
      print('fatal: no such profile: "{}"'.format(args.profile), file=sys.stderr)
      return 1

    config = MergeReadConfig([local_config, global_config])
    changeset: str = local_config.get_value('profile', 'changeset', '')
    if changeset:
      changes = Changeset.from_b64(changeset.encode('ascii'))
      changes.revert(config)  # type: ignore

    if args.profile != 'default':
      changes = Changeset()
      for section in global_config.sections():
        if section.startswith(args.profile + '.'):
          key = section.split('.', 1)[1]
          for opt in global_config.options(section):
            changes.set(config, key, opt, global_config.get(section, opt))  # type: ignore
      changes.set(local_config, 'profile', 'current', args.profile)
      changes.set(local_config, 'profile', 'changeset', changes.to_b64().decode('ascii'))

    local_config.write()
    del local_config

    if args.diff and Path(local_config_fn).read_text() != current_config_text:
      with nr.fs.tempfile('_old', text=True) as a:
        a.write(current_config_text)
        a.close()
        print()
        subprocess.call(['git', 'diff', '--no-index', a.name, local_config_fn])
        print()

    print('Switched to profile "{}".'.format(args.profile))
    return 0


if __name__ == '__main__':
  sys.exit(main())
