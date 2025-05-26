#
#    Copyright (C) 2001  Jeff Epler  <jepler@gmail.com>
#    Copyright (C) 2006  Csaba Henk  <csaba.henk@creo.hu>
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#


# suppress version mismatch warnings
try:
    import warnings
    warnings.filterwarnings('ignore',
                            'Python C API version mismatch',
                            RuntimeWarning,
                            )
except:
    pass

import sys
import os
from errno import *
from os import environ
import re
import argparse
from argparse import ArgumentParser, SUPPRESS
from fuseparts import __version__
from fuseparts._fuse import main, FuseGetContext, FuseInvalidate, FuseNotifyPoll
from fuseparts._fuse import FuseError, FuseAPIVersion


##########
###
###  API specification API.
###
##########

# The actual API version of this module
FUSE_PYTHON_API_VERSION = (0, 2)

def __getenv__(var, pattern = '.', trans = lambda x: x):
    """
    Fetch enviroment variable and optionally transform it. Return `None` if
    variable is unset. Bail out if value of variable doesn't match (optional)
    regex pattern.
    """

    if var not in environ:
        return None
    val = environ[var]
    rpat = pattern
    if not isinstance(rpat, type(re.compile(''))):
        rpat = re.compile(rpat)
    if not rpat.search(val):
        raise RuntimeError("env var %s doesn't match required pattern %s" % \
                           (var, repr(pattern)))
    return trans(val)

def get_fuse_python_api():
    if fuse_python_api:
        return fuse_python_api
    elif compat_0_1:
        # deprecated way of API specification
        return (0,1)

def get_compat_0_1():
    return get_fuse_python_api() == (0, 1)

# API version to be used
fuse_python_api = __getenv__('FUSE_PYTHON_API', r'^[\d.]+$',
                              lambda x: tuple([int(i) for i in x.split('.')]))

# deprecated way of API specification
compat_0_1 = __getenv__('FUSE_PYTHON_COMPAT', '^(0.1|ALL)$', lambda x: True)

fuse_python_api = get_fuse_python_api()

##########
###
###  Parsing for FUSE.
###
##########



class FuseArgs:
    """
    Class representing a FUSE command line.
    """

    fuse_modifiers = {'showhelp': '-ho',
                      'showversion': '-V',
                      'foreground': '-f'}

    def __init__(self):
        self.modifiers = {}
        self.mountpoint = None
        self.optlist = set()
        self.optdict = {}

        for m in self.fuse_modifiers:
            self.modifiers[m] = False

    def __str__(self):
        return '\n'.join(['< on ' + str(self.mountpoint) + ':',
                          '  ' + str(self.modifiers), '  -o ']) + \
               ',\n     '.join(self._str_core()) + \
               ' >'

    def _str_core(self):
        sa = []
        for k, v in self.optdict.items():
            sa.append(str(k) + '=' + str(v))
        ra = (list(self.optlist) + sa) or ["(none)"]
        ra.sort()
        return ra

    def getmod(self, mod):
        return self.modifiers[mod]

    def setmod(self, mod):
        self.modifiers[mod] = True

    def unsetmod(self, mod):
        self.modifiers[mod] = False

    def mount_expected(self):
        if self.getmod('showhelp'):
            return False
        if self.getmod('showversion'):
            return False
        return True

    def assemble(self):
        """Mangle self into an argument array"""

        self.canonify()
        # Use the actual program name from sys.argv[0]
        args = [os.path.basename(sys.argv[0]) if sys.argv else "python"]
        if self.mountpoint:
            args.append(self.mountpoint)
        for m, v in self.modifiers.items():
            if v:
                args.append(self.fuse_modifiers[m])

        opta = []
        # Add options in a consistent order
        for o in sorted(self.optlist):
            opta.append(o)
        for o, v in sorted(self.optdict.items()):
            opta.append(o + '=' + v)

        if opta:
            args.append("-o" + ",".join(opta))

        return args

    def canonify(self):
        """Transform self to an equivalent canonical form"""
        # Create a list of items to process to avoid modifying during iteration
        items = list(self.optdict.items())
        for k, v in items:
            if v == False:
                self.optdict.pop(k)
            elif v == True:
                self.optdict.pop(k)
                self.optlist.add(v)
            else:
                self.optdict[k] = str(v)

    def filter(self, other=None):
        """Filter options based on another FuseArgs instance"""
        if not other:
            other = Fuse.fuseoptref()

        self.canonify()
        other.canonify()

        rej = self.__class__()
        rej.optlist = self.optlist.difference(other.optlist)
        self.optlist.difference_update(rej.optlist)
        for x in self.optdict.copy():
            if x not in other.optdict:
                self.optdict.pop(x)
                rej.optdict[x] = None

        return rej

    def add(self, opt, val=None):
        """Add a suboption"""
        ov = opt.split('=', 1)
        o = ov[0]
        v = len(ov) > 1 and ov[1] or None

        if v:
            if val is not None:
                raise AttributeError("ambiguous option value")
            val = v

        if val == False:
            return

        if val in (None, True):
            self.optlist.add(o)
        else:
            self.optdict[o] = val


