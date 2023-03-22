"""
Base classes for abstracting access to objects on a file system.
"""

import datetime
import functools
import os


try:
    unicode
except NameError:
    # Python 3
    unicode = str


class FSError(Exception):
    pass


class FSFileNotFoundError(FSError):
    pass


class FSReadFailedError(FSError):
    pass


class FSNotADirectoryError(FSError):
    pass


class FSWriteFailedError(FSError):
    pass


class FSMkDirFailedError(FSError):
    pass


class FSDeleteFailedError(FSError):
    pass


class FSRenameFailedError(FSError):
    pass


class FSBase(object):

    dirsep = '/'
    do_caching = True
    supports_mkdir = False
    supports_delete = False
    supports_rename = False

    def __init__(self):
        self.cached_dirs = {}

    def __repr__(self):
        return "<{}()>".format(self.__class__.__name__)

    def rootname(self):
        """
        Return the name of the root directory.
        """
        raise NotImplementedError("{}.rootname() is not implemented".format(self.__class__.__name__))

    def rootdir(self):
        """
        Return the root directory for a given filesystem.
        """
        return self.dir(self.rootname())

    def dir(self, dirname):
        """
        Return a given directory for a given filesystem (through the cache).
        """
        cache_key = None
        if self.do_caching:
            cache_key = self.normalise_name(dirname)
            fsdir = self.cached_dirs.get(cache_key, None)
            if fsdir is not None:
                return fsdir

        # We recurse upwards, trying to get earlier dirs so that we have all the
        # directories cached, if we need to. Or we'll report errors if the directory
        # did not exist.
        parent = self.dirname(dirname)
        parent_fsdir = None
        if dirname != parent and dirname != '':
            parent_fsdir = self.dir(parent)

        fsdir = self.get_dir(dirname, parent_fsdir)
        if self.do_caching:
            self.cached_dirs[cache_key] = fsdir
        return fsdir

    def get_dir(self, dirname, parent_fsdir=None):
        """
        Overloadable: Return a given directory for a given filesystem.
        """
        raise NotImplementedError("{}.dir() is not implemented".format(self.__class__.__name__))

    def invalidate_dir(self, dirname):
        """
        Invalidate the cache for a given directory name.
        """
        if self.do_caching:
            cache_key = self.normalise_name(dirname)
            if cache_key in self.cached_dirs:
                # We can just call the invalidate function in the cached directory.
                self.cached_dirs[cache_key].invalidate()
        # If we aren't caching, we hope that the user is able to invalidate any context
        # they hold.

    def rootinfo(self):
        """
        Return a FSFile for the root.
        """
        raise NotImplementedError("{}.rootinfo() is not implemented".format(self.__class__.__name__))

    def fileinfo(self, filename):
        dirname = self.dirname(filename)
        leafname = self.leafname(filename)
        if dirname == self.rootname() and leafname == '':
            return self.rootinfo()
        fsdir = self.dir(dirname)
        return fsdir[leafname]

    def normalise_name(self, name):
        """
        Make the keys for lookups - we lower case for a case insensitive filesystem.
        """
        return name.lower()

    def join(self, *args):
        new_args = []
        for arg in args:
            if self.dirsep in arg:
                more_args = self.split(arg)
                new_args.extend(more_args)
            else:
                new_args.append(arg)

        root = self.rootname()
        name = self.dirsep.join(new_args)
        if not name.startswith(root):
            return root + name
        return name

    def split(self, filename):
        return [part for part in filename.split(self.dirsep) if part]

    def dirandleafname(self, filename):
        parts = self.split(filename)
        if len(parts) > 1:
            dirname = self.join(*parts[:-1])
            leafname = parts[-1]
        elif len(parts) == 1:
            dirname = ''
            leafname = parts[0]
        else:
            dirname = self.rootname()
            leafname = ''
        return (dirname, leafname)

    def dirname(self, filename):
        return self.dirandleafname(filename)[0]

    def leafname(self, filename):
        return self.dirandleafname(filename)[1]

    def can_mkdir(self, dirname=None):
        """
        Check whether we can create a directory in a given directory.

        @param dirname: Directory name to check, or None to check FS capability.
        """
        if dirname is None or not self.supports_mkdir:
            return self.supports_mkdir
        fsdir = self.dir(dirname)
        return fsdir.can_mkdir()

    def can_delete(self, filename=None):
        """
        Check whether we can delete a given file.

        @param dirname: File name to check, or None to check FS capability.
        """
        if filename is None or not self.supports_delete:
            return self.supports_delete
        fsfile = self.fileinfo(filename)
        return fsfile.can_delete()

    def can_rename(self, source=None, dest=None):
        """
        Check whether we can rename a given file.

        @param dirname: File name to check, or None to check FS capability.
        """
        if not self.supports_rename:
            return False
        if source is None:
            # They're only asking about the FS as a whole, so we do support rename
            return True

        (source_dir, source_leaf) = self.dirandleafname(source)
        source_fsdir = self.dir(source_dir)

        if dest is not None:
            (dest_dir, dest_leaf) = self.dirandleafname(dest)
            dest_fsdir = self.dir(dest_dir)
        else:
            dest_dir = None
            dest_leaf = None
            dest_fsdir = None

        if source_dir == dest_dir or dest_dir is None:
            return source_fsdir.can_rename(source_leaf, dest_leaf)

        # FIXME: We don't support moves between directories yet, so this is not supported
        return False

    def mkdir(self, dirname):
        """
        Create a directory with a given name.

        @param dirname: Directory to create.
        """
        if not self.supports_mkdir:
            raise FSMkDirFailedError("{}.mkdir() is not supported".format(self.__class__.__name__))

        fsdir = self.dir(dirname)
        leafname = self.leafname(dirname)
        return fsdir.mkdir(leafname)

    def rename(self, source, dest):
        """
        Rename a file from one location to another. May move the file.

        @param dirname: Directory to create.
        """
        if not self.supports_rename:
            raise FSRenameFailedError("{}.rename() is not supported".format(self.__class__.__name__))

        (source_dir, source_leaf) = self.dirandleafname(source)
        (dest_dir, dest_leaf) = self.dirandleafname(dest)
        if self.normalise_name(source_dir) == self.normalise_name(dest_dir):
            # The source and destinations are the same, so this is a rename within directory
            fsdir = self.dir(source_dir)
            fsdir.rename(source_leaf, dest_leaf)
            return

        # FIXME: Add a move operation
        raise FSRenameFailedError("Moving files between directories is not supported")


