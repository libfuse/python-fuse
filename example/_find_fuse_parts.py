import sys, os, glob 
from os.path import realpath, dirname, join

ddd = realpath(join(dirname(sys.argv[0]), '..'))

for d in [ddd, '.']: 
    for p in glob.glob(join(d, 'build', 'lib.*')):
         sys.path.append(p)

try:
    import fuse
except ImportError:
    raise RuntimeError, """

! Have you ran `python setup.py build'?
!
! We've done our best to find the necessary components of the FUSE bindings
! in an uninstalled state, but no dice...
"""
