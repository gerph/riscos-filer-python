"""
Implementation of the FS interfaces for the native filesystem, using '/' as separator.
"""


import os

from fs import FSBase, FSFileBase, FSDirectoryBase


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

    def rootinfo(self):
        """
        Return a FSFileInfo for the root.
        """
        return FSFileNative(self, '/')

    def get_dir(self, dirname, parent_fsdir=None):
        """
        Overloadable: Return a given directory for a given filesystem.
        """
        return FSDirectoryNative(self, parent_fsdir, dirname)

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
        self._stat_read = False

    def isdir(self):
        if self._isdir is None:
            self._isdir = os.path.isdir(self.native_filename)
        return self._isdir

    def _stat(self):
        if not self._stat_read:
            stat = os.stat(self.native_filename)
            self._size = stat.st_size
            self._epochtime = stat.st_mtime
            self._stat_read = True
        return

    def open(self, mode='rb'):
        """
        Open the file, returning an io like file handle

        @param mode:    Textual mode, like 'r', 'rb', 'w', 'wb'.
        """
        return open(self.native_filename, mode)

    def size(self):
        self._stat()
        return super(FSFileNative, self).size()

    def epochtime(self):
        self._stat()
        return super(FSFileNative, self).epochtime()


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

    def get_filelist(self):
        """
        Overridden: Return a list of the files in this directory.

        @return: A list of objects which describe the files in the directory; can be
                 leafnames as strings or structures. The values will be passed to
                 get_file() to convert to a FSFile object.
        """
        ndirname = self.fs.native_filename(self.dirname)
        files = os.listdir(ndirname)
        return files