# Custom error class for FUSE-specific errors
class FuseError(Exception):
    """Exception raised for FUSE-specific errors"""
    pass

#  Custom action for the -s option
class SingleThreadAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if parser.fuse:
            parser.fuse.multithreaded = False


class FuseOptParse(ArgumentParser):
    """
    This class alters / enhances `ArgumentParser` so that it's
    suitable for usage with FUSE.

    - When adding options, you can use the `mountopt` pseudo-attribute which
      is equivalent with adding a subopt for option ``-o``
      (it doesn't require an option argument).

    - FUSE compatible help and version printing.

    - Error and exit callbacks are relaxed. In case of FUSE, the command
      line is to be treated as a DSL [#]_. You don't wanna this module to
      force an exit on you just because you hit a DSL syntax error.

    - Built-in support for conventional FUSE options (``-d``, ``-f`, ``-s``).
      The way of this can be tuned by keyword arguments, see below.

    .. [#] http://en.wikipedia.org/wiki/Domain-specific_programming_language

    Keyword arguments for initialization
    ------------------------------------

    standard_mods
      Boolean [default is `True`].
      Enables support for the usual interpretation of the ``-d``, ``-f``
      options.

    fetch_mp
      Boolean [default is `True`].
      If it's True, then the last (non-option) argument
      (if there is such a thing) will be used as the FUSE mountpoint.

    dash_s_do
      String: ``whine``, ``undef``, or ``setsingle`` [default is ``whine``].
      The ``-s`` option -- traditionally for asking for single-threadedness --
      is an oddball: single/multi threadedness of a fuse-py fs doesn't depend
      on the FUSE command line, we have direct control over it.

      Therefore we have two conflicting principles:

      - *Orthogonality*: option parsing shouldn't affect the backing `Fuse`
        instance directly, only via its `fuse_args` attribute.

      - *POLS*: behave like other FUSE based fs-es do. The stock FUSE help
        makes mention of ``-s`` as a single-threadedness setter.

      So, if we follow POLS and implement a conventional ``-s`` option, then
      we have to go beyond the `fuse_args` attribute and set the respective
      Fuse attribute directly, hence violating orthogonality.

      We let the fs authors make their choice: ``dash_s_do=undef`` leaves this
      option unhandled, and the fs author can add a handler as she desires.
      ``dash_s_do=setsingle`` enables the traditional behaviour.

      Using ``dash_s_do=setsingle`` is not problematic at all, but we want fs
      authors be aware of the particularity of ``-s``, therefore the default is
      the ``dash_s_do=whine`` setting which raises an exception for ``-s`` and
      suggests the user to read this documentation.

    dash_o_handler
      Argument should be a handler for the ``-o`` option. For example,
      you can alter or suppress the generic ``-o`` entry in help output.
    """

    def __init__(self, *args, **kw):

        self.mountopts = []
        self.fuse_args = kw.pop('fuse_args', FuseArgs())
        dsd = kw.pop('dash_s_do', 'whine')
        self.fetch_mp = kw.pop('fetch_mp', True)
        smods = kw.pop('standard_mods', True)
        self.fuse = kw.pop('fuse', None)
        doh = kw.pop('dash_o_handler', None)

        # Handle version parameter
        version = kw.pop('version', None)
        if version:
            kw['description'] = version

        # Call super().__init__() without version argument
        super().__init__(*args, **kw)

        # Add version action after super().__init__()
        if version:
            self.add_argument('--version', action='version', version=version)

        # Add mountpoint argument first
        if self.fetch_mp:
            self.add_argument('mountpoint', nargs='?', help='Mount point')

        # Add mount options handler
        if doh:
            self.add_argument(doh)
        else:
            self.add_argument('-o', '--options', help="mount options",
                            metavar="opt,[opt...]", dest='mount_options',
                            action='store', default='')

        # Add standard FUSE modifiers
        if smods:
            self.add_argument('-f', '--foreground', action='store_true',
                            help=SUPPRESS, dest='foreground')
            self.add_argument('-d', '--debug', action='store_true',
                            help=SUPPRESS, dest='debug')

        # Handle -s option based on dash_s_do setting
        if dsd == 'whine':
            def dsdcb(option, opt_str, value, parser):
                raise FuseError("""

! If you want the "-s" option to work, pass
!
!   dash_s_do='setsingle'
!
! to the Fuse constructor. See docstring of the FuseOptParse class for an
! explanation why is it not set by default.
""")

        elif dsd == 'setsingle':
            self.add_argument('-s', '--single', action=SingleThreadAction,
                              nargs=0, help=SUPPRESS)
        elif dsd != 'undef':
            raise ValueError("key 'dash_s_do': uninterpreted value " + str(dsd))


    def parse_args(self, args=None, namespace=None):
        """Parse command line arguments"""
        if namespace is None:
            namespace = argparse.Namespace()

        # Store original args for mountpoint handling
        original_args = args

        # Parse arguments
        parsed_args = super().parse_args(args, namespace)

        # Handle mountpoint
        if hasattr(parsed_args, 'mountpoint') and parsed_args.mountpoint and self.fetch_mp:
            self.fuse_args.mountpoint = os.path.realpath(parsed_args.mountpoint)
        elif original_args and len(original_args) > 0 and not original_args[0].startswith('-'):
            # If no mountpoint argument was provided but we have a positional argument
            # that's not an option, use it as the mountpoint
            self.fuse_args.mountpoint = os.path.realpath(original_args[0])

        # Handle modifiers
        if hasattr(parsed_args, 'foreground') and parsed_args.foreground:
            self.fuse_args.setmod('foreground')
        if hasattr(parsed_args, 'debug') and parsed_args.debug:
            self.fuse_args.add('debug')

        # Handle mount options
        if hasattr(parsed_args, 'mount_options') and parsed_args.mount_options:
            for opt in parsed_args.mount_options.split(','):
                self.fuse_args.add(opt)

        return parsed_args

    def add_argument(self, *args, **kwargs):
        """Add an argument to the parser"""
        if 'mountopt' in kwargs:
            if args or 'action' in kwargs:
                raise ValueError(
                    "having options or specifying the `action' attribute conflicts with `mountopt' attribute")
            kwargs['action'] = 'store'
            kwargs['dest'] = kwargs.pop('mountopt')
            args = ('-o', '--options')

        return super().add_argument(*args, **kwargs)

    def error(self, message):
        """Handle parsing errors"""
        raise FuseError(message)

    def exit(self, status=0, message=None):
        """Handle parser exit"""
        if message:
            sys.stderr.write(message)


