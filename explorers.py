"""
The explorer windows that are open: one per directory, and one information window per file.

Opening a directory that already has a window raises that window instead of opening another, as
the RISC OS filer does, so something has to know which windows there are. That is here, and it
does not depend on a toolkit: a window is anything which provides

    show_window()   make the window visible
    raise_window()  bring the window to the front
    close_window()  close the window

A window tells the registry when it opens (`window_has_opened()` or `fileinfo_has_opened()`) and
when it has closed (`window_has_closed()` or `fileinfo_has_closed()`).

A toolkit subclasses `FSExplorersBase`, and provides `create_explorer()` and `create_fileinfo()`
to make its windows.
"""


class FSExplorersBase(object):
    """
    Tracks the explorer windows and file information windows that have been opened.
    """

    def __init__(self, fs):
        """
        @param fs:  `FSBase` for the file system, which gives the names to compare
        """
        self.fs = fs
        self.open_windows = {}
        self.open_fileinfos = {}

    def fsfile_key(self, filename):
        """
        Return a key for the file that has been requested.

        For systems like Windows or RISC OS, this will be a case insensitive name,
        but for Linux might be an identity.
        """
        return self.fs.normalise_name(filename)

    # --- Explorer windows

    def window_has_closed(self, dirname):
        filenamekey = self.fsfile_key(dirname)
        if filenamekey in self.open_windows:
            del self.open_windows[filenamekey]

    def window_has_opened(self, dirname, window):
        filenamekey = self.fsfile_key(dirname)
        existing = self.open_windows.get(filenamekey)
        if existing is not None and existing is not window:
            # If there was a window already, force it to close so that we don't get multiple windows on the screen.
            # Shouldn't happen if these functions are called consistently.
            existing.close_window()
        self.open_windows[filenamekey] = window

    def find_window(self, dirname):
        return self.open_windows.get(self.fsfile_key(dirname), None)

    def create_explorer(self, dirname, pos=None, display_format=None, sort_order=None):
        """
        Overloadable: Make the window for a directory.

        @return: The window, or None if it could not be made (the failure having been reported)
        """
        raise NotImplementedError("{}.create_explorer() is not implemented".format(self.__class__.__name__))

    def open_window(self, dirname, pos=None, display_format=None, sort_order=None):
        """
        Show the window for a directory, making it if there is not one already.

        @return: The window, or None if it could not be made
        """
        win = self.find_window(dirname)
        if win:
            win.raise_window()
        else:
            win = self.create_explorer(dirname, pos=pos, display_format=display_format, sort_order=sort_order)
            if win:
                win.show_window()
        return win

    # --- Information windows

    def fileinfo_has_closed(self, filename):
        filenamekey = self.fsfile_key(filename)
        if filenamekey in self.open_fileinfos:
            del self.open_fileinfos[filenamekey]

    def fileinfo_has_opened(self, filename, window):
        filenamekey = self.fsfile_key(filename)
        existing = self.open_fileinfos.get(filenamekey)
        if existing is not None and existing is not window:
            existing.close_window()
        self.open_fileinfos[filenamekey] = window

    def find_fileinfo(self, filename):
        return self.open_fileinfos.get(self.fsfile_key(filename), None)

    def create_fileinfo(self, filename, pos=None):
        """
        Overloadable: Make the information window for a file.

        @return: The window, or None if it could not be made (the failure having been reported)
        """
        raise NotImplementedError("{}.create_fileinfo() is not implemented".format(self.__class__.__name__))

    def open_fileinfo(self, filename, pos=None):
        """
        Show the information window for a file, making it if there is not one already.

        @return: The window, or None if it could not be made
        """
        win = self.find_fileinfo(filename)
        if win:
            win.raise_window()
        else:
            win = self.create_fileinfo(filename, pos=pos)
            if win:
                win.show_window()
        return win
