# distutils build script
# To install fuse-python, run 'python setup.py install'

# This setup.py based on that of shout-python (py bindings for libshout,
# part of the icecast project, http://svn.xiph.org/icecast/trunk/shout-python)

from distutils.core import setup, Extension
import os
import sys

from fuseparts import __version__ 

# write default fuse.pc path into environment if PKG_CONFIG_PATH is unset
#if not os.environ.has_key('PKG_CONFIG_PATH'):
#  os.environ['PKG_CONFIG_PATH'] = '/usr/local/lib/pkgconfig'

# Find fuse compiler/linker flag via pkgconfig
if os.system('pkg-config --exists fuse 2> /dev/null') == 0:
    pkgcfg = os.popen('pkg-config --cflags fuse')
    cflags = pkgcfg.readline().strip()
    pkgcfg.close()
    pkgcfg = os.popen('pkg-config --libs fuse')
    libs = pkgcfg.readline().strip()
    pkgcfg.close()

else:
    if os.system('pkg-config --usage 2> /dev/null') == 0:
        print """pkg-config could not find fuse:
you might need to adjust PKG_CONFIG_PATH or your 
FUSE installation is very old (older than 2.1-pre1)"""

    else:
        print "pkg-config unavailable, build terminated"
        sys.exit(1)

# there must be an easier way to set up these flags!
iflags = [x[2:] for x in cflags.split() if x[0:2] == '-I']
extra_cflags = [x for x in cflags.split() if x[0:2] != '-I']
libdirs = [x[2:] for x in libs.split() if x[0:2] == '-L']
libsonly = [x[2:] for x in libs.split() if x[0:2] == '-l']

try:
    import thread
except ImportError:
    # if our Python doesn't have thread support, we enforce
    # linking against libpthread so that libfuse's pthread
    # related symbols won't be undefined
    libsonly.append("pthread")

# include_dirs=[]
# libraries=[]
# runtime_library_dirs=[]
# extra_objects, extra_compile_args, extra_link_args
fusemodule = Extension('fuseparts._fusemodule', sources = ['fuseparts/_fusemodule.c'],
                  include_dirs = iflags,
                  extra_compile_args = extra_cflags,
                  library_dirs = libdirs,
                  libraries = libsonly)

# data_files = []
setup (name = 'fuse-python',
       version = __version__,
       description = 'Bindings for FUSE',
       url = 'http://fuse.sourceforge.net',
       author = 'Jeff Epler',
       author_email = 'jepler@unpythonic.dhs.org',
       maintainer = 'Csaba Henk',
       maintainer_email = 'csaba.henk@creo.hu',
       ext_modules = [fusemodule],
       packages = ["fuseparts"],
       py_modules=["fuse"])
