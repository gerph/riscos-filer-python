#!/usr/bin/env python3
"""
Tests for the descriptions of files in the file system module. No toolkit is needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fs


class FakeFS(fs.FSBase):
    def rootname(self):
        return '/'


class FormatTests(unittest.TestCase):

    def file(self, **kwargs):
        return fs.FSFileBase(FakeFS(), '/file', **kwargs)

    def test_a_timestamp_is_shown_in_centiseconds(self):
        # 1000.42 seconds after the epoch
        self.assertEqual(self.file(epochtime=1000.42).format_timestamp(), '00:16:40.42 01 Jan 1970')

    def test_a_whole_second_has_two_digits_of_centiseconds(self):
        self.assertEqual(self.file(epochtime=1000).format_timestamp(), '00:16:40.00 01 Jan 1970')
        self.assertEqual(self.file(epochtime=1000.05).format_timestamp(), '00:16:40.05 01 Jan 1970')

    def test_no_time_is_unknown(self):
        self.assertEqual(self.file().format_timestamp(), '00:00:00.00 01 Jan 1970')

    def test_sizes(self):
        self.assertEqual(self.file(size=12).format_size(), '12 bytes')
        self.assertEqual(self.file().format_size(), 'Unknown')

    def test_types(self):
        self.assertEqual(self.file().format_filetype(), '&FFD')


if __name__ == '__main__':
    unittest.main()
