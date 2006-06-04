#
#    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>
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

from _fusemeta import __version__ 
from _fuse import main, FuseGetContext, FuseInvalidate, FuseError, FuseAPIVersion
from string import join
import sys
from errno import *
from os import environ
from optparse import Option, OptionParser, OptParseError, OptionConflictError
from optparse import IndentedHelpFormatter, SUPPRESS_HELP
from sets import Set

compat_0_1 = environ.has_key('FUSE_PYTHON_COMPAT') and \
             environ['FUSE_PYTHON_COMPAT'] in ('0.1', 'ALL')


##########
###
###  Parsing related stuff.
###
##########

# XXX We should break out respective base classes from the following
# ones, which would implement generic parsing of comma separated suboptions,
# and would be free of FUSE specific hooks.

class FuseArgs(object):
    """
    Class representing a FUSE command line.
    """

    fuse_modifiers = {'showhelp': '-ho',
                      'showversion': '-V',        
                      'foreground': '-f'}

    def __init__(self):

        self.modifiers = {}
        self.optlist = Set([])
        self.optdict = {}
        self.mountpoint = None

        for m in self.fuse_modifiers:
            self.modifiers[m] = False

    def __str__(self):

        sa = []
        for k, v in self.optdict.iteritems():
             sa.append(str(k) + '=' + str(v))

        return '\n'.join(['< on ' + str(self.mountpoint) + ':',
                          '  ' + str(self.modifiers), '  -o ']) + \
               ',\n     '.join((list(self.optlist) + sa) or ["(none)"]) + \
               ' >'

    def getmod(self, mod):
        return self.modifiers[mod]

    def setmod(self, mod):
        self.modifiers[mod] = True

    def unsetmod(self, mod):
        self.modifiers[mod] = False

    def do_mount(self):

        if self.getmod('showhelp'):
            return False
        if self.getmod('showversion'):
            return False
        return True

    def assemble(self):
        """Mangle self into an argument array"""

        self.canonify()
        args = [sys.argv and sys.argv[0] or "python"]
        if self.mountpoint:
            args.append(self.mountpoint)
        for m, v in self.modifiers.iteritems():
            if v:
                args.append(self.fuse_modifiers[m])

        opta = []
        for o, v in self.optdict.iteritems():
                opta.append(o + '=' + v)
        opta.extend(self.optlist)

        if opta:
            args.append("-o" + ",".join(opta)) 
        
        return args

    def canonify(self):
        """
        Transform self to an equivalent canonical form:
        delete optdict keys with False value, move optdict keys
        with True value to optlist, stringify other values.
        """

        for k, v in self.optdict.iteritems():
            if v == False:
                self.optdict.pop(k)
            elif v == True:
                self.optdict.pop(k)
                self.optlist.add(v)
            else:
                self.optdict[k] = str(v)

    def filter(self, other = None):
        """
        Throw away those options which are not in the other one.
        If other is `None`, `fuseoptref()` is run and its result will be used.
        Returns a `FuseArgs` instance with the rejected options.
        """

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
        """Add a mount option."""

        ov = opt.split('=', 1)
        o = ov[0]
        v = len(ov) > 1 and ov[1] or None

        if (v):
            if val != None:
                raise AttributeError, "ambiguous option value"
            val = v

        if val == False:
            return

        if val in (None, True):
            self.optlist.add(o)
        else:
            self.optdict[o] = val


class FuseOpt(Option):
    """
    Option subclass which support having a ``mountopt`` attr instead of
    short and long opts.
    """

    ATTRS = Option.ATTRS + ["mountopt"]

    def _check_opt_strings(self, opts):
        return opts

    def _check_dest(self):
        try:
            Option._check_dest(self)
        except IndexError:
            if self.mountopt:
                self.dest = self.mountopt
            else:
                raise

    def get_opt_string(self):
        if hasattr(self, 'mountopt'):
            return self.mountopt
        else:
            return Option.get_opt_string(self)

    CHECK_METHODS = []
    for m in Option.CHECK_METHODS:
        #if not m == Option._check_dest:
        if not m.__name__ == '_check_dest':
            CHECK_METHODS.append(m)
    CHECK_METHODS.append(_check_dest)


