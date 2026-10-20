"""
The model of a file explorer window: what it shows and what the user can do with it.

The explorer windows (`fsexplorer` for WxWidgets, `gtkexplorer` for GTK) show the files of one
directory in the style of the RISC OS filer. Everything about that which does not depend on a
toolkit is here, so that each toolkit only has to draw the model and pass the user's clicks and
menu choices to it:

* the directory being shown, and the files in it, in the display order;
* the display format (`large`, `small` or `fullinfo`) and the sort order (`name`, `size`,
  `filetype` or `timestamp`);
* the selection, which is a set of leafnames, and which survives the directory being read again;
* what the menu offers (`capabilities()`), given the selection;
* how a click is taken as a RISC OS button (`click_to_button()`), with either mouse model, and
  what activating a file or directory means (`activate()`);
* creating a directory, renaming and deleting, with confirmation and error reporting.

The model does not import a toolkit, and does not draw anything. The functions which change it
return True if the toolkit needs to draw the window again.

Failures are reported, not raised. A directory which cannot be read (because it has been
deleted or renamed behind the window, say) is reported through `report_error`; the model keeps
the listing that it had, and is marked `stale`, so the window can still be closed, refreshed,
or used to open the parent directory.

The file system is accessed through the `fs` module's `FSBase`, `FSDirectoryBase` and
`FSFileBase`, so the model can be tested against a file system held in memory.
"""

import collections


# What the menu of an explorer offers. All the 'shown' fields say whether the item is in the
# menu at all (a read-only explorer has no rename), and the 'enabled' fields whether it can be
# chosen now.
Capabilities = collections.namedtuple(
    'Capabilities',
    ['selection_label',     # The text of the selection item, like "File 'hello'" or "Selection"
     'selection_enabled',   # True if there is a selection
     'clear_enabled',       # True if there is a selection to clear
     'mkdir_shown', 'mkdir_enabled',
     'rename_shown', 'rename_enabled',
     'delete_shown', 'delete_enabled',
     'refresh_shown',
     'view_enabled',        # True if the file under the menu can be viewed (it is not a directory)
     'parent',              # The directory name that Open parent would open, or None
     ])

# What activating a file or directory means, which the toolkit carries out:
#   action OPEN_DIRECTORY: open the directory `target` (a filename); `close` says that this
#                          window is to be replaced by (or closed in favour of) the new one
#   action RUN_FILE:       run the file `target` (an FSFile); `shift` says shift was held
Activation = collections.namedtuple('Activation', ['action', 'target', 'close', 'shift'])

OPEN_DIRECTORY = 'open-directory'
RUN_FILE = 'run-file'


