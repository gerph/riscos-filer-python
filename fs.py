import functools
import os


class FSError(Exception):
    pass


class FSFileNotFoundError(FSError):
    pass


class FSBase(object):

    dirsep = '/'

    def __init__(self):
        pass

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
        raise NotImplementedError("{}.root() is not implemented".format(self.__class__.__name__))

    def dir(self, name):
        """
        Return a given directory for a given filesystem.
        """
        raise NotImplementedError("{}.dir() is not implemented".format(self.__class__.__name__))

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

        return self.rootname() + self.dirsep.join(new_args)

    def split(self, filename):
        return [part for part in filename.split(self.dirsep) if part]

    def dirname(self, filename):
        parts = self.split(filename)
        if len(parts) > 1:
            return self.join(parts[:-1])
        else:
            return self.rootname()

    def leafname(self, filename):
        parts = self.split(filename)
        return parts[-1]


@functools.total_ordering
class FSFileBase(object):
    TYPE_DATA = 0xFFD
    TYPE_DIRECTORY = 0x1000
    TYPE_LOADEXEC = -1

    def __init__(self, fs, filename, parent=None):
        self.fs = fs
        self.filename = filename
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
        return False

    def filetype(self):
        # Unknown type always goes to data.
        return self.TYPE_DATA

    @property
    def leafname(self):
        return self.fs.leafname(self.filename)


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

    def get_file(self, leafname):
        """
        Overridden: Return a FSFile object for this file.
        """
        return FSFileBase(self.fs, self.fs.join(self.dirname, leafname))

    def get_filenames(self):
        """
        Overridden: Return a list of the leafnames in this directory.
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
            fsfile = self.files.get(namekey, None)
            if fsfile is None:
                raise FSFileNotFoundError("File '{}' not found in {}".format(name_or_index,
                                                                             self.dirname))
            return fsfile

        else:
            raise NotImplementedError("Cannot read files from FS using a {}".format(name_or_index.__class__.__name__))

    def __len__(self):
        return len(self.files)

    @property
    def files(self):
        """
        Return a list of objects for files within this directory
        """
        if self._files is None:
            leafnames = self.get_filenames()

            self._files = {}
            for leafname in sorted(leafnames):
                self._files[self.fs.normalise_name(leafname)] = self.get_file(leafname)

        return sorted(self._files.values())


class FSNative(FSBase):

    def __init__(self, anchor='/'):
        super(FSNative, self).__init__()
        self.anchor = anchor

    def rootname(self):
        """
        Return the name of the root directory.
        """
        return '/'

    def rootdir(self):
        """
        Return the root directory for a given filesystem.
        """
        return FSDirectoryNative(self, None, self.rootname())

    def dir(self, filename):
        """
        Return a given directory for a given filesystem.
        """
        parts = self.split(filename)
        fsdir = self.rootdir()
        for index in range(0, len(parts)):
            dirparts = parts[0:index + 1]
            filename = self.join(*dirparts)
            fsdir = FSDirectoryNative(self, fsdir, filename)

        return fsdir

    def native_filename(self, filename):
        if self.anchor == '/' and self.dirsep == '/':
            return filename

        parts = self.split(filename)
        parts.insert(0, self.anchor)
        return os.path.join(*parts)


class FSFileNative(FSFileBase):

    def __init__(self, fs, filename, parent=None):
        super(FSFileNative, self).__init__(fs, filename, parent)
        self.native_filename = self.fs.native_filename(self.filename)
        self._isdir = None

    def isdir(self):
        if self._isdir is None:
            self._isdir = os.path.isdir(self.native_filename)
        return self._isdir

    @property
    def leafname(self):
        return self.fs.leafname(self.filename)


class FSDirectoryNative(FSDirectoryBase):
    """
    Object for retrieving information about files within a filesystem.
    """

    def __init__(self, fs, parent, dirname):
        super(FSDirectoryNative, self).__init__(fs, parent, dirname)

    def get_file(self, leafname):
        """
        Overridden: Return a FSFile object for this file.
        """
        return FSFileNative(self.fs, self.fs.join(self.dirname, leafname))

    def get_filenames(self):
        """
        Overridden: Return a list of the leafnames in this directory.
        """
        ndirname = self.fs.native_filename(self.dirname)
        files = os.listdir(ndirname)
        return files


fs = FSNative('/Users/charles')