class FuseFormatter(IndentedHelpFormatter):

    def __init__(self, **kw):
        if not kw.has_key('indent_increment'):
            kw['indent_increment'] = 4  
        IndentedHelpFormatter.__init__(self, **kw)

    def format_option_strings(self, option):
        if hasattr(option, "mountopt"):
            res = '-o ' + option.mountopt
            if option.takes_value():
                res += "="
                res += option.metavar or 'FOO'
            return res

        return IndentedHelpFormatter.format_option_strings(self, option)

    def store_option_strings(self, parser): 
        IndentedHelpFormatter.store_option_strings(self, parser)
        # 27 is how the lib stock help appears
        self.help_position = max(self.help_position, 27)
        self.help_width = self.width - self.help_position 


class FuseOptParse(OptionParser):
    """
    This class alters / enhances `OptionParser` in the following ways:

    - Support for *mount option* handlers (instances of `FuseOpt`).
      These match comma separated members of a ``-o`` option.

    - `parse_args()` collects unhandled mount options, see there.

    - `parse_args()` also steals a mountpoint argument.

    - Built-in support for conventional FUSE options (``-d``, ``-f`, ``-s``).
      The way of this can be tuned by keyword arguments, see below.

    Keyword arguments
    ----------------
 
    standard_mods
      Boolean [default is `True`].
      Enables support for the usual interpretation of the ``-d``, ``-f``
      options.

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

      We let the fs authors make their choice: ``dash_s_do=undef`` leaves
      this option unhandled, and the fs author can add a handler as she desires.
      ``dash_s_do=setsingle`` enables the traditional behaviour.

      While using ``dash_s_do=setsingle`` usually won't be a problem, it might have
      suprising side effects. We want fs authors should be aware of it, therefore
      the default is the ``dash_s_do=whine`` setting which raises an exception
      for ``-s`` and suggests the user to read this documentation.
    """

    def __init__(self, *args, **kw):

         self.mountopts = []

         self.fuse_args = \
             kw.has_key('fuse_args') and kw.pop('fuse_args') or FuseArgs()

         dsd = kw.has_key('dash_s_do') and kw.pop('dash_s_do') or 'whine'

         smods = True
         if kw.has_key('standard_mods'):
             smods = kw.pop('standard_mods')
         if smods == None:
             smods = True

         if kw.has_key('fuse'):
             self.fuse = kw.pop('fuse')

         if not kw.has_key('formatter'):
             kw['formatter'] = FuseFormatter()
         OptionParser.__init__(self, *args, **kw)

         def gather_fuse_opt(option, opt_str, value, parser):
             for o in value.split(","):
                 oo = o.split('=')
                 ok = oo[0]
                 ov = None
                 if (len(oo) > 1):
                     ov = oo[1] 
                 for mopt in self.mountopts:
                     if mopt.mountopt == ok:
                         mopt.process(ok, ov, self.values, parser)
                         break
                     self.fuse_args.add(*oo)

         def fuse_foreground(option, opt_str, value, parser):
             self.fuse_args.setmod('foreground')

         def fuse_showhelp(option, opt_str, value, parser):
             self.fuse_args.setmod('showhelp')

         def fuse_debug(option, opt_str, value, parser):
             self.fuse_args.add('debug')

         self.add_option('-o', type=str, action='callback', callback=gather_fuse_opt, help=SUPPRESS_HELP)
         if smods:
             self.add_option('-f', action='callback', callback=fuse_foreground, help=SUPPRESS_HELP)
             self.add_option('-d', action='callback', callback=fuse_debug, help=SUPPRESS_HELP)

         if dsd == 'whine':
             def dsdcb(option, opt_str, value, parser):
                 raise RuntimeError, """

! If you want the "-s" option to work, pass
! 
!   dash_s_do='setsingle'
! 
! to the Fuse constructor. See docstring of the FuseOptParse class for an
! explanation why is it not set by default.
"""

         elif dsd == 'setsingle':
             def dsdcb(option, opt_str, value, parser):
                 self.fuse.multithreaded = False

         elif dsd == 'undef':
             dsdcb = None
         else:
             raise ArgumentError, "key `dash_s_do': uninterpreted value " + str(dsd)

         if dsdcb:
             self.add_option('-s', action='callback', callback=dsdcb,
                             help=SUPPRESS_HELP)
              

    def add_option(self, *args, **kwargs):
        if kwargs.has_key('mountopt'):
            o = FuseOpt(*args, **kwargs)
            for oo in self.mountopts:
                if oo.mountopt == o.mountopt:
                    raise OptionConflictError, "conflicting mount options: " + o.mountopt, o
            self.mountopts.append(o)
            args = (o,)
            kwargs = {} 
        return OptionParser.add_option(self, *args, **kwargs)

    def exit(self, status=0, msg=None):
        if msg:
            sys.stderr.write(msg)

    def error(self, msg):
        OptionParser.error(self, msg)
        raise OptParseError, msg

    def print_help(self, file=None):
        OptionParser.print_help(self, file)
        print
        self.fuse_args.setmod('showhelp')

    def print_version(self, file=None):
        OptionParser.print_version(self, file)
        self.fuse_args.setmod('showversion')

    def parse_args(self, args=None, values=None):
        """
        differences to :super: :

         - Return value is a triplet, where the first two
           entries are like for :super:, the third is a
           `FuseArgs` instance, in which unhandled mount
           options are collected.

         - One (non-option) argument is taken and passed on
           to the `FuseArgs` instance as its `mountpoint`
           attribute.
        """

        o, a = OptionParser.parse_args(self, args, values)
        if a: 
            self.fuse_args.mountpoint = a.pop()
        return o, a, self.fuse_args


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
            return apply(self.func, args, kw)
        except (IOError, OSError), detail:
            # Sometimes this is an int, sometimes an instance...
            if hasattr(detail, "errno"): detail = detail.errno
            return -detail


