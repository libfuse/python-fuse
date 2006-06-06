/*
    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>

    This program can be distributed under the terms of the GNU LGPL.
    See the file COPYING.

    Updated for libfuse API changes
    2004 Steven James <pyro@linuxlabs.com> and
    Linux Labs International, Inc. http://www.linuxlabs.com

    Copyright (C) 2006  Csaba Henk  <csaba.henk@creo.hu> 
*/

#ifndef FUSE_VERSION
#ifndef FUSE_MAKE_VERSION
#define FUSE_MAKE_VERSION(maj, min)  ((maj) * 10 + (min))
#endif
#define FUSE_VERSION FUSE_MAKE_VERSION(FUSE_MAJOR_VERSION, FUSE_MINOR_VERSION)
#endif

#define FUSE_USE_VERSION 26

#include <sys/types.h>
#include <sys/param.h>
#include <sys/mount.h>
#include <stdint.h>
#include <time.h>
#include <Python.h>
#include "fuse.h"

static PyObject *getattr_cb=NULL, *readlink_cb=NULL, *readdir_cb=NULL,
  *mknod_cb=NULL, *mkdir_cb=NULL, *unlink_cb=NULL, *rmdir_cb=NULL,
  *symlink_cb=NULL, *rename_cb=NULL, *link_cb=NULL, *chmod_cb=NULL,
  *chown_cb=NULL, *truncate_cb=NULL, *utime_cb=NULL,
  *open_cb=NULL, *read_cb=NULL, *write_cb=NULL, *release_cb=NULL,
  *statfs_cb=NULL, *fsync_cb=NULL, *create_cb=NULL, *opendir_cb=NULL,
  *releasedir_cb=NULL, *fsyncdir_cb=NULL, *flush_cb=NULL, *ftruncate_cb=NULL,
  *fgetattr_cb=NULL, *getxattr_cb=NULL, *listxattr_cb=NULL, *setxattr_cb=NULL,
  *removexattr_cb=NULL, *access_cb=NULL;

static PyObject *Py_FuseError;

#define PROLOGUE		\
int ret = -EINVAL;		\
				\
if (!v) {			\
	PyErr_Print();		\
	goto OUT;		\
}				\
if (v == Py_None) {		\
	ret = 0;		\
	goto OUT_DECREF;	\
}				\
if (PyInt_Check(v)) {		\
	ret = PyInt_AsLong(v);	\
	goto OUT_DECREF;	\
}

#define EPILOGUE		\
OUT_DECREF:			\
	Py_DECREF(v);		\
OUT:				\
	return ret;

#if FUSE_VERSION >= 22
static __inline PyObject *
fi_to_py(struct fuse_file_info *fi)
{
	return (PyObject *)(uintptr_t)fi->fh;
}

