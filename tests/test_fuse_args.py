import pytest
import optparse
import os
import sys
from pathlib import Path
import argparse

from fuse import FuseArgs, FuseOptParse, Fuse, FuseError, FUSE_PYTHON_API_VERSION

# Set up fuse_python_api for testing
import fuse
fuse.fuse_python_api = FUSE_PYTHON_API_VERSION


def test_init():
    """FuseArgs initialization"""
    args = FuseArgs()
    assert args.mountpoint is None
    assert args.optlist == set()
    assert args.optdict == {}
    assert args.getmod('showhelp') is False
    assert args.getmod('showversion') is False
    assert args.getmod('foreground') is False

@pytest.mark.parametrize("mod", ['showhelp', 'showversion', 'foreground'])
def test_get_set_mod(mod):
    """FuseArgs modifier handling"""
    args = FuseArgs()
    args.setmod(mod)
    assert args.getmod(mod) is True

    args.unsetmod(mod)
    assert args.getmod(mod) is False

def test_fuse_args_mount_expected():
    """FuseArgs mount_expected method"""
    args = FuseArgs()
    assert args.mount_expected() is True

    args.setmod('showhelp')
    assert args.mount_expected() is False
    args.unsetmod('showhelp')

    args.setmod('showversion')
    assert args.mount_expected() is False
    args.unsetmod('showversion')

def test_fuse_args_add():
    """FuseArgs add method"""
    args = FuseArgs()

    # Test adding simple option
    args.add('debug')
    assert 'debug' in args.optlist

    # Test adding option with value
    args.add('uid=1000')
    assert args.optdict['uid'] == '1000'

    # Test adding option with explicit value
    args.add('gid', '1000')
    assert args.optdict['gid'] == '1000'

    # Test adding False value
    args.add('allow_other', False)
    assert 'allow_other' not in args.optlist
    assert 'allow_other' not in args.optdict

def test_fuse_args_canonify():
    """FuseArgs canonify method"""
    args = FuseArgs()

    # Test converting False values
    args.optdict['allow_other'] = False
    args.canonify()
    assert 'allow_other' not in args.optdict

    # Test converting True values
    args.optdict['debug'] = True
    args.canonify()
    assert True in args.optlist
    assert True not in args.optdict

def test_fuse_args_assemble():
    """FuseArgs assemble method"""
    args = FuseArgs()
    args.mountpoint = '/mnt'
    args.setmod('foreground')
    args.add('debug')
    args.add('uid=1000')

    cmdline = args.assemble()
    # The first argument should be a program name
    assert isinstance(cmdline[0], str)
    assert cmdline[1] == '/mnt'
    assert '-f' in cmdline
    assert cmdline[-1] in ('-odebug,uid=1000', '-ouid=1000,debug')

def test_fuse_cliparse_basic():
    """Basic FuseOptParse functionality"""
    parser = FuseOptParse()
    parser.add_argument('--mountpoint', nargs='?', help='Mount point')
    args = parser.parse_args(['/mnt', '-f', '-o', 'debug,uid=1000'])

    assert parser.fuse_args.mountpoint == '/mnt'
    assert parser.fuse_args.getmod('foreground')
    assert 'debug' in parser.fuse_args.optlist
    assert parser.fuse_args.optdict['uid'] == '1000'

def test_fuse_cliparse_standard_mods():
    """FuseOptParse standard modifiers"""
    parser = FuseOptParse(standard_mods=True)
    parser.add_argument('--mountpoint', nargs='?', help='Mount point')
    args = parser.parse_args(['/mnt', '-f', '-d'])

    assert parser.fuse_args.getmod('foreground')
    assert 'debug' in parser.fuse_args.optlist

def test_fuse_cliparse_dash_s():
    """FuseOptParse -s option handling"""
    # Test whine mode (default)
    parser = FuseOptParse()
    parser.add_argument('--mountpoint', nargs='?', help='Mount point')
    with pytest.raises(FuseError):
        parser.parse_args(['/mnt', '-s'])

    # Test setsingle mode
    mock_fuse = Fuse()
    mock_fuse.multithreaded = True

    parser = FuseOptParse(dash_s_do='setsingle', fuse=mock_fuse)
    parser.add_argument('--mountpoint', nargs='?', help='Mount point')
    args = parser.parse_args(['/mnt', '-s'])
    assert not mock_fuse.multithreaded

def test_fuse_cliparse_error_handling():
    """FuseOptParse error handling"""
    parser = FuseOptParse()
    parser.add_argument('--mountpoint', nargs='?', help='Mount point')

    # Test invalid option
    with pytest.raises(FuseError):
        parser.parse_args(['/mnt', '--invalid-option'])

def test_fuse_cliparse_mount_options():
    """FuseOptParse mount options handling"""
    parser = FuseOptParse()
    parser.add_argument('--mountpoint', nargs='?', help='Mount point')
    args = parser.parse_args(['/mnt', '-o', 'debug,uid=1000,gid=1000'])

    assert 'debug' in parser.fuse_args.optlist
    assert parser.fuse_args.optdict['uid'] == '1000'
    assert parser.fuse_args.optdict['gid'] == '1000'
