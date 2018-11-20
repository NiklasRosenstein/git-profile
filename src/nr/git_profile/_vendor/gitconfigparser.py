#!/usr/bin/env python
# based on GitPython.config
try:
    import builtins  # python2.X
except ImportError:
    import __builtin__ as builtins  # python3+
import re
try:
    import ConfigParser as cp
except ImportError:
    # PY3
    import configparser as cp
import inspect
import abc
import os
import sys
from py3 import PY3

# from git.odict import OrderedDict
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

# from git.compat import force_text,string_types
from gitdb.utils.encoding import force_text, string_types

__all__ = ('GitConfigParser', 'SectionConstraint')

# from git.compat import defenc
defenc = sys.getdefaultencoding()
# from git.compat import with_metaclass
# from future.utils import with_metaclass # python3.2 not compatible


def with_metaclass(meta, *bases):
    class metaclass(meta):
        __call__ = type.__call__
        __init__ = type.__init__

        def __new__(cls, name, nbases, d):
            if nbases is None:
                return type.__new__(cls, name, (), d)
            if not PY3 and '___metaclass__' not in d:
                d['__metaclass__'] = meta
            # end
            return meta(name, bases, d)
        # end
    # end metaclass
    return metaclass(meta.__name__ + 'Helper', None, {})
    # end handle py2


# from git.compat import FileType
if PY3:
    import io
    FileType = io.IOBase

    def byte_ord(b):
        return b

    def bchr(n):
        return bytes([n])

    def mviter(d):
        return d.values()
    unicode = str
else:
    FileType = builtins.file

# log = logging.getLogger('git.config')
# log.addHandler(logging.NullHandler())

# from git.util import LockFile


class LockFile(object):
    __slots__ = ("_file_path", "_owns_lock")

    def __init__(self, file_path):
        self._file_path = file_path
        self._owns_lock = False

    def __del__(self):
        self._release_lock()

    def _lock_file_path(self):
        """:return: Path to lockfile"""
        return "%s.lock" % (self._file_path)

    def _has_lock(self):
        return self._owns_lock

    def _obtain_lock_or_raise(self):
        if self._has_lock():
            return
        lock_file = self._lock_file_path()
        if os.path.isfile(lock_file):
            msg = """Lock for file %r did already exist,
delete %r in case the lock is illegal""" % (self._file_path, lock_file)
            raise IOError(msg)

        try:
            fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0)
            os.close(fd)
        except OSError as e:
            raise IOError(str(e))

        self._owns_lock = True

    def _obtain_lock(self):
        return self._obtain_lock_or_raise()

    def _release_lock(self):
        """Release our lock if we have one"""
        if not self._has_lock():
            return

        lfp = self._lock_file_path()
        try:
            if os.name == 'nt':
                os.chmod(lfp, 0o777)
            # END handle win32
            os.remove(lfp)
        except OSError:
            pass
        self._owns_lock = False


class MetaParserBuilder(abc.ABCMeta):

    def __new__(metacls, name, bases, clsdict):
        kmm = '_mutating_methods_'
        if kmm in clsdict:
            mutating_methods = clsdict[kmm]
            for base in bases:
                methods = (
                    t for t in inspect.getmembers(
                        base, inspect.isroutine) if not t[0].startswith("_"))
                for method_name, method in methods:
                    if method_name in clsdict:
                        continue
                    method_with_values = needs_values(method)
                    if method_name in mutating_methods:
                        method_with_values = set_dirty_and_flush_changes(
                            method_with_values)
                    # END mutating methods handling

                    clsdict[method_name] = method_with_values
                # END for each name/method pair
            # END for each base
        # END if mutating methods configuration is set

        new_type = super(
            MetaParserBuilder,
            metacls).__new__(
            metacls,
            name,
            bases,
            clsdict)
        return new_type


def needs_values(func):

    def assure_data_present(self, *args, **kwargs):
        self.read()
        return func(self, *args, **kwargs)
    # END wrapper method
    assure_data_present.__name__ = func.__name__
    return assure_data_present


def set_dirty_and_flush_changes(non_const_func):

    def flush_changes(self, *args, **kwargs):
        rval = non_const_func(self, *args, **kwargs)
        self._dirty = True
        self.write()
        return rval
    # END wrapper method
    flush_changes.__name__ = non_const_func.__name__
    return flush_changes


class SectionConstraint(object):
    __slots__ = ("_config", "_section_name")
    _valid_attrs_ = (
        "get_value",
        "set_value",
        "get",
        "set",
        "getint",
        "getfloat",
        "getboolean",
        "has_option",
        "remove_section",
        "remove_option",
        "options"
    )

    def __init__(self, config, section):
        self._config = config
        self._section_name = section

    def __del__(self):
        self._config.release()

    def __getattr__(self, attr):
        if attr in self._valid_attrs_:
            return lambda *args, **kwargs: self._call_config(
                attr, *args, **kwargs)
        return super(SectionConstraint, self).__getattribute__(attr)

    def _call_config(self, method, *args, **kwargs):
        return getattr(self._config, method)(
            self._section_name, *args, **kwargs)

    @property
    def config(self):
        return self._config

    def release(self):
        return self._config.release()


