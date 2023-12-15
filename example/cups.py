#!/usr/bin/env python

#
# cups.py: a FUSE filesystem for mounting an LDAP directory in Python
# Need python-fuse bindings, and an LDAP server.
# usage: ./cups.py <mountpoint>
# unmount with fusermount -u <mountpoint>
#

import stat
import errno
import fuse
from time import time
from subprocess import Popen, PIPE

fuse.fuse_python_api = (0, 2)


class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = stat.S_IFDIR | 0o755
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 2
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 4096
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0


class CupsFS(fuse.Fuse):
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)

        # Get our list of printers available.
        lpstat = Popen(['lpstat -p'], shell=True, stdout=PIPE)
        output = lpstat.communicate()[0]
        lines = output.split(b'\n')
        lpstat.wait()

        self.printers = {}
        self.files = {}
        self.lastfiles = {}
        for line in lines:
            words = line.split(b' ')
            if len(words) > 2:
                self.printers[words[1]] = []

    def getattr(self, path):
        st = MyStat()
        pe = path.split('/')[1:]

        st.st_atime = int(time())
        st.st_mtime = st.st_atime
        st.st_ctime = st.st_atime
        if path == '/':
            pass
        elif pe[-1] in self.printers:
            pass
        elif pe[-1] in self.lastfiles:
            st.st_mode = stat.S_IFREG | 0o666
            st.st_nlink = 1
            st.st_size = len(self.lastfiles[pe[-1]])
        else:
            return -errno.ENOENT
        return st

    def readdir(self, path, offset):
        dirents = ['.', '..']
        if path == '/':
            dirents.extend(list(self.printers.keys()))
        else:
            dirents.extend(self.printers[path[1:]])
        for r in dirents:
            yield fuse.Direntry(r)

    def mknod(self, path, mode, dev):
        pe = path.split('/')[1:]  # Path elements 0 = printer 1 = file
        self.printers[pe[0]].append(pe[1])
        self.files[pe[1]] = ""
        self.lastfiles[pe[1]] = ""
        return 0

    def unlink(self, path):
        pe = path.split('/')[1:]  # Path elements 0 = printer 1 = file
        self.printers[pe[0]].remove(pe[1])
        del (self.files[pe[1]])
        del (self.lastfiles[pe[1]])
        return 0

    def read(self, path, size, offset):
        pe = path.split('/')[1:]  # Path elements 0 = printer 1 = file
        return self.lastfiles[pe[1]][offset:offset + size]

    def write(self, path, buf, offset):
        pe = path.split('/')[1:]  # Path elements 0 = printer 1 = file
        self.files[pe[1]] += buf
        return len(buf)

    def release(self, path, flags):
        pe = path.split('/')[1:]  # Path elements 0 = printer 1 = file
        if len(self.files[pe[1]]) > 0:
            lpr = Popen(['lpr -P ' + pe[0]], shell=True, stdin=PIPE)
            lpr.communicate(input=self.files[pe[1]])
            lpr.wait()
            self.lastfiles[pe[1]] = self.files[pe[1]]
            self.files[pe[1]] = ""  # Clear out string
        return 0

    def open(self, path, flags):
        return 0

    def truncate(self, path, size):
        return 0

    def utime(self, path, times):
        return 0

    def mkdir(self, path, mode):
        return 0

    def rmdir(self, path):
        return 0

    def rename(self, pathfrom, pathto):
        return 0

    def fsync(self, path, isfsyncfile):
        return 0


def main():
    usage = """
       CupsFS: A filesystem to allow printing for applications that can
               only print to file.
   """ + fuse.Fuse.fusage

    server = CupsFS(version="%prog " + fuse.__version__,
                    usage=usage, dash_s_do='setsingle')
    server.parse(errex=1)
    server.main()


if __name__ == '__main__':
    main()
