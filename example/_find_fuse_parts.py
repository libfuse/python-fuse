import sys, os, glob 
from os.path import realpath, dirname, join, isdir

ddd = realpath(join(dirname(sys.argv[0]), '..'))
cdirs = [ d for d in ('.', ddd) if isdir(join(d, 'build')) ]
if ddd in cdirs:
    sys.path.append(ddd)

def lookupso(dirs):
    for d in dirs:
        for p in glob.glob(join(d, 'build', 'lib.*', '_fusemodule.so')):
             return dirname(p)

p = lookupso(cdirs)
if p:
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