########### Custom objects for transmitting system structures to FUSE

class Stat(object):
    """
    Auxiliary class which can be filled up stat attributes.
    The attributes are undefined by default.
    """

    pass


class StatVfs(object):
    """
    Auxiliary class which can be filled up statvfs attributes.
    The attributes are 0 by default.
    """

    def __init__(self):

	self.f_bsize = 0
	self.f_frsize = 0
	self.f_blocks = 0
	self.f_bfree = 0
	self.f_bavail = 0
	self.f_files = 0
	self.f_ffree = 0
	self.f_favail = 0
	self.f_flag = 0
	self.f_namemax = 0

class Direntry(object):
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

    def __init__(self, name):

        self.name = name
        self.offset = 0
        self.type = 0
        self.ino = 0


########## Interface for requiring certain features from your underlying FUSE library.


def feature_need(*feas):
    """
    Takes a list of feature specifiers.
    Returns the smallest FUSE API version number which has all the given features.

    To see the list of valid feature specifiers (and the respective requirements),
    call it without arguments. Besides, any integer `n` is directly interpreted as 
    requiring FUSE API at least `n`.

    Specifiers worth to explicit mention:
    - ``stateful_files``: you want to use custom filehandles (eg. a file class).
    - ``*``: you want all features.
    """

    fmap = {'stateful_files': 22,
            'stateful_dirs': 23,
            'stateful_io': ('stateful_files', 'stateful_dirs'),
            'create': 25,
            'access': 25,
            'fgetattr': 25,
            'ftruncate': 25,
            '*': '.*'}

    if not feas:
        return fmap

    def match(fpat):
        import re

        if isinstance(fpat, list) or isinstance(fpat, tuple):
           return fpat

        if isinstance(fpat, str):
            fpat = re.compile(fpat)

        if not isinstance(fpat, type(re.compile(''))):  # ouch!
            raise TypeError, "unhandled pattern type `%s'" % type(fpat)

        return [ f for f in fmap if re.search(fpat, f) ]

    def resolve(feas):
        return max([ resolve_one(fea) for fea in feas ])

    def resolve_one(fea):

        if isinstance(fea, int):
            return fea

        if not fmap.has_key(fea):
            raise KeyError, "unknown FUSE feature `%s'" % str(fea)

        fv = fmap[fea]

        if isinstance(fv, int):
            return fv

        feas = match(fv)
        if fea in feas:
            feas.remove(fea)
        return resolve(feas)

    return resolve(feas)


def APIVersion():
    """Get the API version of your underlying FUSE lib"""

    return FuseAPIVersion()


