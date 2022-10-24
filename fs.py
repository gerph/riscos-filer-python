"""
Base classes for abstracting access to objects on a file system.
"""

import datetime
import functools
import os


class FSError(Exception):
    pass


class FSFileNotFoundError(FSError):
    pass


class FSNotADirectoryError(FSError):
    pass


class FSBase(object):

    dirsep = '/'
    do_caching = True

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
        if dirname != parent:
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
        Return a FSFileInfo for the root.
        """
        raise NotImplementedError("{}.rootinfo() is not implemented".format(self.__class__.__name__))

    def fileinfo(self, filename):
        dirname = self.dirname(filename)
        leafname = self.leafname(filename)
        if dirname == self.rootname and leafname == '':
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

    def dirname(self, filename):
        parts = self.split(filename)
        if len(parts) > 1:
            return self.join(*parts[:-1])
        else:
            return self.rootname()

    def leafname(self, filename):
        parts = self.split(filename)
        if len(parts) == 0:
            return ''
        return parts[-1]


@functools.total_ordering
class FSFileBase(object):
    TYPE_DATA = 0xFFD
    TYPE_DIRECTORY = 0x1000
    TYPE_IMAGE = 0x3000
    TYPE_LOADEXEC = -1

    def __init__(self, fs, filename, size=None, epochtime=None, parent=None):
        self.fs = fs
        self.filename = filename
        self.leafname = self.fs.leafname(self.filename)
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
            names = sorted(self.files)
            try:
                name = names[name_or_index]
            except IndexError:
                raise FSFileNotFoundError("File #{} not found in {}".format(name_or_index,
                                                                            self.dirname))
            return self.files[name]

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
