## Simple FUSE Filesystem HOWTO in Python

I've written a few filesystems (k8055fs, ltspfs, etc) using FUSE, and
something I keep seeing on the lists is a request for a tutorial from
people new to FUSE. Here's my stab at one.

### The Problem

Where I work, we access some government functions through a web based
Java 3270 emulator. Recently, the government updated the Java client,
and broke printing, so my users couldn't print out screenshots of
information that they needed. Rather than trying to argue with the
government that they should support my GNU/Linux clients, which would
have gone nowhere, I started trying to come up with an alternative
solution. It seemed that "printing to a text file" still worked fine
within the client. So, all we need to do is just find a way to have
text files automatically spit out on a printer as soon as they're
written. We've got a thin-client environment, so multiple people are
logged onto a server, and there are several printers defined on a
server.

### The Design

We needed the following:

  * To print to any of the printers defined on the server.
  * To have multiple people print to the same printer on the same server
  * Screen prints are small, typically less than 2k of text
  * I needed to get it going quickly

So, it seemed the following would make sense:

  * The filesystem, when mounted, would have a directory for each of the printers on the system
  * Under each of the "printer directories", any file could be created.
  * This file, when closed, would be sent to the printer whose directory it was in.

Seems simple enough. I've done this in Python, since it's fast to get
something going in, and has good FUSE bindings.

So, how will we manage this within Python? Well, having three
dictionaries seemed to make the most sense:

  1. A dictionary with an entry for each of the printers, that
     referenced a list of all the "files" that printer owned.
  2. Two dictionaries of all the files, one that is currently being
     written to, and a shadow one that contains the last file printed
     (in case you want to see the last thing printed for debugging, or
     to re-print it).

So, by way of example, lets say we have 3 printers, babypuss, dino, and
hoparoo. Barney prints to dino, Wilma and Betty print to babypuss, and
Fred prints to hoparoo. So:

     printers = {"dino": [ "barney.txt" ], "babypuss": [ "wilma.txt", "betty.txt" ], "hoparoo": [ "fred.txt" ]}
     files = { "barney.txt": "blahblah...", "wilma.txt": "etcetc...", ...}
     lastfiles = { "barney.txt": "lastblahblah...", "wilma.txt": "lastetcetc...", ...}

Fairly straightforward, and shouldn't take too much to get going.

### Implementation

Usually, when I'm implementing a filesystem using FUSE, the first
three functions

I'll implement will be the *init* to kick things off, *getattr*, so
that the attributes of a file can be passed back, and *readdir*, so I
can "see" the files using `ls`. Once you implement those three
functions, you've at least got a filesystem you can `cd` around
in. We'll flesh it out from there.

#### __init__

So, first thing we're going to need is a list of printers. There's
probably some cups bindings for Python, but `lpstat` will give us what
we need:

       sbalneav@bedrock:~$ lpstat -p
       printer babypuss is idle.  enabled since Fri 27 Jun 2008 10:53:43 AM CDT
       printer dino is idle.  enabled since Mon 14 Jul 2008 11:15:56 AM CDT
       printer hoparoo is idle.  enabled since Tue 08 Jul 2008 05:30:44 PM CDT
       sbalneav@bedrock:~$

So, we'll want to get this list going, and build our printer list in
the *init* function using this output.

First, we'll subclass the Fuse object in the usual manner, and define the *init* function:

       class CupsFS(fuse.Fuse):
       def __init__(self, *args, **kw):
           fuse.Fuse.__init__(self, *args, **kw)

We'll need to get our list of printers. Let's split this out using the subprocess module:

        lpstat = Popen(['lpstat -p'], shell=True, stdout=PIPE)
        output = lpstat.communicate()[0]
        lines = output.split(b'\n');
        lpstat.wait()

And, we'll build our dictionary of *printers*, and the (currently empty) dictionary of *files*, and *lastfiles*:

       self.printers = {}
       self.files = {}
       self.lastfiles = {}
           for line in lines:
               words = line.split(b' ')
               if len(words) > 2:
                   self.printers[words[1]] = []  # the second word on the line is the printer name

#### getattr