def cascade_offset(counter=0, offset_x=16, offset_y=32):
    """
    Where a window opened as part of a sequence goes, relative to the window opening it.

    Windows opened one after the other appear in different positions, stepping down and to the
    right and then wrapping.

    @param counter:     Number of windows already opened in this sequence
    @param offset_x:    Step across, in pixels
    @param offset_y:    Step down, in pixels

    @return: Tuple (x, y) offset from the position of the opening window
    """
    counterx = (counter % 8) + ((counter // 8) % 6)
    countery = (counter % 8) + (((counter // 8) % 6) / 2.0)
    return (int(offset_x * (counterx + 1)), int(offset_y * (countery + 1)))


class FSExplorerModel(object):
    """
    The state of one explorer window, and the operations on it.

    Public state, which the toolkit reads to draw the window:

    * `dirname`, `fsdir`: the directory being shown
    * `files`: the `FSFile` objects in the display order
    * `display_format`, `sort_order`
    * `stale`: True if the directory could not be read when it was last refreshed, so `files`
      is what it was before; `error` is the message
    """

    default_display_format = 'large'
    default_sort_order = 'name'

    def __init__(self, fs, dirname, display_format=None, sort_order=None, mouse_model_riscos=False,
                 support_mkdir=True, support_delete=True, support_rename=True, support_refresh=True,
                 report_error=None, confirm=None, title_text=None):
        """
        Read the directory to show.

        @param fs:                  `FSBase` for the file system
        @param dirname:             Name of the directory to show
        @param display_format:      'large', 'small' or 'fullinfo' (default 'large')
        @param sort_order:          'name', 'size', 'filetype' or 'timestamp' (default 'name')
        @param mouse_model_riscos:  True for the RISC OS mouse model (Select, Menu, Adjust), False
                                    for the other (left Select, Ctrl+left Adjust, right Menu)
        @param support_mkdir:       False if directories cannot be created from this window
        @param support_delete:      False if files cannot be deleted from this window
        @param support_rename:      False if files cannot be renamed from this window
        @param support_refresh:     False if the window has no Refresh
        @param report_error:        Function called with (title, message) for a failure; the
                                    default drops the message
        @param confirm:             Function called with (title, message, cancel_default) which
                                    returns True if the user agreed; the default says no
        @param title_text:          Text to use as the title, instead of the directory name

        @raise: whatever the file system raises, if the directory cannot be read. The caller
                decides whether that means there is no window to show.
        """
        self.fs = fs
        self.dirname = dirname
        self.fsdir = fs.dir(dirname)
        self.display_format = display_format or self.default_display_format
        self.sort_order = sort_order or self.default_sort_order
        self.mouse_model_riscos = mouse_model_riscos
        self.support_mkdir = support_mkdir
        self.support_delete = support_delete
        self.support_rename = support_rename
        self.support_refresh = support_refresh
        self.report_error = report_error or (lambda title, message: None)
        self.confirm = confirm or (lambda title, message, cancel_default=False: False)
        self.title_text = title_text

        self.stale = False
        self.error = None
        self._selection = set()
        self.files = self._sorted(self.fsdir.files)

    # --- Titles

    def title(self):
        """
        The title shown at the top of the window.
        """
        if self.title_text:
            return self.title_text
        return "Directory: {}".format(self.dirname)

    # --- The files

    def _sort_key(self, sort_order):
        if sort_order == 'name':
            return lambda f: self.fs.normalise_name(f.leafname)
        if sort_order == 'size':
            return lambda f: 0 if f.isdir() else f.size()
        if sort_order == 'filetype':
            return lambda f: -2 if f.isdir() else f.filetype()
        if sort_order == 'timestamp':
            return lambda f: f.epochtime()
        # An order which is not known leaves the files by leafname
        return lambda f: f.leafname

    def _sorted(self, files):
        return sorted(files, key=self._sort_key(self.sort_order))

    def file(self, leafname):
        """
        The file shown with a given leafname, or None.
        """
        for fsfile in self.files:
            if fsfile.leafname == leafname:
                return fsfile
        return None

    def refresh(self):
        """
        Read the directory again.

        The selection is kept for the files which are still there. If the directory cannot be
        read, the error is reported, and the files and the selection are left as they were, but
        the model is marked `stale`.

        @return: True if the window needs to be drawn again
        """
        self.fs.invalidate_dir(self.dirname)
        self.fsdir.invalidate()
        was_stale = self.stale
        try:
            files = self._sorted(self.fsdir.files)
        except Exception as exc:
            self.stale = True
            self.error = str(exc)
            self.report_error("Failed to read directory", self.error)
            return not was_stale

        self.files = files
        self.stale = False
        self.error = None
        self._selection &= set(fsfile.leafname for fsfile in files)
        return True

    def change_directory(self, dirname):
        """
        Show another directory in this window. The selection is cleared.

        If the directory cannot be read, the error is reported and the window keeps showing the
        directory that it was showing.

        @return: True if the window needs to be drawn again
        """
        try:
            fsdir = self.fs.dir(dirname)
            files = self._sorted(fsdir.files)
        except Exception as exc:
            self.report_error("Failed to read directory", str(exc))
            return False

        self.dirname = dirname
        self.fsdir = fsdir
        self.files = files
        self.stale = False
        self.error = None
        self._selection = set()
        return True

    def set_display_format(self, display_format):
        """
        @return: True if the window needs to be drawn again
        """
        if display_format == self.display_format:
            return False
        self.display_format = display_format
        return True

    def set_sort_order(self, sort_order):
        """
        Show the files in another order. The directory is not read again.

        @return: True if the window needs to be drawn again
        """
        if sort_order == self.sort_order:
            return False
        self.sort_order = sort_order
        self.files = self._sorted(self.files)
        return True

    def parent_dirname(self):
        """
        The name of the parent directory, or None if this is the root.
        """
        target = self.fs.dirname(self.dirname)
        if not target or self.fs.normalise_name(target) == self.fs.normalise_name(self.dirname):
            return None
        return target

    # --- The selection

    def is_selected(self, leafname):
        return leafname in self._selection

    def select(self, leafname, state=True):
        """
        Select or deselect a file; a file which is not shown is ignored.

        @param leafname:    File to change
        @param state:       True to select, False to deselect, None to toggle

        @return: True if the selection changed
        """
        if self.file(leafname) is None:
            return False
        if state is None:
            state = leafname not in self._selection
        state = bool(state)
        if state == (leafname in self._selection):
            return False
        if state:
            self._selection.add(leafname)
        else:
            self._selection.discard(leafname)
        return True

    def select_all(self):
        """
        @return: True if the selection changed
        """
        everything = set(fsfile.leafname for fsfile in self.files)
        changed = everything != self._selection
        self._selection = everything
        return changed

    def deselect_all(self):
        """
        @return: True if the selection changed
        """
        changed = bool(self._selection)
        self._selection = set()
        return changed

    def selected(self):
        """
        The selected files, in the display order.
        """
        return [fsfile for fsfile in self.files if fsfile.leafname in self._selection]

    # --- What the user can do

    def capabilities(self, fsfile=None):
        """
        What the menu offers.

        @param fsfile:  The file that the menu was opened over, or None for the window itself.
                        (The view items follow this file and not the whole selection.)

        @return: Capabilities
        """
        selection = self.selected()

        if not selection:
            label = "File ''"
        elif len(selection) == 1:
            kind = 'Directory' if selection[0].isdir() else 'File'
            label = "{} '{}'".format(kind, selection[0].leafname)
        else:
            label = "Selection"

        # New directory only works if the directory allows it
        mkdir_enabled = bool(self.support_mkdir and self.fsdir.can_mkdir())

        # Delete: the file system must allow it, and at least one of the files be deletable
        delete_enabled = False
        if self.support_delete and selection and self.fs.can_delete(None):
            delete_enabled = any(selected.can_delete() for selected in selection)

        # Rename works on one file, if the file system says it is renameable
        rename_enabled = False
        if self.support_rename and len(selection) == 1:
            rename_enabled = bool(self.fs.can_rename(selection[0].filename, None))

        return Capabilities(
                selection_label=label,
                selection_enabled=bool(selection),
                clear_enabled=bool(selection),
                mkdir_shown=self.support_mkdir, mkdir_enabled=mkdir_enabled,
                rename_shown=self.support_rename, rename_enabled=rename_enabled,
                delete_shown=self.support_delete, delete_enabled=delete_enabled,
                refresh_shown=self.support_refresh,
                view_enabled=not (fsfile and fsfile.isdir()),
                parent=self.parent_dirname())

    def click_to_button(self, button, double=False, control=False):
        """
        Take a click as a RISC OS button.

        The RISC OS mouse model has the left button as Select, the middle as Menu and the right as
        Adjust. The other model has left as Select, Ctrl+left as Adjust, and right as Menu.

        @param button:  'left', 'middle' or 'right'
        @param double:  True for a double click (only left and right double click)
        @param control: True if Control was held

        @return: 'SELECT', 'ADJUST' or 'MENU', preceded by 'D-' for a double click; or 'NONE' for
                 a click that means nothing
        """
        result = 'NONE'
        if double:
            if button == 'left':
                result = 'SELECT'
            elif button == 'right':
                result = 'ADJUST'
        else:
            if button == 'left':
                result = 'SELECT'
            elif button == 'right':
                result = 'ADJUST'
            elif button == 'middle':
                result = 'MENU'

        if not self.mouse_model_riscos:
            if result == 'ADJUST':
                # Right button means Menu
                result = 'MENU'
            elif result == 'SELECT' and control:
                result = 'ADJUST'

        if result != 'NONE' and double:
            result = 'D-' + result
        return result

    def activate(self, fsfile, close=False, shift=False):
        """
        Say what activating a file or directory means.

        @param fsfile:  The file or directory
        @param close:   True if the activation was with Adjust (which replaces this window)
        @param shift:   True if Shift was held

        @return: Activation
        """
        if fsfile.isdir():
            return Activation(OPEN_DIRECTORY, fsfile.filename, close, shift)
        return Activation(RUN_FILE, fsfile, close, shift)

    # --- Changing the directory

    def mkdir(self, leafname):
        """
        Create a directory within the directory being shown.

        @return: True if the window needs to be drawn again
        """
        try:
            self.fsdir.mkdir(leafname)
        except Exception as exc:
            self.report_error("Failed to create directory", str(exc))
            return False
        self.refresh()
        return True

    def rename(self, leafname, new_leafname):
        """
        Rename a file within the directory being shown.

        @return: True if the window needs to be drawn again
        """
        source = self.fs.join(self.dirname, leafname)
        dest = self.fs.join(self.dirname, new_leafname)
        try:
            self.fs.rename(source, dest)
        except Exception as exc:
            self.report_error("Failed to rename", str(exc))
            return False
        self.refresh()
        return True

    def delete(self, leafnames=None, ask=True):
        """
        Delete files within the directory being shown.

        Each file is confirmed in turn, unless `ask` is False. A file which the user does not
        confirm is left, as is one which fails to delete (with the failure reported); the others
        are still deleted.

        @param leafnames:   Names of the files to delete, or None for the selection
        @param ask:         False to delete without confirmation

        @return: True if the window needs to be drawn again
        """
        if leafnames is None:
            targets = self.selected()
        else:
            targets = [self.file(leafname) for leafname in leafnames]
            targets = [fsfile for fsfile in targets if fsfile is not None]

        deleted = False
        for fsfile in targets:
            if ask and not self.confirm("Confirm delete object",
                                        "Are you sure you want to delete '{}'?".format(fsfile.filename),
                                        cancel_default=True):
                continue
            try:
                fsfile.delete()
            except Exception as exc:
                self.report_error("Failed to delete", str(exc))
                continue
            deleted = True

        if deleted:
            self.refresh()
        return deleted