@functools.total_ordering
class FSFileBase(object):
    TYPE_DATA = 0xFFD
    TYPE_DIRECTORY = 0x1000
    TYPE_IMAGE = 0x3000
    TYPE_LOADEXEC = -1

    def __init__(self, fs, filename, size=None, epochtime=None, parent=None):
        self.fs = fs
        self.filename = filename
        (self.dirname, self.leafname) = self.fs.dirandleafname(self.filename)
        self._size = size
        self._epochtime = epochtime
        self._parent = parent

    def __repr__(self):
        return "<{}({!r})>".format(self.__class__.__name__, self.filename)

    def __eq__(self, other):
        if isinstance(other, (str, unicode)):
            return self.leafname == other
        return self.leafname == other.leafname

    def __lt__(self, other):
        if isinstance(other, (str, unicode)):
            return self.leafname < other
        return self.leafname < other.leafname

    def isdir(self):
        """
        Is this object a directory?
        """
        return False

    def dir(self):
        """
        Obtain a FSDirectory for this object, if this is directory.
        """
        if not self.isdir():
            raise FSNotADirectoryError("FSFile '{}' is not a directory".format(self.filename))
        return self.fs.dir(self.filename)

    def parent(self):
        """
        Obtain a FSDirectory for the parent directory of this object.
        """
        dirname = self.fs.dirname(self.filename)
        return self.fs.dir(dirname)

    def filetype(self):
        # Unknown type always goes to data.
        return self.TYPE_DATA

    def size(self):
        # Return the size we gave on creation
        if self._size is None:
            return -1
        return self._size

    def epochtime(self):
        # Return the Unix epoch time we gave on creation
        if self._epochtime is None:
            return 0
        return self._epochtime

    def open(self, mode='rb'):
        """
        Open the file, returning an io like file handle

        @param mode:    Textual mode, like 'r', 'rb', 'w', 'wb'.
        """
        raise NotImplementedError("{}.open() is not implemented".format(self.__class__.__name__))

    def read(self):
        """
        Read the contents of the file.
        """
        with self.open('rb') as fh:
            data = fh.read()
            return data

    def can_delete(self):
        """
        Overloadable: Check whether we can delete a given file.

        @return: True if this file is deletable.
        """
        # Check the FS itself first
        if not self.fs.can_delete():
            return False
        if not self.parent().is_writeable():
            return False

        # Actually, we always say no in the base implementation.
        return False

    def delete(self):
        """
        Delete this file.
        """
        if not self.can_delete():
            raise FSDeleteFailedError("Cannot delete '{}' from '{}'".format(self.leafname, self.dirname))

        self.do_delete()
        # FIXME: Mark this object as invalid too?
        self.dir().invalidate()

    def do_delete(self):
        """
        Overloadable: Delete the file
        """
        raise FSDeleteFailedError("Cannot delete '{}' from '{}'".format(self.leafname, self.dirname))

    def format_filetype(self):
        filetype = self.filetype()
        if filetype == self.TYPE_DIRECTORY or self.isdir():
            return "Directory"
        if filetype == self.TYPE_LOADEXEC:
            return "Untyped"

        if filetype >= self.TYPE_IMAGE:
            return "Image file (&{:03X})".format(filetype)

        return "&{:03X}".format(filetype)

    def format_size(self):
        size = self.size()
        if size == -1 or size is None:
            return "Unknown"
        return "{} bytes".format(size)

    def format_timestamp(self):
        epochtime = self.epochtime()
        if epochtime is None:
            return "Unknown"
        dt = datetime.datetime.utcfromtimestamp(epochtime)
        return dt.strftime('%H:%M:%S.X %d %b %Y').replace('X', '{:02}'.format(dt.microsecond / 10000))


