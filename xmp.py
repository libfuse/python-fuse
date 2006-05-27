#!/usr/bin/env python

#    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#

import os, sys
from errno import *
from stat import *
try:
    import fuse
    from fuse import Fuse
except ImportError:
    print >> sys.stderr, """
! If you are trying the Python example filesystem from
! the fuse-python source directory, without installation,
! you are suggested to link or copy build/lib.*/_fusemodule.so
! to the root of the source tree.
"""
    raise

if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

import thread
class Xmp(Fuse):

    root = '/'

    def __init__(self, *args, **kw):

        Fuse.__init__(self, *args, **kw)

        if 0:
            print "xmp.py:Xmp:mountpoint: %s" % repr(self.mountpoint)
            print "xmp.py:Xmp:unnamed mount options: %s" % self.optlist
            print "xmp.py:Xmp:named mount options: %s" % self.optdict

        # do stuff to set up your filesystem here, if you want
        #thread.start_new_thread(self.mythread, ())
        pass

    def mythread(self):

        """
        The beauty of the FUSE python implementation is that with the python interp
        running in foreground, you can have threads
        """
        print "mythread: started"
        #while 1:
        #    time.sleep(120)
        #    print "mythread: ticking"

    def getattr(self, path):
        return os.lstat(self.root + path)

    def readlink(self, path):
        return os.readlink(self.root + path)

    def getdir(self, path):
        return map(lambda x: (x,0), os.listdir(self.root + path))

    def unlink(self, path):
        return os.unlink(self.root + path)

    def rmdir(self, path):
        return os.rmdir(self.root + path)

    def symlink(self, path, path1):
        return os.symlink(path, self.root + path1)

    def rename(self, path, path1):
        return os.rename(self.root + path, self.root + path1)

    def link(self, path, path1):
        return os.link(self.root + path, self.root + path1)

    def chmod(self, path, mode):
        return os.chmod(self.root + path, mode)

    def chown(self, path, user, group):
        return os.chown(self.root + path, user, group)

    def truncate(self, path, size):
        f = open(self.root + path, "w+")
        return f.truncate(size)

    def mknod(self, path, mode, dev):
        """ Python has no os.mknod, so we can only do some things """
        if S_ISREG(mode):
            open(self.root + path, "w")
        else:
            return -EINVAL

    def mkdir(self, path, mode):
        return os.mkdir(self.root + path, mode)

    def utime(self, path, times):
        return os.utime(self.root + path, times)

    def open(self, path, flags):
        #print "xmp.py:Xmp:open: %s" % path
        os.close(os.open(self.root + path, flags))
        return 0

    def read(self, path, length, offset):
        #print "xmp.py:Xmp:read: %s" % path
        f = open(self.root + path, "r")
        f.seek(offset)
        return f.read(length)

    def write(self, path, buf, off):
        #print "xmp.py:Xmp:write: %s" % path
        f = open(self.root + path, "r+")
        f.seek(off)
        f.write(buf)
        return len(buf)

    def release(self, path, flags):
        print "xmp.py:Xmp:release: %s %s" % (path, flags)
        return 0

    def statfs(self):
        """
        Should return a tuple with the following 6 elements:
            - blocksize - size of file blocks, in bytes
            - totalblocks - total number of blocks in the filesystem
            - freeblocks - number of free blocks
            - totalfiles - total number of file inodes
            - freefiles - nunber of free file inodes

        Feel free to set any of the above values to 0, which tells
        the kernel that the info is not available.
        """
        print "xmp.py:Xmp:statfs: returning fictitious values"
        blocks_size = 1024
        blocks = 100000
        blocks_free = 25000
        files = 100000
        files_free = 60000
        namelen = 80
        return (blocks_size, blocks, blocks - blocks_free, blocks_free, files, files_free, namelen)

    def fsync(self, path, isfsyncfile):
        print "xmp.py:Xmp:fsync: path=%s, isfsyncfile=%s" % (self.root + path, isfsyncfile)
        return 0

if __name__ == '__main__':

    usage="""
Userspace nullfs-alike: mirror the filesystem tree from some point on.

""" + Fuse.fusage

    server = Xmp(version="%prog " + fuse.__version__,
                 usage=usage),
                 dash_s_do='setsingle')

    server.parser.add_option(mountopt="root", metavar="PATH", default='/', type=str,
                             help="mirror filesystem from under PATH [default: %default]")
    server.parse(values=server, errex=1)

    try:
        os.stat(server.root)
    except OSError:
        print >> sys.stderr, "can't stat root of underlying filesystem"
        sys.exit(1)
     
    server.main()