#define PYO_CALLWITHFI(fi, fnc, fmt, ...)				      \
	fi_to_py(fi) ?							      \
	PyObject_CallFunction(fnc, #fmt "O", ## __VA_ARGS__, fi_to_py(fi)) :  \
	PyObject_CallFunction(fnc, #fmt, ## __VA_ARGS__)
#else
#define PYO_CALLWITHFI(fi, fnc, fmt, ...)				      \
	PyObject_CallFunction(fnc, #fmt, ## __VA_ARGS__)
#endif /* FUSE_VERSION >= 22 */


#define fetchattr_nam(st, attr, aname)					\
	if (!(tmp = PyObject_GetAttrString(v, aname)))			\
		goto OUT_DECREF;					\
	if (!(PyInt_Check(tmp) || PyLong_Check(tmp))) {			\
		Py_DECREF(tmp);						\
		goto OUT_DECREF;					\
	}								\
	(st)->attr =  PyInt_Check(tmp) ? PyInt_AsLong(tmp) :		\
		      (PyLong_Check(tmp) ? PyLong_AsLong(tmp) : 0);	\
	Py_DECREF(tmp);

#define fetchattr(st, attr)						\
	fetchattr_nam(st, attr, #attr)

/* 
 * Local Variables:
 * indent-tabs-mode: t
 * c-basic-offset: 8
 * End:
 * Changed by David McNab (david@rebirthing.co.nz) to work with recent pythons.
 * Namely, replacing PyTuple_* with PySequence_*, and checking numerical values
 * with both PyInt_Check and PyLong_Check.
 */

static int
getattr_backend(struct stat *st, PyObject *v)
{
	PyObject *tmp;

	PROLOGUE

	fetchattr(st, st_mode);
	fetchattr(st, st_ino);
	fetchattr(st, st_dev);
	fetchattr(st, st_nlink);
	fetchattr(st, st_uid);
	fetchattr(st, st_gid);
	fetchattr(st, st_size);
	fetchattr(st, st_atime);
	fetchattr(st, st_mtime);
	fetchattr(st, st_ctime);

#define fetchattr_soft(st, attr)				\
	tmp = PyObject_GetAttrString(v, #attr);			\
        if (tmp == Py_None) {					\
		Py_DECREF(tmp);					\
		tmp = NULL;					\
	}							\
	if (tmp) {						\
		if (!(PyInt_Check(tmp) || PyLong_Check(tmp))) {	\
			Py_DECREF(tmp);				\
			goto OUT_DECREF;			\
		}						\
		(st)->attr =  PyInt_AsLong(tmp);		\
		Py_DECREF(tmp);					\
	}

#define fetchattr_soft_d(st, attr, defa)			\
	fetchattr_soft(st, attr) else st->attr = defa

	/*
	 * XXX Following fields are not necessarily available on all platforms
	 * (were "all" stands for "POSIX-like"). Therefore we should have some
	 * #ifdef-s around... However, they _are_ available on those platforms
	 * where FUSE has a chance to run now and in the foreseeable future,
	 * and we don't use autotools so we just dare to throw these in as is. 
	 */

	fetchattr_soft(st, st_rdev);
	fetchattr_soft_d(st, st_blksize, 4096);
	fetchattr_soft_d(st, st_blocks, (st->st_size + 511)/512);

#undef fetchattr_soft
#undef fetchattr_soft_d

	ret = 0;

	EPILOGUE
}

static int
getattr_func(const char *path, struct stat *st)
{
	PyObject *v = PyObject_CallFunction(getattr_cb, "s", path);

	return getattr_backend(st, v);
}

#if FUSE_VERSION >= 25
static int
fgetattr_func(const char *path, struct stat *st, struct fuse_file_info *fi)
{
	PyObject *v = PYO_CALLWITHFI(fi, fgetattr_cb, s, path);

	return getattr_backend(st, v);
}
#endif

static int
readlink_func(const char *path, char *link, size_t size)
{
	PyObject *v = PyObject_CallFunction(readlink_cb, "s", path);
	char *s;

	PROLOGUE

	if(!PyString_Check(v)) {
		ret = -EINVAL;
		goto OUT_DECREF;
	}
	s = PyString_AsString(v);
	strncpy(link, s, size);
	link[size-1] = '\0';
	ret = 0;

	EPILOGUE
}

#if FUSE_VERSION >= 23
static int
opendir_func(const char *path, struct fuse_file_info *fi)
{
	PyObject *v = PyObject_CallFunction(opendir_cb, "s", path);
	PROLOGUE

	fi->fh = (uintptr_t) v;

	return 0;

	EPILOGUE
}

static int
releasedir_func(const char *path, struct fuse_file_info *fi)
{
	PyObject *v = fi_to_py(fi) ?
  	              PyObject_CallFunction(releasedir_cb, "sN", path,
	                                    fi_to_py(fi)) :
		      PyObject_CallFunction(releasedir_cb, "s", path);

	PROLOGUE

	EPILOGUE
}

static int
fsyncdir_func(const char *path, int datasync, struct fuse_file_info *fi)
{
	PyObject *v = PYO_CALLWITHFI(fi, fsyncdir_cb, si, path, datasync);

	PROLOGUE
	EPILOGUE
}

static __inline int
dir_add_entry(PyObject *v, void *buf, fuse_fill_dir_t df)
#else
static __inline int
dir_add_entry(PyObject *v, fuse_dirh_t buf, fuse_dirfil_t df)
#endif
{
	PyObject *tmp;
	int ret = -EINVAL;
	struct stat st;
	struct { off_t offset; } offs;

	memset(&st, 0, sizeof(st));
	fetchattr_nam(&st, st_ino, "ino");
	fetchattr_nam(&st, st_mode, "type");
	fetchattr(&offs, offset);

	if (!(tmp = PyObject_GetAttrString(v, "name"))) 
		goto OUT_DECREF;		       
	if (!PyString_Check(tmp)) {
		Py_DECREF(tmp);
		goto OUT_DECREF;		       
	}					       

#if FUSE_VERSION >= 23
	ret = df(buf, PyString_AsString(tmp), &st, offs.offset);
#elif FUSE_VERSION >= 21
	ret = df(buf, PyString_AsString(tmp), (st.st_mode & 0170000) >> 12,
                 st.st_ino);
#else
	ret = df(buf, PyString_AsString(tmp), (st.st_mode & 0170000) >> 12);
#endif
	Py_DECREF(tmp);

OUT_DECREF:
	Py_DECREF(v);

	return ret;
}

#if FUSE_VERSION >= 23
static int
readdir_func(const char *path, void *buf, fuse_fill_dir_t df, off_t off,
             struct fuse_file_info *fi)
{
	PyObject *v = PYO_CALLWITHFI(fi, readdir_cb, sK, path, off);
#else
static int
readdir_func(const char *path, fuse_dirh_t buf, fuse_dirfil_t df)
{
	PyObject *v = PyObject_CallFunction(readdir_cb, "sK", path);
#endif
	PyObject *iter, *w;

	PROLOGUE

	iter = PyObject_GetIter(v);
	if(!iter) {
		PyErr_Print();
		goto OUT_DECREF;
	}

	while ((w = PyIter_Next(iter))) {
		if (dir_add_entry(w, buf, df))
			break;
	}

	Py_DECREF(iter);
	if (PyErr_Occurred()) {
		PyErr_Print();
		goto OUT_DECREF;
	}
	ret = 0;

	EPILOGUE
}

static int
mknod_func(const char *path, mode_t m, dev_t d)
{
	PyObject *v = PyObject_CallFunction(mknod_cb, "sii", path, m, d);

	PROLOGUE
	EPILOGUE
}

static int
mkdir_func(const char *path, mode_t m)
{
	PyObject *v = PyObject_CallFunction(mkdir_cb, "si", path, m);

	PROLOGUE
	EPILOGUE
}

static int
unlink_func(const char *path)
{
	PyObject *v = PyObject_CallFunction(unlink_cb, "s", path);

	PROLOGUE
	EPILOGUE
}

static int
rmdir_func(const char *path)
{
	PyObject *v = PyObject_CallFunction(rmdir_cb, "s", path);

	PROLOGUE
	EPILOGUE
}

static int
symlink_func(const char *path, const char *path1)
{
	PyObject *v = PyObject_CallFunction(symlink_cb, "ss", path, path1);

	PROLOGUE
	EPILOGUE
}

static int
rename_func(const char *path, const char *path1)
{
	PyObject *v = PyObject_CallFunction(rename_cb, "ss", path, path1);

	PROLOGUE
	EPILOGUE
}

static int
link_func(const char *path, const char *path1)
{
	PyObject *v = PyObject_CallFunction(link_cb, "ss", path, path1);

	PROLOGUE
	EPILOGUE
}

static int
chmod_func(const char *path, mode_t m) 
{
	PyObject *v = PyObject_CallFunction(chmod_cb, "si", path, m);

	PROLOGUE
	EPILOGUE
}

static int
chown_func(const char *path, uid_t u, gid_t g) 
{
	PyObject *v = PyObject_CallFunction(chown_cb, "sii", path, u, g);

	PROLOGUE
	EPILOGUE
}

static int
truncate_func(const char *path, off_t length)
{
	PyObject *v = PyObject_CallFunction(truncate_cb, "sK", path, length);

	PROLOGUE
	EPILOGUE
}

#if FUSE_VERSION >= 25
static int
ftruncate_func(const char *path, off_t length, struct fuse_file_info *fi)
{
	PyObject *v = PYO_CALLWITHFI(fi, ftruncate_cb, sK, path, length);

	PROLOGUE
	EPILOGUE
}
#endif

static int
utime_func(const char *path, struct utimbuf *u)
{
	int actime = u ? u->actime : time(NULL);
	int modtime = u ? u->modtime : actime;
	PyObject *v = PyObject_CallFunction(utime_cb, "s(ii)",
	                                    path, actime, modtime);

	PROLOGUE
	EPILOGUE
}

#if FUSE_VERSION >= 22
static int
read_func(const char *path, char *buf, size_t s, off_t off,
                     struct fuse_file_info *fi)
#else
static int
read_func(const char *path, char *buf, size_t s, off_t off)
#endif
{
	PyObject *v = PYO_CALLWITHFI(fi, read_cb, siK, path, s, off);

	PROLOGUE

	if(PyString_Check(v)) {
		if(PyString_Size(v) > s)
			goto OUT_DECREF;
		memcpy(buf, PyString_AsString(v), PyString_Size(v));
		ret = PyString_Size(v);
	}

	EPILOGUE
}

#if FUSE_VERSION >= 22
static int
write_func(const char *path, const char *buf, size_t t, off_t off,
           struct fuse_file_info *fi)
#else
static int
write_func(const char *path, const char *buf, size_t t, off_t off)
#endif
{
	PyObject *v = PYO_CALLWITHFI(fi, write_cb, ss#K, path, buf, t, off);

	PROLOGUE
	EPILOGUE
}

#if FUSE_VERSION >= 22
static int
open_func(const char *path, struct fuse_file_info *fi)
{
	PyObject *v = PyObject_CallFunction(open_cb, "si", path, fi->flags);
	PROLOGUE

	fi->fh = (uintptr_t) v;

	return 0;

	EPILOGUE
}
#else
static int
open_func(const char *path, int mode)
{
	PyObject *v = PyObject_CallFunction(open_cb, "si", path, mode);
	PROLOGUE

	EPILOGUE
}
#endif

#if FUSE_VERSION >= 25
static int
create_func(const char *path, mode_t mode, struct fuse_file_info *fi)
{
	PyObject *v = PyObject_CallFunction(create_cb, "si", path, fi->flags, mode);
	PROLOGUE

	fi->fh = (uintptr_t) v;

	return 0;

	EPILOGUE
}
#endif

#if FUSE_VERSION >= 22
static int
release_func(const char *path, struct fuse_file_info *fi)
{
	PyObject *v = fi_to_py(fi) ?
		      PyObject_CallFunction(release_cb, "siN", path, fi->flags,
		                            fi_to_py(fi)) :
		      PyObject_CallFunction(release_cb, "si", path, fi->flags);
#else
static int
release_func(const char *path, int flags)
{
	PyObject *v = PyObject_CallFunction(release_cb, "si", path, flags);
#endif
	PROLOGUE

	EPILOGUE
}

#if FUSE_VERSION >= 25
static int
statfs_func(const char *dummy, struct statvfs *fst)
#else
static int
statfs_func(const char *dummy, struct statfs *fst)
#endif
{
	PyObject *tmp;
	PyObject *v = PyObject_CallFunction(statfs_cb, "");

	PROLOGUE


	fetchattr(fst, f_bsize);
#if FUSE_VERSION >= 25
	fetchattr(fst, f_frsize);
#endif
	fetchattr(fst, f_blocks);
	fetchattr(fst, f_bfree);
	fetchattr(fst, f_bavail);
	fetchattr(fst, f_files);
	fetchattr(fst, f_ffree);
#if FUSE_VERSION >= 25
	fetchattr(fst, f_favail);
	fetchattr(fst, f_flag);
	fetchattr(fst, f_namemax);
#else
	fetchattr_nam(fst, f_namelen, "f_namemax");
#endif

	ret = 0;
 
	EPILOGUE
}

#if FUSE_VERSION >= 22
static int
fsync_func(const char *path, int datasync, struct fuse_file_info *fi)
#else
static int
fsync_func(const char *path, int datasync)
#endif
{
	PyObject *v = PYO_CALLWITHFI(fi, fsync_cb, si, path, datasync);

	PROLOGUE
	EPILOGUE
}

#if FUSE_VERSION >= 22
static int
flush_func(const char *path, struct fuse_file_info *fi)
#else
static int
flush_func(const char *path)
#endif
{
	PyObject *v = PYO_CALLWITHFI(fi, flush_cb, s, path);

	PROLOGUE
	EPILOGUE
}

static int
getxattr_func(const char *path, const char *name, char *value, size_t size)
{
	PyObject *v = PyObject_CallFunction(getxattr_cb, "ssi", path, name,
	                                    size);

	PROLOGUE

	if(PyString_Check(v)) {
		if(PyString_Size(v) > size)
			goto OUT_DECREF;
		memcpy(value, PyString_AsString(v), PyString_Size(v));
		ret = PyString_Size(v);
	}

	EPILOGUE
}

static int
listxattr_func(const char *path, char *list, size_t size)
{
	PyObject *v = PyObject_CallFunction(listxattr_cb, "si", path, size);
	PyObject *iter, *w;
	char *lx = list;

	PROLOGUE

	iter = PyObject_GetIter(v);
	if(!iter) {
		PyErr_Print();
		goto OUT_DECREF;
	}

	for (;;) {
		int ilen;

	        w = PyIter_Next(iter);
		if (!w) {
			ret = lx - list;
			break;
		}

		if (!PyString_Check(w)) {
			Py_DECREF(w);
			break;
		}

		ilen = PyString_Size(w);
		if (lx - list + ilen >= size) {
			Py_DECREF(w);
			break;
		}

		strncpy(lx, PyString_AsString(w), ilen + 1);
		lx += ilen + 1;

		Py_DECREF(w);
	}

	Py_DECREF(iter);
	if (PyErr_Occurred()) {
		PyErr_Print();
		ret = -EINVAL;
	}

	EPILOGUE
}

static int
setxattr_func(const char *path, const char *name, const char *value,
              size_t size, int flags)
{
	PyObject *v = PyObject_CallFunction(setxattr_cb, "sss#i", path, name,
                                            value, size, flags);

	PROLOGUE
	EPILOGUE
}

static int
removexattr_func(const char *path, const char *name)
{
	PyObject *v = PyObject_CallFunction(removexattr_cb, "ss", path, name);

	PROLOGUE
	EPILOGUE
}

#if FUSE_VERSION >= 25
static int
access_func(const char *path, int mask)
{
	PyObject *v = PyObject_CallFunction(access_cb, "si", path, mask);

	PROLOGUE
	EPILOGUE
}
#endif

static void
process_cmd(struct fuse *f, struct fuse_cmd *cmd, void *data)
{
	PyInterpreterState *interp = (PyInterpreterState *) data;
	PyThreadState *state;

	PyEval_AcquireLock();
	state = PyThreadState_New(interp);
	PyThreadState_Swap(state);
#if FUSE_VERSION >= 22
	fuse_process_cmd(f, cmd);
#else
	__fuse_process_cmd(f, cmd);
#endif
	PyThreadState_Clear(state);
	PyThreadState_Swap(NULL);
	PyThreadState_Delete(state);
	PyEval_ReleaseLock();
}

static int
pyfuse_loop_mt(struct fuse *f)
{
	PyInterpreterState *interp;
	PyThreadState *save;
	int err;

	PyEval_InitThreads();
	interp = PyThreadState_Get()->interp;
	save = PyEval_SaveThread();
#if FUSE_VERSION >= 22
	err = fuse_loop_mt_proc(f, process_cmd, interp);
#else
	err = __fuse_loop_mt(f, process_cmd, interp);
#endif
	/* Not yet reached: */
	PyEval_RestoreThread(save);

	return(err);
}

static struct fuse *fuse=NULL;

static PyObject *
Fuse_main(PyObject *self, PyObject *args, PyObject *kw)
{
#if FUSE_VERSION < 26
	int fd;
#endif
	int multithreaded=0, mthp;
	PyObject *fargseq = NULL;
	int err;
	int i;
	char *fmp;
	struct fuse_operations op;
	int fargc;
	char **fargv;

	static char  *kwlist[] = {
		"getattr", "readlink", "readdir", "mknod",
		"mkdir", "unlink", "rmdir", "symlink", "rename",
		"link", "chmod", "chown", "truncate", "utime",
		"open", "read", "write", "release", "statfs", "fsync",
		"create", "opendir", "releasedir", "fsyncdir", "flush",
	        "ftruncate", "fgetattr", "getxattr", "listxattr", "setxattr",
	        "removexattr", "access", "fuse_args", "multithreaded", NULL
	};
	
	memset(&op, 0, sizeof(op));

	if (!PyArg_ParseTupleAndKeywords(args, kw,
	                                 "|OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOi", 
	                                 kwlist, &getattr_cb, &readlink_cb,
	                                 &readdir_cb, &mknod_cb, &mkdir_cb,
	                                 &unlink_cb, &rmdir_cb, &symlink_cb,
	                                 &rename_cb, &link_cb, &chmod_cb,
	                                 &chown_cb, &truncate_cb, &utime_cb,
	                                 &open_cb, &read_cb, &write_cb,
	                                 &release_cb, &statfs_cb, &fsync_cb,
	                                 &create_cb, &opendir_cb,
	                                 &releasedir_cb, &fsyncdir_cb,
	                                 &flush_cb, &ftruncate_cb,
	                                 &fgetattr_cb, &getxattr_cb,
	                                 &listxattr_cb, &setxattr_cb,
	                                 &removexattr_cb, &access_cb,
	                                 &fargseq, &multithreaded))
		return NULL;

#define DO_ONE_ATTR_AS(fname, pyname)		\
	 if(pyname ## _cb) {			\
		Py_INCREF(pyname ## _cb);	\
		op.fname = pyname ## _func;	\
	} else					\
		op.fname = NULL;

#define DO_ONE_ATTR(name)			\
	DO_ONE_ATTR_AS(name, name)

	DO_ONE_ATTR(getattr);
	DO_ONE_ATTR(readlink);
#if FUSE_VERSION >= 23
	DO_ONE_ATTR(opendir);
	DO_ONE_ATTR(releasedir);
	DO_ONE_ATTR(fsyncdir);
	DO_ONE_ATTR(readdir);
#else
	DO_ONE_ATTR_AS(getdir, readdir);
#endif
	DO_ONE_ATTR(mknod);
	DO_ONE_ATTR(mkdir);
	DO_ONE_ATTR(unlink);
	DO_ONE_ATTR(rmdir);
	DO_ONE_ATTR(symlink);
	DO_ONE_ATTR(rename);
	DO_ONE_ATTR(link);
	DO_ONE_ATTR(chmod);
	DO_ONE_ATTR(chown);
	DO_ONE_ATTR(truncate);
	DO_ONE_ATTR(utime);
	DO_ONE_ATTR(open);
	DO_ONE_ATTR(read);
	DO_ONE_ATTR(write);
	DO_ONE_ATTR(release);
	DO_ONE_ATTR(statfs);
	DO_ONE_ATTR(fsync);
	DO_ONE_ATTR(flush);
	DO_ONE_ATTR(getxattr);
	DO_ONE_ATTR(listxattr);
	DO_ONE_ATTR(setxattr);
	DO_ONE_ATTR(removexattr);
#if FUSE_VERSION >= 25
	DO_ONE_ATTR(ftruncate);
	DO_ONE_ATTR(fgetattr);
	DO_ONE_ATTR(access);
	DO_ONE_ATTR(create);
#endif

#undef DO_ONE_ATTR

	if (!fargseq || !PySequence_Check(fargseq) ||
            (fargc = PySequence_Length(fargseq)) == 0) {
		PyErr_SetString(PyExc_TypeError,
		                "fuse_args is not a non-empty sequence");
		return(NULL);
	}

 	fargv = malloc(fargc * sizeof(char *)); 	
	if (!fargv)
		return(PyErr_NoMemory());

	if (fargseq) {
		for (i=0; i < fargc; i++) {
			PyObject *pa;
	
			pa = PySequence_GetItem(fargseq, i);
			if (!PyString_Check(pa)) {
				Py_DECREF(pa);

				PyErr_SetString(PyExc_TypeError,
			                        "fuse argument is not a string");
		                return(NULL);
			}
			fargv[i] =  PyString_AsString(pa);

			Py_DECREF(pa);
		}
	}

	/*
   	 * We don't use the mthp value, set below. We just pass it on so that
   	 * the lib won't end up in dereferring a NULL pointer.
   	 * (Later versions check for NULL, nevertheless we play safe.)
   	 */
#if FUSE_VERSION >= 26
	fuse = fuse_setup(fargc, fargv, &op, sizeof(op), &fmp, &mthp, NULL);
#elif FUSE_VERSION >= 22
	fuse = fuse_setup(fargc, fargv, &op, sizeof(op), &fmp, &mthp, &fd);
#else
	fuse = __fuse_setup(fargc, fargv, &op, &fmp, &mthp, &fd);
#endif
	free(fargv);

	if (fuse == NULL) {
		PyErr_SetString(Py_FuseError, "filesystem initialization failed");

		return (NULL);
	}
		 
	if (multithreaded)
		err = pyfuse_loop_mt(fuse);
	else
		err = fuse_loop(fuse);
	
#if FUSE_VERSION >= 26
	fuse_teardown(fuse, fmp);	
#elif FUSE_VERSION >= 22
	fuse_teardown(fuse, fd, fmp);
#else
	__fuse_teardown(fuse, fd, fmp);
#endif

	if (err == -1) {
		PyErr_SetString(Py_FuseError, "service loop failed");

		return (NULL);
	}		 

	Py_INCREF(Py_None);
	return Py_None;
}

static char FuseInvalidate__doc__[] =
	"Tell Fuse kernel module to explicitly invalidate a cached inode's contents\n";

static PyObject *
FuseInvalidate(PyObject *self, PyObject *args)
{
	char *path;
	PyObject *ret, *arg1;
	int err;

	if (!(arg1 = PyTuple_GetItem(args, 1)))
		return(NULL);

	if(!PyString_Check(arg1)) {
		PyErr_SetString(PyExc_TypeError, "argument must be a string");

		return(NULL);
	}

	path = PyString_AsString(arg1);

	err = fuse_invalidate(fuse, path);

	ret = PyInt_FromLong(err);

	return(ret);
}

static char FuseGetContext__doc__[] =
	"Return the context of a filesystem operation in a dict. uid, gid, pid\n";

static PyObject *
FuseGetContext(PyObject *self, PyObject *args)
{
	struct fuse_context *fc;
	PyObject *ret;
	PyObject *num;

	fc = fuse_get_context();
	ret = PyDict_New();

	if(!ret)
		return(NULL);

	num = PyInt_FromLong(fc->uid);
	PyDict_SetItemString(ret, "uid", num);	

	num = PyInt_FromLong(fc->gid);
	PyDict_SetItemString(ret, "gid", num);	

	num = PyInt_FromLong(fc->pid);
	PyDict_SetItemString(ret, "pid", num);	

	return(ret);
}

static char FuseAPIVersion__doc__[] =
	"Return FUSE API version.\n";

static PyObject *
FuseAPIVersion(PyObject *self, PyObject *args)
{
	PyObject *favers = PyInt_FromLong(FUSE_VERSION);

	return favers;
}

static PyMethodDef Fuse_methods[] = {
	{"main",	(PyCFunction)Fuse_main,	 METH_VARARGS|METH_KEYWORDS},
	{"FuseGetContext", (PyCFunction)FuseGetContext, METH_VARARGS, FuseGetContext__doc__},
	{"FuseInvalidate", (PyCFunction)FuseInvalidate, METH_VARARGS, FuseInvalidate__doc__},
	{"FuseAPIVersion", (PyCFunction)FuseAPIVersion, METH_NOARGS,  FuseAPIVersion__doc__},
	{NULL,		NULL}		/* sentinel */
};


/* Initialization function for the module (*must* be called init_fuse) */

DL_EXPORT(void)
init_fuse(void)
{
	PyObject *m, *d;
 
	/* Create the module and add the functions */
	m = Py_InitModule("_fuse", Fuse_methods);

	/* Add some symbolic constants to the module */
	d = PyModule_GetDict(m);
	Py_FuseError = PyErr_NewException("fuse.FuseError", NULL, NULL);
	PyDict_SetItemString(d, "FuseError", Py_FuseError);
	/* compat */
	PyDict_SetItemString(d, "error", Py_FuseError);
}