Next, we'll need to make up some attributes. Since this is a "fake"
filesystem (i.e. it isn't really storing real file objects), we can be
a little "loosey goosey" with the file attributes. Let's have all files
owned by root, with the directories' mode 0755, and files 0666, so we
won't have to worry about access problems.

So, first off, we'll need a separate class to return the status
object. Fortunately, the Python fuse bindings give us one we can
subclass:

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


The inode and dev numbers we can ignore, as FUSE will handle those for
us. We'll make the default status object be a directory, so we set the
number of links to two (all directories have at least 2 links, itself,
and the link back to ...) and a size of 4096, which is usually the
"default" directory size. The access, modify, and change times are set
to zero for now.

As well, we'll need to provide the *getattr* function in the CupsFS object itself:

       def getattr(self, path):
           st = MyStat()
           pe = path.split('/')[1:]

           st.st_atime = int(time())
           st.st_mtime = st.st_atime
           st.st_ctime = st.st_atime


So, we'll create a stat object, and split out our path we're handed on
the '/' character, and set the access, modification, and change time
to be "now". But why split up the path elements?

Well, for our little filesystem, we're either going to be handed paths
like `/` for the root, `/printer` to look at the printer directory, or
`/printer/file` to get attributes for one of the files, so, by
breaking them into path elements:

       >>> path = "/dino/barney.txt"
       >>> path.split('/')[1:]
       ['dino', 'barney.txt']
       >>>

We'll be able to look at the last element (`pe[-1]`), and see if it's
either a printer, or a file. And that's what we'll do next:

        if path == '/':                         # root
            pass
        elif pe[-1] in self.printers:           # a printer
            pass
        elif pe[-1] in self.lastfiles:          # a file
            st.st_mode = stat.S_IFREG | o0666
            st.st_nlink = 1
            st.st_size = len(self.lastfiles[pe[-1]]
        else:
            return -errno.ENOENT
        return st


So, if the path is '/' (the root), or, we can find the last path
element in the *printers* dictionary (i.e. '/dino'), then we don't
have to do anything, since we defaulted the status object above to be
a directory.

If, however, it's in the *lastfiles* dictionary, then we set the mode
of the file with the all important `stat.S_IFREG`, which will mark
this entry as a "regular" file, and give it mode 0666 (-rw-rw-rw). As
well, we drop the link count to 1 (regular files that don't have hard
links to them only have a link count of one), and set the size to the
size of the string stored in *lastfiles*. If the file was simply
created, via, say, the "touch" command, the *lastfiles* string will be
zero length, and we'll get the expected return value. However, if
we've written to a file, we'll get the size, as we'd expect if we do
an `ls` in the printer directory.

If it didn't satisfy one of the three conditions ('/', '/printer',
'/printer/file') we return `-errno.ENOENT` so we'll get the expected
"no such file or directory" error if we try to access something that
isn't there.

So much for our simple getattr! On to readdir!

#### readdir

If we're in the root directory of our filesystem, we'd like to see the list of printers:

       sbalneav@bedrock:/printer$ ls -la
       total 40K
       drwxr-xr-x  2 root root 4.0K 2008-07-16 13:21 .
       drwxr-xr-x 23 root root 4.0K 2008-07-15 15:44 ..
       drwxr-xr-x  2 root root 4.0K 2008-07-16 13:21 babypuss
       drwxr-xr-x  2 root root 4.0K 2008-07-16 13:21 dino
       drwxr-xr-x  2 root root 4.0K 2008-07-16 13:21 hoparoo
       sbalneav@bedrock:/printer$

And, if we're in a printer directory, we'd like to see the list of files:

       sbalneav@bedrock:/printer/babypuss$ ls -la
       total 8.0K
       drwxr-xr-x 2 root root 4.0K 2008-07-16 13:24 .
       drwxr-xr-x 2 root root 4.0K 2008-07-16 13:24 ..
       -rw-rw-rw- 1 root root    0 2008-07-16 13:24 betty.txt
       -rw-rw-rw- 1 root root    0 2008-07-16 13:24 wilma.txt
       sbalneav@bedrock:/printer/babypuss$

FUSE requires that you return the standard '.' and '..' files, plus
the list of files you want to display. If we're in the root, we want
to return the list of keys that's in our *printers* dictionary, and if
we're in a printer directory, we want to return the list of files
that's associated with that printer key.

Since each key in the *printers* dictionary has a list of the files
associated with it, this is fairly simple:

       def readdir(self, path, offset):
           dirents = [ '.', '..' ]
           if path == '/':
               dirents.extend(list(self.printers.keys()))
           else:
               # Note use of path[1:] to strip the leading '/'
               # from the path, so we just get the printer name
               dirents.extend(self.printers[path[1:]])
           for r in dirents:
               yield fuse.Direntry(r)

So, we start off with the list containing the '.' and '..' directory
entries, and then check to see if we're in the root. If we are, we
just add the list of keys by calling the *.keys()* method of the
*printers* dictionary, and if not, we add the list associated with the
path we've been given.

That's it. We should have a filesystem that we're able to cd around
in. The full program's listed at the end of the page.

#### mknod

Well, we've got a boring filesystem that just has a few directories
corresponding to printers on the system. Now we want to be able to
create files, so we can print them! For that, we'll have to implement
the mknod call.

Since we're not doing anything fancy with our filesystem, like making
pipes, or /dev nodes, etc., we don't have to worry about examining the
*mode* and *dev* parameters we're passed. If you were trying to
implement something more complicated, you would, but since this is a
simple example, and a quick tutorial, we'll gloss over that. All *we*
need to do, to add a file for printing, is to add the filename to the
printer entry in the *printers* dictionary, and create a new empty
string entry in the *files* and *lastfiles* dictionaries for that
file.

        def mknod(self, path, mode, dev):
            pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
            self.printers[pe[0]].append(pe[1])
            self.files[pe[1]] = ""
            self.lastfiles[pe[1]] = ""
            return 0

So, once again, we split up the path elements to get the printer name
and filename easily. We then append the filename to the list of files
associated with that printer, and add the empty string dictionary
entries for the file.

So, when we start up the filesystem, there won't be any files under
the printers, but if we do a:

    sbalneav@bedrock$ touch /printers/babypuss/wilma.txt

the *mknod* function will be called, and we'll add the entry to the
*printers*, *files*, and *lastfiles* dictionaries, so that doing an

    ls

will now list

    wilma.txt

in the right place.

#### unlink

For debugging purposes when trying to solve printer problems, it might
be handy to be able to "remove" the file, so we can see if the
application that's printing to the file is recreating the "print job"
when it's supposed to. So,

let's implement the unlink function, so we can do a

    rm wilma.txt

This is almost the exact opposite of the mknod. Now, we just want to
remove the filename from the list associated with the printer, and
delete the dictionary entries in the *files* and *lastfiles*
dictionaries:

        def unlink(self, path):
            pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
            self.printers[pe[0]].remove(pe[1])
            del(self.files[pe[1]])
            del(self.lastfiles[pe[1]])
            return 0

Simple.

#### write

OK, meat and potatoes time. Although, for our little example here, a
surprisingly small slice of meat! When FUSE calls the *write*
function, you're passed the path, data buffer, and offset within the
file to write the data to.

Since we're just handling files that are 1) small and 2) linear, we
don't have to worry about the offset! In a real filesystem you would,
for say, doing random access reads and writes to a database file. But
for our little "text print" filesystem, we can just concatenate any
data we receive to the dictionary entry associated with the filename
in the *files* dictionary.

        def write(self, path, buf, offset):
            pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
            self.files[pe[1]] += buf
            return len(buf)

the length of the buffer. The *write* system call expects you to
return the *actual* amount of data read or written, so if you have a
short write, the kernel can handle it appropriately. We won't worry
about that for our little application.

#### read

Reading's even simpler. We're just going to read from the *lastfiles*
dictionary we're maintaining. We're passed a size and offset of the
chunk to read, so all we need to do is take a string slice from the
*lastfiles* dictionary.

        def read(self, path, size, offset):
            pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
            return self.lastfiles[pe[1]][offset:offset+size]

So, all that remains is: how do we actually print the data?

#### release

Nothing causes beginning FUSE filesystems authors more problems than
how to handle the close() of a file. For reasons that are outlined in
the FUSE FAQ, there *IS* no *close* function, but rather the *flush*
and *release*functions, the semantics of which are tricky for some
files (devices, pipes, mmap()'d files, etc.). However, for *OUR*
little example, we'll get one call to *release* when the text file's
closed for writing, so we'll use that to be our signal to print the
file.

All we want to do is check and see if the string length in the *files*
dictionary is greater than zero. If it is, then we've written to the
file, so we want to print out the text. However, if it isn't, we've
gotten the release call from an open for reading. In that case, we'll
just ignore it.

Once we get a release of the filename, all we want to do is pipe the
text associated with the file to the *lpr* command. We know what
printer to print to by the directory we're in. Once the file's
printed, we just want to save the current text in the *lastfiles*
dictionary (so it can be read later, by the "read" call) and zero out
the text that's been built up in the *files* dictionary, so that every
print job does what you'd expect. If we didn't do that, every time
you'd print onto that file, you'd get all the previous print jobs out
as well.

Once again, we'll use the subprocess module to pipe our data to lpr:

        def release(self, path, flags):
            pe = path.split('/')[1:]        # Path elements 0 = printer 1 = file
            if len(self.files[pe[1]]) > 0:
                lpr = Popen(['lpr -P ' + pe[0]], shell=True, stdin=PIPE)
                lpr.communicate(input=self.files[pe[1]])
                lpr.wait()
                self.lastfiles[pe[1]] = self.files[pe[1]]
                self.files[pe[1]] = ""          # Clear out string
            return 0

The only fancy footwork is passing the string we've built up to the
input of *lpr* via the *communicate* call.

#### The rest

As you'll see in the full listing below, we stub out the rest of the
filesystem calls, just so they don't return "function not implemented"
errors.

### Conclusion

As you can see, it's pretty easy to throw together a FUSE filesystem
that accomplishes a useful, non-trivial task in a relatively few lines
of code. FUSE is a lot of fun to write filesystems with, and it's
really nice tool to be able to solve problems that would otherwise be
messy or impossible.

Have fun, and enjoy

### Listing of cups.py

- [cups.py](example/cups.py)
