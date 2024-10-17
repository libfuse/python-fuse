#!/usr/bin/env python
# -*- coding: utf-8 -*-

# To install fuse-python, run 'python setup.py install'

# This setup.py based on that of shout-python (py bindings for libshout,
# part of the icecast project, http://svn.xiph.org/icecast/trunk/shout-python)

try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension
import os
import sys

from fuseparts import __version__

classifiers = [ "Development Status :: 5 - Production/Stable",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
                "Environment :: Console",
                "Operating System :: POSIX",
                "Programming Language :: C",
                "Programming Language :: Python",
                "Programming Language :: Python :: 2",
                "Programming Language :: Python :: 2.7",
                "Programming Language :: Python :: 3",
                "Programming Language :: Python :: 3.6",
                "Programming Language :: Python :: 3.7",
                "Programming Language :: Python :: 3.8",
                "Programming Language :: Python :: 3.9",
                "Programming Language :: Python :: 3.10",
                "Programming Language :: Python :: 3.11",
                "Programming Language :: Python :: 3.12",
                "Topic :: System :: Filesystems" ]

# write default fuse.pc path into environment if PKG_CONFIG_PATH is unset
#if not os.environ.has_key('PKG_CONFIG_PATH'):
#  os.environ['PKG_CONFIG_PATH'] = '/usr/local/lib/pkgconfig'

libs = cflags = ''

# Find fuse compiler/linker flag via pkgconfig
if os.system('pkg-config --exists fuse 2> /dev/null') == 0:
    pkgcfg = os.popen('pkg-config --cflags fuse')
    cflags = pkgcfg.readline().strip()
    pkgcfg.close()
    pkgcfg = os.popen('pkg-config --libs fuse')
    libs = pkgcfg.readline().strip()
    pkgcfg.close()

else:
    if os.system('pkg-config --help 2>&1 >/dev/null') == 0:
        print("""pkg-config could not find fuse:
you might need to adjust PKG_CONFIG_PATH or your
FUSE installation is very old (older than 2.1-pre1)""")

    else:
        print("pkg-config unavailable, build terminated")
        sys.exit(1)

# there must be an easier way to set up these flags!
iflags = [x[2:] for x in cflags.split() if x[0:2] == '-I']
extra_cflags = [x for x in cflags.split() if x[0:2] != '-I']
libdirs = [x[2:] for x in libs.split() if x[0:2] == '-L']
libsonly = [x[2:] for x in libs.split() if x[0:2] == '-l']

try:
    import _thread
except ImportError:
    # if our Python doesn't have thread support, we enforce
    # linking against libpthread so that libfuse's pthread
    # related symbols won't be undefined
    libsonly.append("pthread")

# include_dirs=[]
# libraries=[]
# runtime_library_dirs=[]
# extra_objects, extra_compile_args, extra_link_args
fusemodule = Extension('fuseparts._fuse', sources = ['fuseparts/_fusemodule.c'],
                  include_dirs = iflags,
                  extra_compile_args = extra_cflags,
                  library_dirs = libdirs,
                  libraries = libsonly)

# data_files = []
if sys.version_info < (2, 3):
    _setup = setup
    def setup(**kwargs):
        if "classifiers" in kwargs:
            del kwargs["classifiers"]
        _setup(**kwargs)

setup(name='fuse-python',
       version = __version__,
       description = 'Bindings for FUSE',
       long_description = """This is a Python interface to libfuse (https://github.com/libfuse/libfuse),
a simple interface for userspace programs to export a virtual filesystem to the Linux kernel""",
       classifiers = classifiers,
       license = 'LGPL',
       platforms = ['posix'],
       url = 'https://github.com/libfuse/python-fuse',
       package_data={'': ['COPYING', 'AUTHORS', 'FAQ', 'INSTALL',
                          'README.md', 'README.new_fusepy_api.rst',
                          'README.package_maintainers.rst']},
       author = 'Csaba Henk <csaba.henk@creo.hu>, Steven James, Miklos Szeredi <miklos@szeredi.hu>, Sébastien Delafond<sdelafond@gmail.com>',
       maintainer = 'Sébastien Delafond',
       maintainer_email = 'sdelafond@gmail.com',
       ext_modules = [fusemodule],
       packages = ["fuseparts"],
       py_modules=["fuse"])
