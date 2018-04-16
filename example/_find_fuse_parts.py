import sys, os, glob
from os.path import realpath, dirname, join
from traceback import format_exception

PYTHON_MAJOR_MINOR = "%s.%s" % (sys.version_info[0], sys.version_info[1])

ddd = realpath(join(dirname(sys.argv[0]), '..'))

for d in [ddd, '.']: 
    for p in glob.glob(join(d, 'build', 'lib.*%s' % PYTHON_MAJOR_MINOR)):
        sys.path.insert(0, p)

try:
    import fuse
except ImportError:
    raise RuntimeError("""

! Got exception:
""" + "".join([ "> " + x for x in format_exception(*sys.exc_info()) ]) + """
! Have you ran `python setup.py build'?
!
! We've done our best to find the necessary components of the FUSE bindings
! even if it's not installed, we've got no clue what went wrong for you...
""")
