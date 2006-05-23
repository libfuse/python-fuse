# distutils build script
# To install fuse-python, run 'python setup.py install'

# This setup.py based on that of south-python (py bindings for icecast)

from distutils.core import setup, Extension
import os
import sys

ver = '0.1.1'

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

# include_dirs=[]
# libraries=[]
# runtime_library_dirs=[]
# extra_objects, extra_compile_args, extra_link_args
fuse = Extension('_fusemodule', sources = ['_fusemodule.c'],
                  include_dirs = iflags,
                  extra_compile_args = extra_cflags,
                  library_dirs = libdirs,
                  libraries = libsonly)

# data_files = []
setup (name = 'fuse-python',
       version = ver,
       description = 'Bindings for FUSE',
       url = 'http://fuse.sourceforge.net',
       author = 'Jeff Epler',
       author_email = 'jepler@unpythonic.dhs.org',
       maintainer = 'Csaba Henk',
       maintainer_email = 'csaba.henk@creo.hu',
       ext_modules = [fuse])
