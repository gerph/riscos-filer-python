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

    def dir(self, dirname):
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
        self.leafname = self.fs.leafname(self.filename)
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
            filelist = self.get_filelist()

            self._files = {}
            for f in filelist:
                fsfile = self.get_file(f)
                self._files[fsfile.leafname] = fsfile

        return sorted(self._files.values())
