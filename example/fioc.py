#!/usr/bin/python

#    Copyright (C) 2016  Cedric CARREE  <beg0@free.fr>
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#
import os, stat, errno, struct

try:
    import _find_fuse_parts
except ImportError:
    pass
import fuse
from fuse import Fuse


if not hasattr(fuse, '__version__'):
    raise RuntimeError("your fuse-py doesn't know of fuse.__version__, probably it's too old.")

fuse.fuse_python_api = (0, 2)

# this mimics asm-generic/ioctl.h  header
# I'm not sure this is really portable, you'd better use ioctl-opt package or something similar
class IOCTL:
	_IOC_NRBITS = 8
	_IOC_TYPEBITS = 8
	_IOC_SIZEBITS = 14
	_IOC_DIRBITS = 2

	_IOC_NRMASK = (1 << _IOC_NRBITS)-1
	_IOC_TYPEMASK = (1 << _IOC_TYPEBITS)-1
	_IOC_SIZEMASK = (1 << _IOC_SIZEBITS)-1
	_IOC_DIRMASK = (1 << _IOC_DIRBITS)-1

	_IOC_NRSHIFT = 0
	_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
	_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
	_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

	_IOC_NONE = 0
	_IOC_WRITE = 1
	_IOC_READ = 2

	@classmethod
	def _IOC(cls, d,t,nr,size):
		return (((d)  << cls._IOC_DIRSHIFT) |
			 ((t) << cls._IOC_TYPESHIFT) | \
			 ((nr)   << cls._IOC_NRSHIFT) | \
			 ((size) << cls._IOC_SIZESHIFT))

	@classmethod
	def _IO(cls, t,nr):
		return cls._IOC(cls._IOC_NONE, t, nr, 0)

	@classmethod
	def _IOR(cls, t,nr,size):
		return cls._IOC(cls._IOC_READ, t, nr, size)

	@classmethod
	def _IOW(cls, t,nr,size):
		return cls._IOC(cls._IOC_WRITE, t, nr, size)

	@classmethod
	def _IOWR(cls,t,nr,size):
		return cls._IOC(cls._IOC_WRITE|cls._IOC_READ, t, nr, size)


# IOCTL (as defined in fioc.h)
# Note: on my system, size_t is an unsigned long
FIOC_GET_SIZE = IOCTL._IOR(ord('E'),0, struct.calcsize("L"));
FIOC_SET_SIZE = IOCTL._IOW(ord('E'),1, struct.calcsize("L"));

# object type
FIOC_NONE = 0
FIOC_ROOT = 1
FIOC_FILE = 2

FIOC_NAME  = "fioc"

class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0


class FiocFS(Fuse):

    def __init__(self, *args, **kw):
        Fuse.__init__(self, *args, **kw)
        self.buf =  b""

    def resize(self, new_size):
        old_size = len(self.buf)
        if new_size == old_size:
            return 0

        if new_size < old_size:
            self.buf = self.buf[0:new_size]
        else:
            self.buf = self.buf + b"\x00" * (new_size - old_size)

        return 0

    def file_type(self, path):
        if not type(path) == str:
            return FIOC_NONE
        if path == "/":
            return FIOC_ROOT
        elif path == "/" + FIOC_NAME:
            return FIOC_FILE
        else:
            return FIOC_NONE

    def getattr(self, path):
        st = MyStat()
        ft = self.file_type(path)
        if ft == FIOC_ROOT:
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 2
        elif ft == FIOC_FILE:
            st.st_mode = stat.S_IFREG | 0o666
            st.st_nlink = 1
            st.st_size = len(self.buf)
        else:
            return -errno.ENOENT
        return st

    def open(self, path, flags):
        if self.file_type(path) != FIOC_NONE:
            return 0

        return -errno.ENOENT

    def do_read(self, path, size, offset):

        if offset >= len(self.buf):
            return 0

        if size > (len(self.buf) - offset):
            size = len(self.buf) - offset

        return self.buf[offset:offset+size]

    def read(self, path, size, offset):
        if self.file_type(path) != FIOC_FILE:
            return -errno.EINVAL;

        return self.do_read(path, size, offset)

    def do_write(self, path, buf, offset):
        self.buf = self.buf[0:offset-1] + buf + self.buf[offset+len(buf)+1:len(self.buf)]
        return len(buf)

    def write(self, path, buf, offset):
        if self.file_type(path) != FIOC_FILE:
            return -errno.EINVAL;

        return self.do_write(path, buf, offset)

    def truncate(self, path, size):
        if self.file_type(path) != FIOC_FILE:
            return -error.EINVAL

        return self.resize(size)

    def readdir(self, path, offset):
        for r in  '.', '..', FIOC_NAME:
            yield fuse.Direntry(r)

    def ioctl(self, path, cmd, arg, flags):
        if cmd == FIOC_GET_SIZE:
            data = struct.pack("L",len(self.buf))
            return data
        elif cmd == FIOC_SET_SIZE:
            (l,) = struct.unpack("L",arg);
            self.resize(l)
            return 0

        return -errno.EINVAL

def main():
    usage="""
Userspace ioctl example

""" + Fuse.fusage
    server = FiocFS(version="%prog " + fuse.__version__,
                     usage=usage,
                     dash_s_do='setsingle')

    server.parse(errex=1)
    server.main()

if __name__ == '__main__':
    main()

