#!/usr/bin/env python3
"""
Tests for the GTK explorer window. They need PyGObject and an X display, and report that they were not
run (and pass) if either is missing.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk
    if Gdk.Display.get_default() is None:
        raise ImportError("no display")
    import cairo
    import explorer
    import fsnative
    import gtkexplorer
except Exception as exc:
    gtkexplorer = None
    reason = str(exc)


def settle():
    while Gtk.events_pending():
        Gtk.main_iteration()


class Recording(object):
    """
    The frame, with the dialogues replaced by records of what they were asked.
    """

    def __init__(self):
        self.errors = []
        self.questions = []
        self.menus = []


@unittest.skipIf(gtkexplorer is None, "GTK is not available")
class GtkExplorerTests(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        for name in ('apple', 'Banana', 'cherry'):
            with open(os.path.join(self.root, name), 'w') as fh:
                fh.write(name * 10)
        os.mkdir(os.path.join(self.root, 'Docs'))
        with open(os.path.join(self.root, 'Docs', 'readme'), 'w') as fh:
            fh.write('hello')
        self.fs = fsnative.FSNative(self.root)
        self.registry = gtkexplorer.GtkExplorers(self.fs)
        self.rec = Recording()
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.destroy()
        shutil.rmtree(self.root)

    def open(self, dirname='/', **kwargs):
        window = self.registry.explorer_frame_cls(self.fs, dirname, explorers=self.registry, **kwargs)
        window.report_error = lambda title, message: self.rec.errors.append((title, message))
        window.confirm = lambda title, message, cancel_default=False: self.rec.questions.append(message) or True
        window.popup_menu = lambda menu, event=None: self.rec.menus.append(menu)
        window.show_window()
        settle()
        self.windows.append(window)
        return window

    def names(self, window):
        return [fsfile.leafname for fsfile in window.files]

    def click(self, window, leafname, button='left', double=False, control=False):
        index = self.names(window).index(leafname)
        (x, y, width, height) = window.panel.layout.rects[index]
        window.pointer_event(window.panel.layout.hit(x + width // 2, y + height // 2), button, double, control)

    def describe(self, menu, indent=''):
        lines = []
        for item in menu.get_children():
            if isinstance(item, Gtk.SeparatorMenuItem):
                lines.append(indent + '----')
                continue
            state = []
            if not item.get_sensitive():
                state.append('disabled')
            if isinstance(item, Gtk.CheckMenuItem):
                state.append('checked' if item.get_active() else 'unchecked')
            lines.append("{}{}{}".format(indent, item.explorer_label, ' [{}]'.format(', '.join(state)) if state else ''))
            if item.get_submenu():
                lines.extend(self.describe(item.get_submenu(), indent + '  '))
        return lines

    def test_it_shows_the_directory(self):
        window = self.open()
        self.assertEqual(window.get_title(), 'Directory: /')
        self.assertEqual(self.names(window), ['apple', 'Banana', 'cherry', 'Docs'])
        self.assertIs(self.registry.find_window('/'), window)

    def test_a_click_selects_and_replaces_the_selection(self):
        window = self.open()
        self.click(window, 'apple')
        self.click(window, 'Banana')
        self.assertEqual([f.leafname for f in window.selected_files()], ['Banana'])

    def test_adjust_toggles(self):
        window = self.open()
        self.click(window, 'apple')
        self.click(window, 'Banana', control=True)
        self.assertEqual([f.leafname for f in window.selected_files()], ['apple', 'Banana'])
        self.click(window, 'apple', control=True)
        self.assertEqual([f.leafname for f in window.selected_files()], ['Banana'])

    def test_a_click_on_the_background_deselects(self):
        window = self.open()
        self.click(window, 'apple')
        window.pointer_event(None, 'left', False, False)
        self.assertEqual(window.selected_files(), [])

    def test_the_menu_button_opens_the_menu_and_selects_the_icon(self):
        window = self.open()
        self.click(window, 'cherry', button='right')
        self.assertEqual([f.leafname for f in window.selected_files()], ['cherry'])
        self.assertEqual(len(self.rec.menus), 1)
        lines = self.describe(self.rec.menus[0])
        self.assertIn("File 'cherry'", lines)
        self.assertIn('  Info', lines)
        # The native file system cannot change anything
        self.assertIn('  Delete [disabled]', lines)

    def test_the_riscos_mouse_model_uses_the_middle_button_for_the_menu(self):
        class RiscosFrame(gtkexplorer.GtkExplorerFrame):
            mouse_model_riscos = True
        self.registry.explorer_frame_cls = RiscosFrame
        window = self.open()
        self.click(window, 'apple', button='right')
        self.click(window, 'cherry', button='right')
        self.assertEqual([f.leafname for f in window.selected_files()], ['apple', 'cherry'])
        self.assertEqual(self.rec.menus, [])
        self.click(window, 'apple', button='middle')
        self.assertEqual(len(self.rec.menus), 1)

    def test_a_double_click_on_a_directory_opens_it(self):
        window = self.open()
        self.click(window, 'Docs', double=True)
        settle()
        child = self.registry.find_window('/Docs')
        self.assertIsNotNone(child)
        self.windows.append(child)
        self.assertEqual(self.names(child), ['readme'])

    def test_adjust_double_click_replaces_the_window(self):
        window = self.open()
        self.click(window, 'Docs', double=True, control=True)
        settle()
        self.assertEqual(window.dirname, '/Docs')
        self.assertEqual(self.names(window), ['readme'])
        self.assertIs(self.registry.find_window('/Docs'), window)
        self.assertIsNone(self.registry.find_window('/'))

    def test_the_sort_order_and_display_format_change(self):
        window = self.open()
        window.set_sort_order('size')
        self.assertEqual(window.sort_order, 'size')
        window.set_display_format('fullinfo')
        self.assertEqual(window.display_format, 'fullinfo')
        self.assertGreater(window.panel.layout.cell_width, 300)

    def test_a_directory_that_has_gone_is_reported_and_kept(self):
        window = self.open('/Docs')
        self.click(window, 'readme')
        shutil.rmtree(os.path.join(self.root, 'Docs'))
        window.refresh_directory()
        self.assertEqual(len(self.rec.errors), 1)
        self.assertEqual(self.rec.errors[0][0], 'Failed to read directory')
        self.assertEqual(self.names(window), ['readme'])
        self.assertEqual([f.leafname for f in window.selected_files()], ['readme'])
        self.assertEqual(window.get_title(), 'Directory: /Docs (not available)')

    def test_a_directory_that_cannot_be_opened_is_reported_and_there_is_no_window(self):
        window = self.open()
        window.open_explorer('/nothere')
        self.assertEqual(self.rec.errors[0][0], 'Failed to open directory')
        self.assertIsNone(self.registry.find_window('/nothere'))

    def test_the_information_window(self):
        window = self.open()
        self.click(window, 'apple')
        window.on_selection_info()
        info = self.registry.find_fileinfo('/apple')
        self.assertIsNotNone(info)
        self.windows.append(info)
        self.assertEqual(info.get_title(), 'File info: /apple')
        window.on_selection_info()
        self.assertEqual(len(self.registry.open_fileinfos), 1)

    def test_every_format_draws_with_the_icons_and_without(self):
        window = self.open()
        self.click(window, 'apple')
        for fallback in (False, True):
            if fallback:
                window.icons.pixbufs = dict(((filetype, height), None)
                                            for filetype in (0x1000, 0xFFD, 0xFFF)
                                            for height in range(1, 100))
                window.icons.load = lambda filetype, height: None
            for display_format in ('large', 'small', 'fullinfo'):
                window.set_display_format(display_format)
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 640, 480)
                window.panel.on_draw(window.panel, cairo.Context(surface))

    def test_the_icons_are_scaled_to_the_height(self):
        cache = gtkexplorer.IconCache()
        pixbuf = cache.pixbuf(explorer.FILETYPE_DIRECTORY, 36)
        if pixbuf is None:
            self.skipTest("SVG icons cannot be loaded")
        self.assertEqual(pixbuf.get_height(), 36)
        self.assertGreater(pixbuf.get_width(), 20)
        # An icon which has no file of its own gets the unknown icon
        self.assertIsNotNone(cache.pixbuf(0x123, 36))


if __name__ == '__main__':
    unittest.main()
