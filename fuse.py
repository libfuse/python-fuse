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
from _fuse import main, FuseGetContext, FuseInvalidate, FuseError
from string import join
import sys
from errno import *

class ErrnoWrapper:

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kw):
        try:
            return apply(self.func, args, kw)
        except (IOError, OSError), detail:
            # Sometimes this is an int, sometimes an instance...
            if hasattr(detail, "errno"): detail = detail.errno
            return -detail

class Fuse:

    _attrs = ['getattr', 'readlink', 'getdir', 'mknod', 'mkdir',
              'unlink', 'rmdir', 'symlink', 'rename', 'link', 'chmod',
              'chown', 'truncate', 'utime', 'open', 'read', 'write', 'release',
              'statfs', 'fsync']
    
    flags = 0
    multithreaded = 0
    
    def __init__(self, *args, **kw):
    
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

        # This kind of forced commandline parsing still sucks,
        # but:
        #  - changing it would hurt compatibility
        #  - if changed, that should be done cleverly:
        #    either by calling down to fuse_opt or coded
        #    purely in python, it should cherry-pick
        #    some args/opts based on a template and place
        #    that into a dict, and return the rest, so that
        #    can be passed to fuselib

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

    def GetContext(self):
        return FuseGetContext(self)

    def Invalidate(self, path):
        return FuseInvalidate(self, path)

    def main(self):

        d = {'mountpoint': self.mountpoint}
        d['multithreaded'] = self.multithreaded

        if not hasattr(self, 'fuse_opt_list'):
            self.fuse_opt_list = []

        # deprecated direct attributes for some fuse options
        for a in 'debug', 'allow_other', 'kernel_cache':
            if hasattr(self, a):
                self.fuse_opt_list.append(a);

        if not hasattr(self, 'fuse_opts'):
            self.fuse_opts = {}
        for o in self.fuse_opt_list:
            self.fuse_opts[o] = True

        nomount = False
        d['fuse_args'] = [] 
        # Regarding those lib options which are direct options 
        # (used as `-x' or `--foo', rather than `-o foo'):
        # we still prefer to have them as attributes
        for a in 'help', 'version':
            if hasattr(self, 'show' + a):
                d['fuse_args'].append('--' + a)
                nomount = True
        if hasattr(self, 'foreground'):
            d['fuse_args'].append('-f')

        opta = []
        for k in self.fuse_opts.keys():
            if self.fuse_opts[k] == True:
                opta.append(str(k))
            else:
                opta.append(str(k) + '=' + str(self.fuse_opts[k]))

        d['fuse_args'].append("-o" + ",".join(opta)) 

        for a in self._attrs:
            if hasattr(self,a):
                d[a] = ErrnoWrapper(getattr(self, a))
        try:
            apply(main, (), d)
        except FuseError:
            if not nomount: raise
