import os
import time
import sys
import struct
import subprocess
import pathlib
import tempfile
import pytest
import fcntl

topdir = pathlib.Path(__file__).parent.parent

@pytest.fixture
def filesystem(request):
    fstype = request.node.get_closest_marker("fstype").args[0]

    with tempfile.TemporaryDirectory() as tmpdir:
        st_dev = os.stat(tmpdir).st_dev
        proc = subprocess.Popen([sys.executable, "-d", topdir / "example" / f"{fstype}.py", tmpdir], stdin=subprocess.DEVNULL)

        deadline = time.time() + 1
        while time.time() < deadline:
            new_st_dev = os.stat(tmpdir).st_dev
            if new_st_dev != st_dev:
                break
            time.sleep(.01)
        if new_st_dev == st_dev:
            proc.terminate()
            raise RuntimeError("Filesystem did not mount within 1s")


        yield pathlib.Path(tmpdir)

        subprocess.call(["fusermount", "-u", "-q", "-z", tmpdir])

        deadline = time.time() + 1
        while time.time() < deadline:
            result = proc.poll()
            if result is not None:
                if result != 0:
                    raise RuntimeError("Filesystem exited with an error: {result}")
                return
            time.sleep(.01)

        proc.terminate()
        raise RuntimeError("Filesystem failed to exit within 1s after unmount")

@pytest.mark.fstype("hello")
def test_hello(filesystem):
    content = (filesystem / "hello").read_text(encoding="utf-8")
    assert content == "Hello World!\n"

@pytest.mark.fstype("fioc")
def test_fioc(filesystem):
    FIOC_GET_SIZE, FIOC_SET_SIZE = 0x80084500, 0x40084501
    with (filesystem / "fioc").open("rb") as f:
        b = struct.pack("L", 42)
        fcntl.ioctl(f.fileno(), FIOC_SET_SIZE, b)

        b = bytearray(struct.calcsize('l'))
        fcntl.ioctl(f.fileno(), FIOC_GET_SIZE, b)
        assert struct.unpack("L", b)[0] == 42

@pytest.mark.fstype("xattr")
def test_xattr(filesystem):
    assert os.getxattr(filesystem / "utf8_attr", "user.xdg.comment").decode("utf-8") == 'ああ、メッセージは切り取られていない'