##########
###
###  The FUSE interface.
###
##########



class ErrnoWrapper(object):

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kw):
        try:
            return self.func(*args, **kw)
        except (IOError, OSError) as detail:
            # Sometimes this is an int, sometimes an instance...
            if hasattr(detail, "errno"): detail = detail.errno
            return -detail


########### Custom objects for transmitting system structures to FUSE

class FuseStruct(object):

    def __init__(self, **kw):
        for k in kw:
             setattr(self, k, kw[k])


class Stat(FuseStruct):
    """
    Auxiliary class which can be filled up stat attributes.
    The attributes are undefined by default.
    """

    def __init__(self, **kw):
        self.st_mode  = None
        self.st_ino   = 0
        self.st_dev   = 0
        self.st_nlink = None
        self.st_uid   = 0
        self.st_gid   = 0
        self.st_size  = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

        FuseStruct.__init__(self, **kw)


class StatVfs(FuseStruct):
    """
    Auxiliary class which can be filled up statvfs attributes.
    The attributes are 0 by default.
    """

    def __init__(self, **kw):

        self.f_bsize   = 0
        self.f_frsize  = 0
        self.f_blocks  = 0
        self.f_bfree   = 0
        self.f_bavail  = 0
        self.f_files   = 0
        self.f_ffree   = 0
        self.f_favail  = 0
        self.f_flag    = 0
        self.f_namemax = 0

        FuseStruct.__init__(self, **kw)


