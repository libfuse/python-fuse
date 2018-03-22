=============================
FUSE-Python_ bindings new API
=============================

.. _FUSE-Python: https://github.com/libfuse/python-fuse

:Author: Csaba Henk

I've made several changes on the FUSE Python interface as we knew it.
We will review here how this effects the usage of the module -- both
from the end user and the developer POV.

*This is not a reference.* This document just wants to show the big
picture.  If you want to write code using this module, then read this
document first, and then take a look at the example filesystems under
``example/`` (``example/xmp.py`` is a pretty complete demo of the usage
of the FUSE binding). For the rest, you can get away with the usual
resources like in-code documentation (ie., docstrings) and the code
itself.


.. contents::


Old API
===================


Enforcing compatibility
-----------------------

There are lot of existing Python based FUSE based filesystems out there.
They won't work with the current fuse-py code as is; however, we'd like
to keep on using them. What can we do?

Easy it is: just set ``fuse.fuse_python_api`` to ``(0, 1)`` before you invoke
your filesystem. This can be achieved externally too, by setting the
``FUSE_PYTHON_API`` environment variable to ``0.1``. [#]_ [#]_

.. [#] Setting ``fuse.compat_0_1`` to ``True`` or having
   ``FUSE_PYTHON_COMPAT = 0.1`` in the environment still works,
   but it's deprecated.

.. [#] Cf. `Long-term compatibility`_.


What's incompatible, anyway?
----------------------------

- ``Fuse`` instance initialization

- Handling of command line options

- Transferring structured system data (file/filesystem attributes, directory
  entries) to the FUSE library

- `getdir` fs method ditched in favor of `readdir`

That is, to upgrade your filesystem to the new API, you will have to
rewrite:

- all your code between instantiating ``Fuse`` and calling the
  ``main()`` method of the instance (and the ``__init__()``, ``main()``
  methods of your ``Fuse`` derived class, if you have overwritten the
  original)

- the following fs methods: `getattr`, `statfs`, `getdir`.


New API
=======

The basic layout is the same: to start with, you get a class,
``fuse.Fuse``. You implement a filesystem by subclassing this class and
add the filesystem as class methods. You can mount your filesystem class
by calling the ``main()`` method of one of its instances.  The list of
possible filesystem methods is available as ``fuse.Fuse._attrs``. [#]_

So what's new? The new API has put emphasis on the following themes:

- FUSE is a command line driven library. Handling ``sys.argv`` and
  the FUSE command line should be integrated.

- Object based interface to system structures.

- Wrap stateful I/O in OO.

- Add support for all FUSE features which are available at the level
  the library is interfaced (the *high-level interface*).

- Reflection.

Let's see how these are implemented.

.. [#] See ``examples/xmp.py`` for the argument list of the fs methods.

   Regarding return values: in each method, you can signal success or
   error by returning ``0`` (*succes*), a negative number (*error*,
   interpreted as negated errno), not returning anything (*success*) or
   by raising (not catching) an exception (*error*, Python infers an
   errno from the nature of the exception).

   For most methods this just does the job (eg., you don't need to pass
   back anything after handling an `mkdir` request, only success/error).
   Some others require data being passed on from your handler to FUSE
   (eg., `read`, `getattr`). Then just return with a suitable object (a
   string for `read`, a stat result alike for `getattr`, cf.  `Simple
   objects to represent system structures`_).  If the object is not
   suitable, then FUSE will signal an EINVAL to the system; you won't
   get feedback about it. (The badness shows up in FUSE's inner context,
   out of Python's, so raising an exception makes no sense. We could
   wrap some fs methods into format valifiers; currently we don't do
   that.)
   

FUSE and the command line
-------------------------

Crudely there can be two ways to provide configuration hooks to some
C library:

- One is having a config structure as a part of the API, which is to be
  filled and pass to some constructor or initializator when you start
  interfacing with the library. Such an interface can be easily used
  from C, but it is very fragile wrt. changing the config options.

- Other is to use some kind of markup or domain specific language
  (*DSL*). This is flexible, but there should be provided a
  parser/generator for this language to be possible to make use of it.

FUSE chose the latter way. Instead of using XML or some other widely
used config format, FUSE made a simple decision: let the command line be
our DSL -- we have to grok the command line anyway. [#]_

So, there are two command lines in the game. One is the actual command
line (``sys.argv``), the other is the FUSE command line: the library can
be initialized with an ``(argc, argv)`` pair.

This makes the library user to want urgently:

- A way to easily generate a FUSE compatible command line from an abstract
  spec.

- A way to easily extract such an abstract spec from the actual command
  line.

(... and these two procedures should interfere *only via the spec*.)

The new API does this as follows:

- Now it's the Python code's duty to put together a complete FUSE command line
  (in the form of a Python sequence). [#]_

- ``FuseArgs`` is the class for the abstract specification: the
  ``mountpoint``, ``set_mod()``, and ``add()`` attributes/methods enable
  you to set up such a beast; ``assemble()`` dumps a complete FUSE
  command line.

- ``Fuse`` got a ``parser`` attribute. It's an instance of
  ``FuseOptParse``, which is derived from the ``OptionParser`` class of
  optparse_. [#]_

  ``FuseOptParse`` groks a new kind of option (a subclass of
  ``Option``), which takes no short or long opts; it matches or not
  based on its ``mountopt`` attribute, which is looked for among the
  comma-separated members of a ``-o`` option.

  You can specify handlers these mountopts, just like to ordinary
  options. The unhandled suboptions are collected in a ``FuseArgs``
  instance.

- Calling ``Fuse``'s ``parse()`` method performs the parsing, and makes
  a note of the resulting ``FuseArgs`` instance. When you invoke
  ``Fuse``'s ``main()``, the FUSE command line will be inferred from
  this instance.

.. [#] Originally this idea seemed as simple as there was no dedicated
   parser/generator interface provided with the library. With FUSE 2.5 we
   finally got the ``fuse_opt`` subAPI to make the command line more
   accessible. That's for C programming, so we don't deal with it here.

.. _optparse: http://docs.python.org/lib/module-optparse.html

.. [#] It wasn't like so: in earlier versions, Python passed down several
   partially parsed pieces of the FUSE command line to the C code, which
   used these directly in low level functions of the library, getting behind
   the main commandline parsing routine of the FUSE lib with no real reason.

.. [#] To be precise, we have the ``SubbedOptParse`` subclass of
   ``OptionParser`` and ``FuseOptParse`` is further derived from
   ``SubbedOptParse``. ``SubbedOptParse`` is a generic class for
   parsing and handling suboptions.


Simple objects to represent system structures
---------------------------------------------

In old Pythons, ``os.stat()`` returned file attributes as a tuple, and
for the convenient access of the stat values, you got a bunch of
constats with it (so you queried file size like
``os.stat("foofile")[stat.ST_SIZE]``). While this approach still works,
and if you print a stat result, it looks like a tuple, *it is, in fact,
not a tuple*. It's an object which is immutable and provides the
sequence protocol, just like tuple, but it has direct stat field
accessors. That is, you can do it now like
``os.stat("foofile").st_size``.

The same is the case with the FUSE bindings: for `getattr`, you are to
return an object which has attributes like those of an ``os.stat()``
result, and for `statfs`, you are to return an object which has
attributes like those of an ``os.statvfs()`` result. This, of course, can
be achieved by calling ``os.stat()``, resp. ``os.statvfs()`` and passing
on the result of this call. But you might feel like starting from
scratch. You can build on the ``fuse.Stat`` and ``fuse.StatVfs``
classes. Subclass and/or instantiate them and specify the stat/statvfs
attributes.

Similarly, when listing directories, you have to return a sequence of
``fuse.Direntry`` objects which can be constructed from filenames
(``fuse.Direntry("foofile")``).

Does the above senctence make sense? I hope so. Anyway, *it's not true
as is*. (Truth has been sacrified for making it short.) Don't worry, we
uncover the lies immediately:

- *You don't necessarily have to return a sequence*. You just have to
  return an object which implements the *iterator protocol*. In
  practice, this means that you can *yield* the direntries one by one,
  instead of aggregating them into a sequence.

- The direntries don't have to be instances of ``fuse.Direntry``, they
  are just required to have some attributes. The ones other than
  ``name`` are probably not interesting for you. If you have large
  directories, you might want to specify a unique ``offset`` value for
  the direntries. This makes it possible for the system to read your dir
  in several chunks, and in each turn, reading can be continued from
  where it has been put off (for this to work, you have to be able to
  decode an ``offset`` and find the direntry which it belongs to).


Filehandles can also be objects if you want
-------------------------------------------

The FUSE library (and the Python new API) supports stateful I/O. That
is, when you open a file, you can choose return an arbitrary object, a
so called *filehandle*. [#]_ FUSE internally will allocate a (FUSE)
filehandle upon open, and keep a record of your (Python) filehandle.
When the system will want to use the FUSE filehandle for I/O, the
respective Python method will get the (py-)filehandle as an argument.
Ie., you can use the filehandle to preserve a state.

You might as well want the filehandle to be an instance of a dedicated
class, and want the filesystem methods get delegated to the filehandle.

The new API can arrange this for you: set up a class, say ``Myfile``,
which implements the I/O related methods (`read`, `write`, ...), and set
``foose.file_class = Myfile`` before calling ``foose.main()`` (where
``foose`` is an instance of ``Fuse``). This will also imply that the
`open` fs method will be handled by instantiating ``Myfile``. Also note
that the *path* argument will be stripped upon delegation (except for
init time).

You can do the same for directories, too. Directory I/O methods have
similar names to file ones, just postfixed with `dir` (like `readdir`),
and there are not that many of them (there is no `writedir`). You can
register a directory class by setting the ``dir_class`` ``Fuse``
attribute. I bet you don't wanna use this feature, though.

Another use of filehandles is that they can be used for adjusting some FUSE
tunables *filewise*. That is, if you return a  py-filehandle object so that it
has a ``keep_cache`` or ``direct_io`` attribute of value ``True``, then the
respective option will be enabled for the given file by FUSE [#]_. As a special
case, if the returned py-filehandle is an instance of ``fuse.FuseFileInfo``, it
will be used for nothing else apart from testing the ``keep_cache`` /
``direct_io`` attributes (after which it will be disposed).

.. [#] although it should not be an integer, as integers are treated as
   error values

.. [#] See the meaning of these options eg.  in standard FUSE help message,
   which you can read by, eg., running ``example/xmp.py -h`` from the root of
   the FUSE Python bindings source tree.

Complete support for hi-lib
---------------------------

The Python bindings support all highlevel (pathname based) methods of
the Fuse library as of API revision 26, including `create`, `access`,
`flush`, extended attributes, advisory file locking, nanosec precise
setting of acces/modify times, and `bmap`.


Reflection
----------

In order to use the stateful I/O features as described above, the FUSE
library on your system has to be recent enough. It's very likely that it
will be so, as stateful I/O is around since a while, but if not... let's
try proactively prevent cryptic bug reports.

Therefore there is ``fuse.feature_assert()`` at your disposal. While
there are several possible features you can assert, the form you will
most likely use is ``feature_assert("stateful_files")``. This will raise
an exception if stateful I/O on files is not supported.

When it comes to reflection, we see that the command line based FUSE
config machinery is sadly unidirectional [#]_. There is no simple way
for querying the option list recognized by the lib. The best we have is
that we can dump a help message. The new Python API tries to make use of
this: it can mangle the help output into an instance of the
aforementioned ``FuseArgs`` class (``Fuse.fuseoptref()``). The most
convenient way to use this as follows: take a ``FuseArgs`` instance, eg.
as its yielded by parsing with ``FuseOptParse``, and call its
``filter()`` method. This returns a new ``FuseArgs`` with the *rejected*
options (which are not understood by the lib, according to the help
message), and also purges out these from self, so the remainder can be
safely passed down to FUSE.

.. [#] We can argue that it's not that sad. We just pass on to FUSE 
   what we get from the user and that either eats it or blows up. Why
   would we want more sophistication?


Long-term compatibility
-----------------------

Your filesystem is expected to set ``fuse.fuse_python_api`` in order to
make it easy for the fuse module to find out the which FUSE-Python API revision
is appropriate for your code. Concretely, set ``fuse.fuse_python_api``
to the value of ``fuse.FUSE_PYTHON_API_VERSION`` as it's definied in the fuse.pyi
instance you code your filesystem against. This ensures that your code will
keep working even if further API revisions take place.