class FSDirectoryBase(object):
    """
    Object for retrieving information about files within a filesystem.
    """

    def __init__(self, fs, parent, dirname):
        self.fs = fs
        self.parent = parent or self
        self.dirname = dirname
        self._files = None

    def __repr__(self):
        return "<{}(fs={}, dirname={!r})>".format(self.__class__.__name__, self.fs, self.dirname)

    def get_file(self, fileref):
        """
        Overridden: Return a FSFile object for this file.
        """
        return FSFileBase(self.fs, self.fs.join(self.dirname, fileref))

    def get_filelist(self):
        """
        Overridden: Return a list of the files in this directory.

        @return: A list of objects which describe the files in the directory; can be
                 leafnames as strings or structures. The values will be passed to
                 get_file() to convert to a FSFile object.
        """
        return []

    def __getitem__(self, name_or_index):
        if isinstance(name_or_index, int):
            # They wanted the file by index
            names = sorted(self.files, key=lambda fsfile: fsfile.leafname)
            try:
                fsfile = names[name_or_index]
            except IndexError:
                raise FSFileNotFoundError("File #{} not found in {}".format(name_or_index,
                                                                            self.dirname))
            return fsfile

        elif isinstance(name_or_index, (str, unicode)):

            namekey = self.fs.normalise_name(name_or_index)
            self.populate_files()
            fsfile = self._files.get(namekey, None)
            if fsfile is None:
                raise FSFileNotFoundError("File '{}' not found in {}".format(name_or_index,
                                                                             self.dirname))
            return fsfile

        else:
            raise NotImplementedError("Cannot read files from FS using a {}".format(name_or_index.__class__.__name__))

    def __len__(self):
        return len(self.files)

    def __contains__(self, name):
        namekey = self.fs.normalise_name(name)
        self.populate_files()
        return  namekey in self._files

    def invalidate(self):
        self._files = None

    def populate_files(self):
        if self._files is None:
            filelist = self.get_filelist()

            self._files = {}
            for f in filelist:
                fsfile = self.get_file(f)
                namekey = self.fs.normalise_name(fsfile.leafname)
                self._files[namekey] = fsfile

    @property
    def files(self):
        """
        Return a list of objects for files within this directory
        """
        self.populate_files()

        return sorted(self._files.values())

    def is_writeable(self):
        """
        Overloadable: Check whether we can write to this directory.

        @return: True if the files in this folder are modifyable, False if we not.
        """
        return False

    def can_mkdir(self):
        """
        Overloadable: Check whether we can create a directory in a given directory.

        @return: True if directories can be created here, False if we cannot.
        """
        # Check the FS itself first
        if not self.fs.can_mkdir():
            return False
        return self.is_writeable()

    def can_delete(self, leafname):
        """
        Overloadable: Check whether we can delete a given file.

        @return: True if the given leafname is deletable.
        """
        # Check the FS itself first
        if not self.fs.can_delete():
            return False
        if not self.is_writeable():
            return False

        # Now check if the file can be deleted
        try:
            fsfile = self[leafname]
            return fsfile.can_delete()
        except Exception:
            # Any problems mean that we cannot delete
            return False

    def can_rename(self, source_leafname, dest_leafname):
        """
        Overloadable: Check whether we can rename a given file within the directory

        @return: True if the given leafname is renameable.
        """
        # Check the FS itself first
        if not self.fs.can_rename():
            return False
        if not self.is_writeable():
            return False

        if dest_leafname and self.fs.normalise_name(source_leafname) == self.fs.normalise_name(dest_leafname):
            # This is a no-op, so we'll allow it.
            return True

        # Now check if the file can be renamed
        try:
            # Check that the source file exists - will exception if not.
            source_fsfile = self[source_leafname]

            # Check that the destination file exists
            if dest_leafname and dest_leafname in self:
                return False

            # If we passed those checks, we probably can rename.
            return True

        except Exception:
            # Any problems mean that we cannot rename
            return False

    def mkdir(self, leafname):
        """
        Create a directory with a given name.

        @param leafname: leafname of the directory to create.
        """
        if not self.is_writeable():
            raise FSWriteFailedError("Directory '{}' is not writeable".format(self.dirname))

        self.do_mkdir(leafname)
        self.invalidate()

    def do_mkdir(self, leafname):
        """
        Overloadable: Create a directory with a given name.

        @param leafname: leafname of the directory to create.
        """
        raise FSWriteFailedError("Cannot create '{}' in '{}'".format(leafname, self.dirname))

    def rename(self, source_leafname, dest_leafname):
        """
        Rename a given file within the directory

        @param source_leafname: leafname to rename from
        @param dest_leafname:   leafname to rename as
        """
        if self.fs.normalise_name(source_leafname) == self.fs.normalise_name(dest_leafname):
            # This is a no-op.
            return

        if not self.is_writeable():
            raise FSRenameFailedError("Directory '{}' is not writeable".format(self.dirname))

        # Check that the source exists
        source_fsfile = self[source_leafname]

        if dest_leafname in self:
            raise FSRenameFailedError("File '{}' already exists in '{}'".format(dest_leafname, self.dirname))

        self.do_rename(source_leafname, dest_leafname)
        self.invalidate()

    def do_rename(self, source_leafname, dest_leafname):
        """
        Overloadable: Rename a given file within the directory

        @param source_leafname: leafname to rename from
        @param dest_leafname:   leafname to rename as
        """
        raise FSRenameFailedError("Cannot rename '{}' to '{}' in '{}'".format(source_leafname, dest_leafname, self.dirname))
