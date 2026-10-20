#!/usr/bin/env python3
"""
Tests for the registry of open explorer windows, with windows that only record what they are told.

No toolkit is needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import explorers


class FakeFS(object):
    def normalise_name(self, name):
        return name.lower()


class FakeWindow(object):
    """
    Records what it is asked, and tells the registry when it closes, as a real window does.
    """

    def __init__(self, registry, name, fileinfo=False):
        self.registry = registry
        self.name = name
        self.fileinfo = fileinfo
        self.events = []

    def show_window(self):
        self.events.append('show')

    def raise_window(self):
        self.events.append('raise')

    def close_window(self):
        self.events.append('close')
        if self.fileinfo:
            self.registry.fileinfo_has_closed(self.name)
        else:
            self.registry.window_has_closed(self.name)


class FakeExplorers(explorers.FSExplorersBase):
    def __init__(self, fs):
        super(FakeExplorers, self).__init__(fs)
        self.created = []
        self.fail = False

    def create_explorer(self, dirname, pos=None, display_format=None, sort_order=None):
        if self.fail:
            return None
        window = FakeWindow(self, dirname)
        self.created.append((dirname, pos, display_format, sort_order))
        self.window_has_opened(dirname, window)
        return window

    def create_fileinfo(self, filename, pos=None):
        window = FakeWindow(self, filename, fileinfo=True)
        self.created.append((filename, pos))
        self.fileinfo_has_opened(filename, window)
        return window


class ExplorersTests(unittest.TestCase):

    def setUp(self):
        self.registry = FakeExplorers(FakeFS())

    def test_a_directory_is_opened_and_shown(self):
        window = self.registry.open_window('$.Docs', pos=(1, 2), display_format='small', sort_order='size')
        self.assertEqual(window.events, ['show'])
        self.assertEqual(self.registry.created, [('$.Docs', (1, 2), 'small', 'size')])
        self.assertIs(self.registry.find_window('$.Docs'), window)

    def test_the_name_is_compared_ignoring_case(self):
        window = self.registry.open_window('$.Docs')
        self.assertIs(self.registry.find_window('$.DOCS'), window)

    def test_opening_an_open_directory_raises_that_window(self):
        window = self.registry.open_window('$.Docs')
        self.assertIs(self.registry.open_window('$.docs'), window)
        self.assertEqual(window.events, ['show', 'raise'])
        self.assertEqual(len(self.registry.created), 1)

    def test_a_closed_window_is_forgotten(self):
        window = self.registry.open_window('$.Docs')
        window.close_window()
        self.assertIsNone(self.registry.find_window('$.Docs'))
        self.registry.open_window('$.Docs')
        self.assertEqual(len(self.registry.created), 2)

    def test_a_second_window_for_a_directory_closes_the_first(self):
        first = FakeWindow(self.registry, '$.Docs')
        second = FakeWindow(self.registry, '$.Docs')
        self.registry.window_has_opened('$.Docs', first)
        self.registry.window_has_opened('$.Docs', second)
        self.assertEqual(first.events, ['close'])
        self.assertIs(self.registry.find_window('$.Docs'), second)

    def test_registering_the_same_window_again_does_not_close_it(self):
        window = FakeWindow(self.registry, '$.Docs')
        self.registry.window_has_opened('$.Docs', window)
        self.registry.window_has_opened('$.Docs', window)
        self.assertEqual(window.events, [])

    def test_a_window_which_could_not_be_made_is_not_shown(self):
        self.registry.fail = True
        self.assertIsNone(self.registry.open_window('$.Docs'))
        self.assertIsNone(self.registry.find_window('$.Docs'))

    def test_closing_a_name_which_is_not_open_is_ignored(self):
        self.registry.window_has_closed('$.Nothere')
        self.registry.fileinfo_has_closed('$.Nothere')

    def test_information_windows_are_tracked_apart_from_explorers(self):
        explorer_window = self.registry.open_window('$.Docs')
        info = self.registry.open_fileinfo('$.Docs')
        self.assertIsNot(info, explorer_window)
        self.assertIs(self.registry.open_fileinfo('$.docs'), info)
        self.assertEqual(info.events, ['show', 'raise'])
        info.close_window()
        self.assertIsNone(self.registry.find_fileinfo('$.Docs'))
        self.assertIs(self.registry.find_window('$.Docs'), explorer_window)

    def test_a_toolkit_must_make_the_windows(self):
        registry = explorers.FSExplorersBase(FakeFS())
        with self.assertRaises(NotImplementedError):
            registry.open_window('$')
        with self.assertRaises(NotImplementedError):
            registry.open_fileinfo('$.file')


if __name__ == '__main__':
    unittest.main()