class GitConfigParser(with_metaclass(
        MetaParserBuilder, cp.RawConfigParser, object)):

    t_lock = LockFile
    re_comment = re.compile('^\s*[#;]')

    # } END configuration

    optvalueonly_source = r'\s*(?P<option>[^:=\s][^:=]*)'

    OPTVALUEONLY = re.compile(optvalueonly_source)

    OPTCRE = re.compile(
        optvalueonly_source +
        r'\s*(?P<vi>[:=])\s*' +
        r'(?P<value>.*)$')

    del optvalueonly_source

    _mutating_methods_ = (
        "add_section",
        "remove_section",
        "remove_option",
        "set")

    def __init__(self, file_or_files, read_only=True, merge_includes=True):
        cp.RawConfigParser.__init__(self, dict_type=OrderedDict)

        if not hasattr(self, '_proxies'):
            self._proxies = self._dict()

        self._file_or_files = file_or_files
        self._read_only = read_only
        self._dirty = False
        self._is_initialized = False
        self._merge_includes = merge_includes
        self._lock = None

        err = """"Write-ConfigParsers can operate on a single file only,
        multiple files have been passed"""
        if not read_only:
            if isinstance(file_or_files, (tuple, list)):
                raise ValueError(err)
            # END single file check

            if not isinstance(file_or_files, string_types):
                file_or_files = file_or_files.name
            # END get filename from handle/stream
            # initialize lock base - we want to write
            self._lock = self.t_lock(file_or_files)

            self._lock._obtain_lock()
        # END read-only check

    def __del__(self):
        """Write pending changes if required and release locks"""
        # NOTE: only consistent in PY2
        self.release()

    def release(self):
        if self.read_only or (self._lock and not self._lock._has_lock()):
            return

        try:
            try:
                self.write()
            except IOError:
                print("Exception during destruction of GitConfigParser")
            except ReferenceError:
                pass
        finally:
            self._lock._release_lock()

    def optionxform(self, optionstr):
        """
Do not transform options in any way when writing
"""
        return optionstr

    def _read(self, fp, fpname):
        cursect = None
        optname = None
        lineno = 0
        is_multi_line = False
        e = None

        def string_decode(v):
            if v[-1] == '\\':
                v = v[:-1]
            # end cut trailing escapes to prevent decode error

            if PY3:
                return v.encode(defenc).decode('unicode_escape')
            return v.decode('string_escape')
            # end
        # end

        while True:
            # we assume to read binary !
            line = fp.readline().decode(defenc)
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if line.strip() == '' or self.re_comment.match(line):
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue

            # is it a section header?
            mo = self.SECTCRE.match(line.strip())
            if not is_multi_line and mo:
                sectname = mo.group('header').strip()
                if sectname in self._sections:
                    cursect = self._sections[sectname]
                elif sectname == cp.DEFAULTSECT:
                    cursect = self._defaults
                else:
                    cursect = self._dict((('__name__', sectname),))
                    self._sections[sectname] = cursect
                    self._proxies[sectname] = None
                # So sections can't start with a continuation line
                optname = None
            # no section header in the file?
            elif cursect is None:
                raise cp.MissingSectionHeaderError(fpname, lineno, line)
            # an option line?
            elif not is_multi_line:
                mo = self.OPTCRE.match(line)
                if mo:
                    # We might just have handled the last line, which could
                    # contain a quotation we want to remove
                    optname, vi, optval = mo.group('option', 'vi', 'value')
                    if vi in ('=', ':') and ';' in optval and not optval.strip(
                    ).startswith('"'):
                        pos = optval.find(';')
                        if pos != -1 and optval[pos - 1].isspace():
                            optval = optval[:pos]
                    optval = optval.strip()
                    if optval == '""':
                        optval = ''
                    # end handle empty string
                    optname = self.optionxform(optname.rstrip())
                    if len(optval) > 1 and optval[
                            0] == '"' and optval[-1] != '"':
                        is_multi_line = True
                        optval = string_decode(optval[1:])
                    # end handle multi-line
                    cursect[optname] = optval
                else:
                    if not self.OPTVALUEONLY.match(line):
                        if not e:
                            e = cp.ParsingError(fpname)
                        e.append(lineno, repr(line))
                    continue
            else:
                line = line.rstrip()
                if line.endswith('"'):
                    is_multi_line = False
                    line = line[:-1]
                # end handle quotations
                cursect[optname] += string_decode(line)
            # END parse section or option
        # END while reading

        # if any parsing errors occurred, raise an exception
        if e:
            raise e

    def _has_includes(self):
        return self._merge_includes and self.has_section('include')

    def read(self):
        if self._is_initialized:
            return
        self._is_initialized = True

        if not isinstance(self._file_or_files, (tuple, list)):
            files_to_read = [self._file_or_files]
        else:
            files_to_read = list(self._file_or_files)
        # end assure we have a copy of the paths to handle

        seen = set(files_to_read)
        num_read_include_files = 0
        while files_to_read:
            file_path = files_to_read.pop(0)
            fp = file_path
            close_fp = False

            # assume a path if it is not a file-object
            if not hasattr(fp, "seek"):
                try:
                    if not hasattr(builtins, "open"):
                        return
                    fp = builtins.open(file_path, 'rb')
                    close_fp = True
                except IOError:
                    continue
            # END fp handling

            try:
                if not fp:
                    return
                self._read(fp, fp.name)
            finally:
                if close_fp:
                    fp.close()
            # END read-handling
            if self._has_includes():
                for _, include_path in self.items('include'):
                    if include_path.startswith('~'):
                        include_path = os.path.expanduser(include_path)
                    if not os.path.isabs(include_path):
                        if not close_fp:
                            continue
