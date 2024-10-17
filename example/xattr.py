# Example by github @vignedev from https://github.com/libfuse/python-fuse/issues/77

import fuse
import stat, errno
from fuse import Fuse, Stat, Direntry

fuse.fuse_python_api = (0, 2)

BROKEN_FILE = '/utf8_attr'
FATTR_NAME = 'user.xdg.comment'
FATTR_VALUE = 'ああ、メッセージは切り取られていない'

class EmptyStat(Stat):
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

class GetAttrBug(Fuse):
  def getattr(self, path):
    ret_stat = EmptyStat()
    if path == '/':
      ret_stat.st_mode = stat.S_IFDIR | int(0e755)
      return ret_stat

    if path == BROKEN_FILE:
      ret_stat.st_mode = stat.S_IFREG | int(0e000)
      return ret_stat
    
    return -errno.ENOENT

  def readdir(self, path, offset):
    yield Direntry('.')
    yield Direntry('..')
    yield Direntry(BROKEN_FILE[1:])

  def open(self, path, flags):
    return -errno.EACCES

  def read(self, path, size, offset):
    return

  def listxattr(self, path, size):
    if size == 0: return 1
    else: return [ FATTR_NAME ]

  def getxattr(self, path, attr, size):
    if size == 0: return len(FATTR_VALUE.encode('utf8'))
    else: return FATTR_VALUE

if __name__ == '__main__':
  server = GetAttrBug(dash_s_do='setsingle')
  server.parse(errex=1)
  server.main()
