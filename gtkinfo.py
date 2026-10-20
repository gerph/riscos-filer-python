"""
The file information window for GTK.

Needs PyGObject and GTK 3.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import explorer


class GtkFileInfoFrame(Gtk.Window):
    """
    Shows what is known about a file: its name, type, size and date/time.
    """

    def __init__(self, parent, fsfile, explorers=None, pos=None):
        """
        @param parent:      The registry of windows that opened it, or None
        @param fsfile:      The file to describe
        @param explorers:   The registry (`explorers.FSExplorersBase`) to tell about the window
        @param pos:         Tuple (x, y) to open at, or None
        """
        super(GtkFileInfoFrame, self).__init__(title="File info: {}".format(fsfile.filename))
        self.parent = parent
        self.fsfile = fsfile
        self.explorers = explorers
        self.set_resizable(False)
        if pos:
            self.move(int(pos[0]), int(pos[1]))

        grid = Gtk.Grid()
        grid.set_border_width(8)
        grid.set_column_spacing(12)
        grid.set_row_spacing(4)
        for (row, (name, value)) in enumerate(explorer.file_info_fields(fsfile)):
            label = Gtk.Label(label=name)
            label.set_halign(Gtk.Align.END)
            grid.attach(label, 0, row, 1, 1)
            text = Gtk.Label(label=value)
            text.set_halign(Gtk.Align.START)
            text.set_selectable(True)
            grid.attach(text, 1, row, 1, 1)
        self.add(grid)

        self.connect("delete-event", self.on_delete)
        if self.explorers:
            self.explorers.fileinfo_has_opened(self.fsfile.filename, self)

    def on_delete(self, widget, event):
        if self.explorers:
            self.explorers.fileinfo_has_closed(self.fsfile.filename)
        self.destroy()
        return True

    # The window protocol, which the registry of windows (explorers.FSExplorersBase) uses.

    def show_window(self):
        self.show_all()
        self.present()

    def raise_window(self):
        self.present()

    def close_window(self):
        self.on_delete(self, None)