class Direntry(FuseStruct):
    """
    Auxiliary class for carrying directory entry data.
    Initialized with `name`. Further attributes (each
    set to 0 as default):

    offset
        An integer (or long) parameter, used as a bookmark
        during directory traversal.
        This needs to be set it you want stateful directory
        reading.

    type
       Directory entry type, should be one of the stat type
       specifiers (stat.S_IFLNK, stat.S_IFBLK, stat.S_IFDIR,
       stat.S_IFCHR, stat.S_IFREG, stat.S_IFIFO, stat.S_IFSOCK).

    ino
       Directory entry inode number.

    Note that Python's standard directory reading interface is
    stateless and provides only names, so the above optional
    attributes doesn't make sense in that context.
    """

    def __init__(self, name, **kw):

        self.name   = name
        self.offset = 0
        self.type   = 0
        self.ino    = 0

        FuseStruct.__init__(self, **kw)


class Flock(FuseStruct):
    """
    Class for representing flock structures (cf. fcntl(3)).

    It makes sense to give values to the `l_type`, `l_start`,
    `l_len`, `l_pid` attributes (`l_whence` is not used by
    FUSE, see ``fuse.h``).
    """

    def __init__(self, name=None, **kw):

        self.l_type  = None
        self.l_start = None
        self.l_len   = None
        self.l_pid   = None

        kw['name'] = name
        FuseStruct.__init__(self, **kw)


class Timespec(FuseStruct):
    """
    Cf. struct timespec in time.h:
    http://www.opengroup.org/onlinepubs/009695399/basedefs/time.h.html
    """

    def __init__(self, name=None, **kw):

        self.tv_sec  = None
        self.tv_nsec = None

        kw['name'] = name
        FuseStruct.__init__(self, **kw)


class FuseFileInfo(FuseStruct):

    def __init__(self, **kw):

        self.keep      = False
        self.direct_io = False

        FuseStruct.__init__(self, **kw)



########## Interface for requiring certain features from your underlying FUSE library.

def feature_needs(*feas):
    """
    Get info about the FUSE API version needed for the support of some features.

    This function takes a variable number of feature patterns.

    A feature pattern is either:

    -  an integer (directly referring to a FUSE API version number)
    -  a built-in feature specifier string (meaning defined by dictionary)
    -  a string of the form ``has_foo``, where ``foo`` is a filesystem method
       (refers to the API version where the method has been introduced)
    -  a list/tuple of other feature patterns (matches each of its members)
    -  a regexp (meant to be matched against the builtins plus ``has_foo``
       patterns; can also be given by a string of the from "re:*")
    -  a negated regexp (can be given by a string of the form "!re:*")

    If called with no arguments, then the list of builtins is returned, mapped
    to their meaning.

    Otherwise the function returns the smallest FUSE API version number which
    has all the matching features.

    Builtin specifiers worth to explicit mention:
    - ``stateful_files``: you want to use custom filehandles (eg. a file class).
    - ``*``: you want all features.
    - while ``has_foo`` makes sense for all filesystem method ``foo``, some
      of these can be found among the builtins, too (the ones which can be
      handled by the general rule).

    specifiers like ``has_foo`` refer to requirement that the library knows of
      the fs method ``foo``.
    """

    fmap = {'stateful_files': 22,
            'stateful_dirs':  23,
            'stateful_io':    ('stateful_files', 'stateful_dirs'),
            'stateful_files_keep_cache': 23,
            'stateful_files_direct_io': 23,
            'keep_cache':     ('stateful_files_keep_cache',),
            'direct_io':      ('stateful_files_direct_io',),
            'has_opendir':    ('stateful_dirs',),
            'has_releasedir': ('stateful_dirs',),
            'has_fsyncdir':   ('stateful_dirs',),
            'has_create':     25,
            'has_access':     25,
            'has_fgetattr':   25,
            'has_ftruncate':  25,
            'has_fsinit':     ('has_init'),
            'has_fsdestroy':  ('has_destroy'),
            'has_lock':       26,
            'has_utimens':    26,
            'has_bmap':       26,
            'has_init':       23,
            'has_destroy':    23,
            '*':              r'!re:^\*$'}

    if not feas:
        return fmap

    def resolve(args, maxva):

        for fp in args:
            if isinstance(fp, int):
                maxva[0] = max(maxva[0], fp)
                continue
            if isinstance(fp, list) or isinstance(fp, tuple):
                for f in fp:
                    yield f
                continue
            ma = isinstance(fp, str) and re.compile(r"(!\s*|)re:(.*)").match(fp)
            if isinstance(fp, type(re.compile(''))) or ma:
                neg = False
                if ma:
                    mag = ma.groups()
                    fp = re.compile(mag[1])
                    neg = bool(mag[0])
                for f in list(fmap.keys()) + [ 'has_' + a for a in Fuse._attrs ]:
                    if neg != bool(re.search(fp, f)):
                        yield f
                continue
            ma = re.compile("has_(.*)").match(fp)
            if ma and ma.groups()[0] in Fuse._attrs and not fp in fmap:
                yield 21
                continue
            yield fmap[fp]

    maxva = [0]
    while feas:
        feas = set(resolve(feas, maxva))

    return maxva[0]