def feature_req(*feas):
    """
    Takes a list of feature specifiers (like `feature_need`).
    Raises a fuse.FuseError if your underlying FUSE lib fails
    to have some of the features.
    """

    fav = APIVersion()

    for fea in feas:
        fn = feature_need(fea)
        if fav < fn:
            raise FuseError, \
              "FUSE API version %d is required for feature `%s' but only %d is available" % \
                 (fn, str(fea), fav)


############# Subclass this.


class Fuse(object):
    """
    Python interface to FUSE.
    """

    _attrs = ['getattr', 'readlink', 'readdir', 'mknod', 'mkdir',
              'unlink', 'rmdir', 'symlink', 'rename', 'link', 'chmod',
              'chown', 'truncate', 'utime', 'open', 'read', 'write', 'release',
              'statfs', 'fsync', 'create', 'opendir', 'releasedir', 'fsyncdir',
              'flush', 'fgetattr', 'ftruncate', 'getxattr', 'listxattr',
              'setxattr', 'removexattr', 'access']

    fusage = "%prog [mountpoint] [options]"
    
    def __init__(self, *args, **kw):
 
        self.fuse_args = \
            kw.has_key('fuse_args') and kw.pop('fuse_args') or FuseArgs()

        if compat_0_1: 
            return self.__init_0_1__(*args, **kw) 

        self.multithreaded = True
    
        if not kw.has_key('usage'):
            kw['usage'] = self.fusage 
        if not kw.has_key('fuse_args'):
            kw['fuse_args'] = self.fuse_args
        kw['fuse'] = self

        self.parser = FuseOptParse(*args, **kw)
        self.methproxy = self.Methproxy()

    def parse(self, *args, **kw):
        """Parse command line, fill `fuse_args` attribute."""

        ev = kw.has_key('errex') and kw.pop('errex')
        if ev and not isinstance(ev, int):
            raise TypeError, "error exit value should be an integer"

        try:
            o, a, fa = self.parser.parse_args(*args, **kw)
            self.cmdline = (o, a)
        except OptParseError:
          if ev:
              sys.exit(ev)
          raise

        return fa

    def main(self, args=None):
        """Enter filesystem service loop."""

        if compat_0_1:
            args = self.main_0_1_preamble()      

        d = {'multithreaded': self.multithreaded and 1 or 0}
        d['fuse_args'] = args or self.fuse_args.assemble()

        for t in 'file_class', 'dir_class':
            if hasattr(self, t):
                getattr(self.methproxy, 'set_' + t)(getattr(self,t))

        for a in self._attrs:
            b = a
            if compat_0_1 and self.compatmap.has_key(a):
                b = self.compatmap[a]
            if hasattr(self, b):
                c = ''
                if compat_0_1 and hasattr(self, a + '_compat_0_1'):
                    c = '_compat_0_1'
                d[a] = ErrnoWrapper(getattr(self, a + c))

        try:
            main(**d)
        except FuseError:
            if args or self.fuse_args.do_mount():
                raise

    def GetContext(self):
        return FuseGetContext(self)

    def Invalidate(self, path):
        return FuseInvalidate(self, path)
 
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
        ore = re.compile("-o\s+(\w+(?:=\w+)?)")
        fpr = os.fdopen(pr)
        for l in fpr:
             m = ore.search(l)
             if m:
                 fa.add(m.groups()[0])
    
        fpr.close()
        return fa 

    fuseoptref = classmethod(fuseoptref)


    class Methproxy(object):
    
        def __init__(self):
    
            class mpx(object):
               def __init__(self, name):
                   self.name = name
               def __call__(self, *a):
                   return getattr(a[-1], self.name)(*(a[1:-1]))
    
            self.proxyclass = mpx
            self.mdic = {}
            self.file_class = None
            self.dir_class = None
    
        def __call__(self, meth):
            return self.mdic.has_key(meth) and self.mdic[meth] or None
    
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
                               'fgetattr', 'ftruncate'))
    Methproxy._add_class_type('dir', ('opendir',),
                              [ m + 'dir' for m in 'read', 'fsync', 'release'])


    def __getattr__(self, meth):

        m = self.methproxy(meth)
        if m:
            return m

        raise AttributeError, "Fuse instance has no attribute '%s'" % meth


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
