#!/usr/bin/env python3
"""
Example application showing the GTK explorer, with no emulator: it browses a directory of the
native file system, and exits when its last window is closed. Used for trying out the behaviour.
"""

import argparse
import os
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import fsnative
import gtkexplorer


class DemoExplorers(gtkexplorer.GtkExplorers):
    """
    The registry of windows, which also ends the application when the last window has gone.
    """

    def check_finished(self):
        if not self.open_windows and not self.open_fileinfos:
            Gtk.main_quit()

    def window_has_closed(self, dirname):
        super(DemoExplorers, self).window_has_closed(dirname)
        self.check_finished()

    def fileinfo_has_closed(self, filename):
        super(DemoExplorers, self).fileinfo_has_closed(filename)
        self.check_finished()


def main():
    parser = argparse.ArgumentParser(usage="%s [<options>] [<directory>]" % (os.path.basename(sys.argv[0]),))
    parser.add_argument('--riscos-mouse', action='store_true', default=False,
                        help="Use the RISC OS mouse model: Select, Menu and Adjust are the left, middle and right buttons")
    parser.add_argument('directory', nargs='?', default='~', help="Directory to display")
    options = parser.parse_args()

    class DemoFrame(gtkexplorer.GtkExplorerFrame):
        mouse_model_riscos = options.riscos_mouse

        def on_file_run(self, fsfile, shift):
            print("Run: {}".format(fsfile.filename))

    fs = fsnative.FSNative(os.path.expanduser(options.directory))
    registry = DemoExplorers(fs)
    registry.explorer_frame_cls = DemoFrame
    registry.open_window(fs.rootname())
    Gtk.main()


if __name__ == '__main__':
    sys.exit(main())