def APIVersion():
    """Get the API version of your underlying FUSE lib"""

    return FuseAPIVersion()


def feature_assert(*feas):
    """
    Takes some feature patterns (like in `feature_needs`).
    Raises a fuse.FuseError if your underlying FUSE lib fails
    to have some of the matching features.

    (Note: use a ``has_foo`` type feature assertion only if lib support
    for method ``foo`` is *necessary* for your fs. Don't use this assertion
    just because your fs implements ``foo``. The usefulness of ``has_foo``
    is limited by the fact that we can't guarantee that your FUSE kernel
    module also supports ``foo``.)
    """

    fav = APIVersion()

    for fea in feas:
        fn = feature_needs(fea)
        if fav < fn:
            raise FuseError(
              "FUSE API version %d is required for feature `%s' but only %d is available" % \
              (fn, str(fea), fav))


############# Subclass this.

class Fuse(object):
    """
    Python interface to FUSE.

    Basic usage:

    - instantiate

    - add options to `parser` attribute (an instance of `FuseOptParse`)

    - call `parse`

    - call `main`
    """

    _attrs = ['getattr', 'readlink', 'readdir', 'mknod', 'mkdir',
              'unlink', 'rmdir', 'symlink', 'rename', 'link', 'chmod',
              'chown', 'truncate', 'utime', 'open', 'read', 'write', 'release',
              'statfs', 'fsync', 'create', 'opendir', 'releasedir', 'fsyncdir',
              'flush', 'fgetattr', 'ftruncate', 'getxattr', 'listxattr',
              'setxattr', 'removexattr', 'access', 'lock', 'utimens', 'bmap',
              'fsinit', 'fsdestroy', 'ioctl', 'poll']

    fusage = "%prog [mountpoint] [options]"

    def __init__(self, *args, **kw):
        """
        Not much happens here apart from initializing the `parser` attribute.
        Arguments are forwarded to the constructor of the parser class almost
        unchanged.

        The parser class is `FuseOptParse` unless you specify one using the
        ``parser_class`` keyword. (See `FuseOptParse` documentation for
        available options.)
        """

        if not fuse_python_api:
            raise RuntimeError(__name__ + """.fuse_python_api not defined.

! Please define """ + __name__ + """.fuse_python_api internally (eg.
!
! (1)  """ + __name__ + """.fuse_python_api = """ + repr(FUSE_PYTHON_API_VERSION) + """
!
! ) or in the enviroment (eg.
!
! (2)  FUSE_PYTHON_API=0.1
!
! ).
!
! If you are actually developing a filesystem, probably (1) is the way to go.
! If you are using a filesystem written before 2007 Q2, probably (2) is what
! you want."
""")

        def malformed():
            raise RuntimeError("malformatted fuse_python_api value " + repr(fuse_python_api))
        if not isinstance(fuse_python_api, tuple):
            malformed()
        for i in fuse_python_api:
            if not isinstance(i, int) or i < 0:
                malformed()

        if fuse_python_api > FUSE_PYTHON_API_VERSION:
            raise RuntimeError("""
! You require FUSE-Python API version """ + repr(fuse_python_api) + """.
! However, the latest available is """ + repr(FUSE_PYTHON_API_VERSION) + """.
""")

        self.fuse_args = kw.pop('fuse_args', FuseArgs())

        if get_compat_0_1():
            return self.__init_0_1__(*args, **kw)

        self.multithreaded = True

        if not 'usage' in kw:
            kw['usage'] = self.fusage
        if not 'fuse_args' in kw:
            kw['fuse_args'] = self.fuse_args
        kw['fuse'] = self
        parserclass = kw.pop('parser_class', FuseOptParse)

        # Handle version argument before passing to parser
        version = kw.pop('version', None)
        if version:
            kw['description'] = version

        self.parser = parserclass(*args, **kw)
        self.methproxy = self.Methproxy()

    def parse(self, *args, **kw):
        """Parse command line, fill `fuse_args` attribute."""

        exit_value = kw.pop('errex', None)
        if exit_value is not None and not isinstance(exit_value, int):
            raise TypeError("error exit value should be an integer")

        try:
            self.cmdline = self.parser.parse_args(*args, **kw)
        except FuseError:
            if exit_value is not None:
                sys.exit(exit_value)
            raise

        return self.fuse_args

    def main(self, args=None):
        """Enter filesystem service loop."""

        if get_compat_0_1():
            args = self.main_0_1_preamble()

        d = {'multithreaded': self.multithreaded and 1 or 0}
        d['fuse_args'] = args or self.fuse_args.assemble()

        for t in 'file_class', 'dir_class':
            if hasattr(self, t):
                getattr(self.methproxy, 'set_' + t)(getattr(self,t))

        for a in self._attrs:
            b = a
            if get_compat_0_1() and a in self.compatmap:
                b = self.compatmap[a]
            if hasattr(self, b):
                c = ''
                if get_compat_0_1() and hasattr(self, a + '_compat_0_1'):
                    c = '_compat_0_1'
                d[a] = ErrnoWrapper(self.lowwrap(a + c))

        try:
            main(**d)
        except FuseError:
            if args or self.fuse_args.mount_expected():
                raise

    def lowwrap(self, fname):
        """
        Wraps the fname method when the C code expects a different kind of
        callback than we have in the fusepy API. (The wrapper is usually for
        performing some checks or transfromations which could be done in C but
        is simpler if done in Python.)

        Currently `open` and `create` are wrapped: a boolean flag is added
        which indicates if the result is to be kept during the opened file's
        lifetime or can be thrown away. Namely, it's considered disposable
        if it's an instance of FuseFileInfo.
        """
        fun = getattr(self, fname)

        if fname in ('open', 'create'):
            def wrap(*a, **kw):
                res = fun(*a, **kw)
                if not res or type(res) == type(0):
                    return res
                else:
                    return (res, type(res) != FuseFileInfo)
        elif fname == 'utimens':
            def wrap(path, acc_sec, acc_nsec, mod_sec, mod_nsec):
                ts_acc = Timespec(tv_sec = acc_sec, tv_nsec = acc_nsec)
                ts_mod = Timespec(tv_sec = mod_sec, tv_nsec = mod_nsec)
                return fun(path, ts_acc, ts_mod)
        else:
            wrap = fun

        return wrap

    def GetContext(self):
        return FuseGetContext(self)

    def Invalidate(self, path):
        return FuseInvalidate(self, path)

    def NotifyPoll(self, pollhandle):
        return FuseNotifyPoll(pollhandle)

    def fuseoptref(cls):
        """
        Find out which options are recognized by the library.
        Result is a `FuseArgs` instance with the list of supported
        options, suitable for passing on to the `filter` method of
        another `FuseArgs` instance.
        """

        import os, re

        pr, pw = os.pipe()
        pid = os.fork()
        if pid == 0:
             os.dup2(pw, 2)
             os.close(pr)

             fh = cls()
             fh.fuse_args = FuseArgs()
             fh.fuse_args.setmod('showhelp')
             fh.main()
             sys.exit()

        os.close(pw)

        fa = FuseArgs()
        ore = re.compile(r"-o\s+([\w\[\]]+(?:=\w+)?)")
        fpr = os.fdopen(pr)
        for l in fpr:
             m = ore.search(l)
             if m:
                 o = m.groups()[0]
                 oa = [o]
                 # try to catch two-in-one options (like "[no]foo")
                 opa = o.split("[")
                 if len(opa) == 2:
                    o1, ox = opa
                    oxpa = ox.split("]")
                    if len(oxpa) == 2:
                       oo, o2 = oxpa
                       oa = [o1 + o2, o1 + oo + o2]
                 for o in oa:
                     fa.add(o)

        fpr.close()
        return fa

    fuseoptref = classmethod(fuseoptref)


    class Methproxy(object):

        def __init__(self):

            class mpx(object):
               def __init__(self, name):
                   self.name = name
               def __call__(self, *a, **kw):
                   return getattr(a[-1], self.name)(*(a[1:-1]), **kw)

            self.proxyclass = mpx
            self.mdic = {}
            self.file_class = None
            self.dir_class = None

        def __call__(self, meth):
            return meth in self.mdic and self.mdic[meth] or None

        def _add_class_type(cls, type, inits, proxied):

            def setter(self, xcls):

                setattr(self, type + '_class', xcls)

                for m in inits:
                    self.mdic[m] = xcls

                for m in proxied:
                    if hasattr(xcls, m):
                        self.mdic[m] = self.proxyclass(m)

            setattr(cls, 'set_' + type + '_class', setter)

        _add_class_type = classmethod(_add_class_type)

    Methproxy._add_class_type('file', ('open', 'create'),
                              ('read', 'write', 'fsync', 'release', 'flush',
                               'fgetattr', 'ftruncate', 'lock'))
    Methproxy._add_class_type('dir', ('opendir',),
                              ('readdir', 'fsyncdir', 'releasedir'))


    def __getattr__(self, meth):

        m = self.methproxy(meth)
        if m:
            return m

        raise AttributeError("Fuse instance has no attribute '%s'" % meth)