# msg = "Need absolute paths to be sure our cycle checks will work"
                        msg = "Need absolute paths"
                        assert os.path.isabs(file_path), msg
                        include_path = os.path.join(
                            os.path.dirname(file_path), include_path)
                    # end make include path absolute
                    include_path = os.path.normpath(include_path)
                    if include_path in seen or not os.access(
                            include_path, os.R_OK):
                        continue
                    seen.add(include_path)
                    files_to_read.append(include_path)
                    num_read_include_files += 1
                # each include path in configuration file
            # end handle includes
        # END for each file object to read

        if num_read_include_files == 0:
            self._merge_includes = False
        # end

    def _write(self, fp):
        def write_section(name, section_dict):
            fp.write(("[%s]\n" % name).encode(defenc))
            for (key, value) in section_dict.items():
                if key != "__name__":
                    fp.write(
                        ("\t%s = %s\n" %
                         (key, self._value_to_string(value).replace(
                             '\n', '\n\t'))).encode(defenc))
                # END if key is not __name__
        # END section writing

        if self._defaults:
            write_section(cp.DEFAULTSECT, self._defaults)
        for name, value in self._sections.items():
            write_section(name, value)

    def items(self, section_name):
        for k, v in super(GitConfigParser, self).items(section_name):
            if k != '__name__':
                yield (k, v)

    @needs_values
    def write(self):
        self._assure_writable("write")
        if not self._dirty:
            return

        if isinstance(self._file_or_files, (list, tuple)):
            msg = """
Cannot write back if there is not exactly a single file to write to,
have %i files
""" % len(self._file_or_files)
            raise AssertionError(msg)
        # end assert multiple files

        if self._has_includes():
            # log.debug
            msg = """
Skipping write-back of confiuration file as include files were merged in
Set merge_includes=False to prevent this
"""
            print(msg)
            return
        # end

        fp = self._file_or_files
        close_fp = False

        # we have a physical file on disk, so get a lock
        if isinstance(fp, string_types + (FileType, )):
            self._lock._obtain_lock()
        # END get lock for physical files

        if not hasattr(fp, "seek"):
            fp = open(self._file_or_files, "wb")
            close_fp = True
        else:
            fp.seek(0)
            # make sure we do not overwrite into an existing file
            if hasattr(fp, 'truncate'):
                fp.truncate()
            # END
        # END handle stream or file

        # WRITE DATA
        try:
            self._write(fp)
        finally:
            if close_fp:
                fp.close()
        # END data writing

        # we do not release the lock - it will be done automatically once the
        # instance vanishes

    def _assure_writable(self, method_name):
        if self.read_only:
            msg = "Cannot execute non-constant method %s.%s" % (
                self, method_name)
            raise IOError(msg)

    def add_section(self, section):
        """
Assures added options will stay in order"""
        return super(GitConfigParser, self).add_section(section)

    @property
    def read_only(self):
        return self._read_only

    def get_value(self, section, option, default=None):
        try:
            valuestr = self.get(section, option)
        except Exception:
            if default is not None:
                return default
            raise

        types = (int, float)
        for numtype in types:
            try:
                val = numtype(valuestr)

                # truncated value ?
                if val != float(valuestr):
                    continue

                return val
            except (ValueError, TypeError):
                continue
        # END for each numeric type

        # try boolean values as git uses them
        vl = valuestr.lower()
        if vl == 'false':
            return False
        if vl == 'true':
            return True

        msg = "Invalid value type: only int, long, float and str are allowed"
        if not isinstance(valuestr, string_types):
            raise TypeError(msg, valuestr)
        return valuestr

    def _value_to_string(self, value):
        if isinstance(value, (int, float, bool)):
            return str(value)
        return force_text(value)

    @needs_values
    @set_dirty_and_flush_changes
    def set_value(self, section, option, value):
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, self._value_to_string(value))
        return self

    def rename_section(self, section, new_name):
        if not self.has_section(section):
            raise ValueError("Source section '%s' doesn't exist" % section)
        if self.has_section(new_name):
            raise ValueError(
                "Destination section '%s' already exists" %
                new_name)

        super(GitConfigParser, self).add_section(new_name)
        for k, v in self.items(section):
            self.set(new_name, k, self._value_to_string(v))
        self.remove_section(section)
        return self