##########
###
###  Compat stuff.
###
##########



    def __init_0_1__(self, *args, **kw):

        self.flags = 0
        multithreaded = 0

        # default attributes
        if args == ():
            # there is a self.optlist.append() later on, make sure it won't
            # bomb out.
            self.optlist = []
        else:
            self.optlist = args
        self.optdict = kw

        if len(self.optlist) == 1:
            self.mountpoint = self.optlist[0]
        else:
            self.mountpoint = None

        # grab command-line arguments, if any.
        # Those will override whatever parameters
        # were passed to __init__ directly.
        argv = sys.argv
        argc = len(argv)
        if argc > 1:
            # we've been given the mountpoint
            self.mountpoint = argv[1]
        if argc > 2:
            # we've received mount args
            optstr = argv[2]
            opts = optstr.split(",")
            for o in opts:
                try:
                    k, v = o.split("=", 1)
                    self.optdict[k] = v
                except:
                    self.optlist.append(o)


    def main_0_1_preamble(self):

        cfargs = FuseArgs()

        cfargs.mountpoint = self.mountpoint

        if hasattr(self, 'debug'):
            cfargs.add('debug')

        if hasattr(self, 'allow_other'):
            cfargs.add('allow_other')

        if hasattr(self, 'kernel_cache'):
            cfargs.add('kernel_cache')

        return cfargs.assemble()


    def getattr_compat_0_1(self, *a):
        from os import stat_result

        return stat_result(self.getattr(*a))


    def statfs_compat_0_1(self, *a):

        oout = self.statfs(*a)
        lo = len(oout)

        svf = StatVfs()
        svf.f_bsize   = oout[0]                   # 0
        svf.f_frsize  = oout[lo >= 8 and 7 or 0]  # 1
        svf.f_blocks  = oout[1]                   # 2
        svf.f_bfree   = oout[2]                   # 3
        svf.f_bavail  = oout[3]                   # 4
        svf.f_files   = oout[4]                   # 5
        svf.f_ffree   = oout[5]                   # 6
        svf.f_favail  = lo >= 9 and oout[8] or 0  # 7
        svf.f_flag    = lo >= 10 and oout[9] or 0 # 8
        svf.f_namemax = oout[6]                   # 9

        return svf


    def readdir_compat_0_1(self, path, offset, *fh):

        for name, type in self.getdir(path):
            de = Direntry(name)
            de.type = type

            yield de


    compatmap = {'readdir': 'getdir'}
