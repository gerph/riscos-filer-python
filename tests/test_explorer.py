#!/usr/bin/env python3
"""
Tests for the model of a file explorer window, against a file system held in memory.

No toolkit is needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fs
import explorer


class MemFile(fs.FSFileBase):
    def __init__(self, memfs, filename, entry):
        super(MemFile, self).__init__(memfs, filename, size=entry['size'], epochtime=entry['epochtime'])
        self.entry = entry

    def isdir(self):
        return self.entry['dir']

    def filetype(self):
        return self.TYPE_DIRECTORY if self.entry['dir'] else self.entry['filetype']

    def can_delete(self):
        return bool(self.fs.can_delete() and self.entry['deletable'] and self.parent().is_writeable())

    def do_delete(self):
        self.fs.remove(self.filename)


class MemDir(fs.FSDirectoryBase):
    def get_filelist(self):
        self.fs.listings.append(self.dirname)
        return self.fs.names_in(self.dirname)

    def get_file(self, leafname):
        filename = self.fs.join(self.dirname, leafname)
        return MemFile(self.fs, filename, self.fs.nodes[self.fs.normalise_name(filename)])

    def is_writeable(self):
        return self.fs.writeable

    def do_mkdir(self, leafname):
        self.fs.add(self.fs.join(self.dirname, leafname), dir=True)

    def do_rename(self, source_leafname, dest_leafname):
        self.fs.move(self.fs.join(self.dirname, source_leafname),
                     self.fs.join(self.dirname, dest_leafname))


class MemFS(fs.FSBase):
    """
    RISC OS style names ('$.dir.file'), case insensitive, with everything in a dictionary.
    """
    dirsep = '.'
    supports_mkdir = True
    supports_delete = True
    supports_rename = True

    def __init__(self):
        super(MemFS, self).__init__()
        self.nodes = {}
        self.writeable = True
        self.listings = []
        self.add('$', dir=True)

    def rootname(self):
        return '$'

    def get_dir(self, dirname, parent_fsdir=None):
        return MemDir(self, parent_fsdir, dirname)

    def add(self, filename, dir=False, size=10, filetype=0xFFF, epochtime=1000, deletable=True):
        self.nodes[self.normalise_name(filename)] = {
                'name': filename, 'dir': dir, 'size': size, 'filetype': filetype,
                'epochtime': epochtime, 'deletable': deletable}

    def remove(self, filename):
        prefix = self.normalise_name(filename)
        for key in list(self.nodes):
            if key == prefix or key.startswith(prefix + '.'):
                del self.nodes[key]

    def move(self, source, dest):
        entry = self.nodes.pop(self.normalise_name(source))
        entry['name'] = dest
        self.nodes[self.normalise_name(dest)] = entry

    def names_in(self, dirname):
        key = self.normalise_name(dirname)
        if key == '':
            # Making a directory also reads its parents, up to the empty name
            return []
        if key not in self.nodes:
            raise fs.FSReadFailedError("Directory '{}' not found".format(dirname))
        names = []
        for (nodekey, entry) in self.nodes.items():
            (parent, leaf) = self.dirandleafname(entry['name'])
            if self.normalise_name(parent) == key and leaf:
                names.append(leaf)
        return names


def make_fs():
    memfs = MemFS()
    memfs.add('$.Zebra', size=300, filetype=0xFFF, epochtime=3000)
    memfs.add('$.apple', size=100, filetype=0xFF0, epochtime=2000)
    memfs.add('$.Mango', size=200, filetype=0xFFD, epochtime=1000)
    memfs.add('$.Docs', dir=True, size=0, epochtime=500)
    memfs.add('$.Docs.readme', size=5)
    memfs.add('$.Locked', size=7, deletable=False)
    return memfs


class Recorder(object):
    def __init__(self, answer=True):
        self.errors = []
        self.questions = []
        self.answer = answer

    def report_error(self, title, message):
        self.errors.append((title, message))

    def confirm(self, title, message, cancel_default=False):
        self.questions.append((title, message, cancel_default))
        return self.answer


def make_model(memfs=None, dirname='$', **kwargs):
    recorder = Recorder(kwargs.pop('answer', True))
    kwargs.setdefault('report_error', recorder.report_error)
    kwargs.setdefault('confirm', recorder.confirm)
    model = explorer.FSExplorerModel(memfs or make_fs(), dirname, **kwargs)
    return (model, recorder)


def names(files):
    return [fsfile.leafname for fsfile in files]


class ListingTests(unittest.TestCase):

    def test_sorted_by_name_ignoring_case(self):
        (model, _) = make_model()
        self.assertEqual(names(model.files), ['apple', 'Docs', 'Locked', 'Mango', 'Zebra'])

    def test_sorted_by_size_with_directories_as_zero(self):
        (model, _) = make_model(sort_order='size')
        self.assertEqual(names(model.files), ['Docs', 'Locked', 'apple', 'Mango', 'Zebra'])

    def test_sorted_by_filetype_with_directories_first(self):
        (model, _) = make_model(sort_order='filetype')
        # Locked and Zebra are the same type, so they stay in leafname order
        self.assertEqual(names(model.files), ['Docs', 'apple', 'Mango', 'Locked', 'Zebra'])

    def test_sorted_by_timestamp(self):
        (model, _) = make_model(sort_order='timestamp')
        # Locked and Mango share a time, so they stay in leafname order
        self.assertEqual(names(model.files), ['Docs', 'Locked', 'Mango', 'apple', 'Zebra'])

    def test_an_unknown_sort_order_leaves_the_files_by_leafname(self):
        (model, _) = make_model(sort_order='nonsense')
        self.assertEqual(names(model.files), ['Docs', 'Locked', 'Mango', 'Zebra', 'apple'])

    def test_the_defaults(self):
        (model, _) = make_model()
        self.assertEqual((model.display_format, model.sort_order), ('large', 'name'))
        self.assertEqual(model.title(), 'Directory: $')
        self.assertFalse(model.stale)

    def test_the_title_can_be_overridden(self):
        (model, _) = make_model(title_text='My files')
        self.assertEqual(model.title(), 'My files')

    def test_changing_the_sort_order_does_not_read_the_directory_again(self):
        (model, _) = make_model()
        reads = len(model.fs.listings)
        self.assertTrue(model.set_sort_order('size'))
        self.assertFalse(model.set_sort_order('size'))
        self.assertEqual(names(model.files)[:2], ['Docs', 'Locked'])
        self.assertEqual(len(model.fs.listings), reads)

    def test_changing_the_display_format(self):
        (model, _) = make_model()
        self.assertTrue(model.set_display_format('fullinfo'))
        self.assertFalse(model.set_display_format('fullinfo'))
        self.assertEqual(model.display_format, 'fullinfo')

    def test_a_directory_which_cannot_be_read_raises_from_the_constructor(self):
        with self.assertRaises(fs.FSReadFailedError):
            make_model(dirname='$.nothere')

    def test_a_subdirectory_is_listed(self):
        (model, _) = make_model(dirname='$.Docs')
        self.assertEqual(names(model.files), ['readme'])

    def test_the_parent_directory(self):
        self.assertIsNone(make_model()[0].parent_dirname())
        self.assertEqual(make_model(dirname='$.Docs')[0].parent_dirname(), '$')


class SelectionTests(unittest.TestCase):

    def test_select_and_deselect(self):
        (model, _) = make_model()
        self.assertTrue(model.select('Mango'))
        self.assertFalse(model.select('Mango'))
        self.assertTrue(model.is_selected('Mango'))
        self.assertTrue(model.select('Mango', False))
        self.assertFalse(model.select('Mango', False))
        self.assertFalse(model.is_selected('Mango'))

    def test_toggle(self):
        (model, _) = make_model()
        self.assertTrue(model.select('apple', None))
        self.assertTrue(model.is_selected('apple'))
        self.assertTrue(model.select('apple', None))
        self.assertFalse(model.is_selected('apple'))

    def test_a_file_which_is_not_shown_cannot_be_selected(self):
        (model, _) = make_model()
        self.assertFalse(model.select('nothere'))
        self.assertEqual(model.selected(), [])

    def test_the_selection_is_in_the_display_order(self):
        (model, _) = make_model()
        model.select('Zebra')
        model.select('apple')
        self.assertEqual(names(model.selected()), ['apple', 'Zebra'])
        model.set_sort_order('size')
        self.assertEqual(names(model.selected()), ['apple', 'Zebra'])

    def test_select_all_and_deselect_all(self):
        (model, _) = make_model()
        self.assertTrue(model.select_all())
        self.assertFalse(model.select_all())
        self.assertEqual(len(model.selected()), 5)
        self.assertTrue(model.deselect_all())
        self.assertFalse(model.deselect_all())
        self.assertEqual(model.selected(), [])

    def test_the_selection_is_kept_when_the_directory_is_refreshed(self):
        (model, _) = make_model()
        model.select('Mango')
        model.select('Zebra')
        model.fs.add('$.Banana')
        model.fs.remove('$.Zebra')
        self.assertTrue(model.refresh())
        self.assertEqual(names(model.files), ['apple', 'Banana', 'Docs', 'Locked', 'Mango'])
        self.assertEqual(names(model.selected()), ['Mango'])
        self.assertFalse(model.is_selected('Zebra'))

    def test_the_selection_is_cleared_by_a_change_of_directory(self):
        (model, _) = make_model()
        model.select('Mango')
        self.assertTrue(model.change_directory('$.Docs'))
        self.assertEqual(model.selected(), [])
        self.assertEqual((model.dirname, names(model.files)), ('$.Docs', ['readme']))
        self.assertEqual(model.title(), 'Directory: $.Docs')


class VanishedDirectoryTests(unittest.TestCase):

    def test_a_failed_refresh_is_reported_and_keeps_the_listing(self):
        (model, recorder) = make_model(dirname='$.Docs')
        model.select('readme')
        model.fs.remove('$.Docs')
        self.assertTrue(model.refresh())
        self.assertTrue(model.stale)
        self.assertIn('not found', model.error)
        self.assertEqual(recorder.errors, [('Failed to read directory', model.error)])
        self.assertEqual(names(model.files), ['readme'])
        self.assertEqual(names(model.selected()), ['readme'])

    def test_a_second_failed_refresh_changes_nothing_to_draw(self):
        (model, recorder) = make_model(dirname='$.Docs')
        model.fs.remove('$.Docs')
        model.refresh()
        self.assertFalse(model.refresh())
        self.assertEqual(len(recorder.errors), 2)

    def test_the_window_can_still_be_used_when_stale(self):
        (model, recorder) = make_model(dirname='$.Docs')
        model.fs.remove('$.Docs')
        model.refresh()
        self.assertTrue(model.set_sort_order('size'))
        model.select_all()
        self.assertEqual(names(model.selected()), ['readme'])
        self.assertEqual(model.parent_dirname(), '$')
        self.assertIsInstance(model.capabilities(), explorer.Capabilities)

    def test_a_refresh_recovers_when_the_directory_comes_back(self):
        (model, recorder) = make_model(dirname='$.Docs')
        model.fs.remove('$.Docs')
        model.refresh()
        model.fs.add('$.Docs', dir=True)
        model.fs.add('$.Docs.other')
        self.assertTrue(model.refresh())
        self.assertFalse(model.stale)
        self.assertIsNone(model.error)
        self.assertEqual(names(model.files), ['other'])

    def test_a_directory_renamed_behind_the_window_is_a_failed_refresh(self):
        (model, recorder) = make_model(dirname='$.Docs')
        model.fs.move('$.Docs', '$.Papers')
        model.fs.move('$.Docs.readme', '$.Papers.readme')
        model.refresh()
        self.assertTrue(model.stale)
        self.assertEqual(len(recorder.errors), 1)

    def test_changing_to_a_missing_directory_keeps_the_window_as_it_was(self):
        (model, recorder) = make_model()
        model.select('Mango')
        self.assertFalse(model.change_directory('$.nothere'))
        self.assertEqual(model.dirname, '$')
        self.assertEqual(model.title(), 'Directory: $')
        self.assertEqual(names(model.selected()), ['Mango'])
        self.assertEqual(len(model.files), 5)
        self.assertEqual(recorder.errors[0][0], 'Failed to read directory')
        self.assertFalse(model.stale)


class CapabilityTests(unittest.TestCase):

    def test_nothing_selected(self):
        (model, _) = make_model()
        caps = model.capabilities()
        self.assertEqual(caps.selection_label, "File ''")
        self.assertFalse(caps.selection_enabled)
        self.assertFalse(caps.clear_enabled)
        self.assertFalse(caps.rename_enabled)
        self.assertFalse(caps.delete_enabled)
        self.assertTrue(caps.mkdir_enabled)
        self.assertIsNone(caps.parent)
        # The view items are enabled when the menu is not over a directory
        self.assertTrue(caps.view_enabled)

    def test_a_file_selected(self):
        (model, _) = make_model()
        model.select('Mango')
        caps = model.capabilities(model.file('Mango'))
        self.assertEqual(caps.selection_label, "File 'Mango'")
        self.assertTrue(caps.selection_enabled and caps.clear_enabled)
        self.assertTrue(caps.rename_enabled and caps.delete_enabled)
        self.assertTrue(caps.view_enabled)

    def test_a_directory_selected(self):
        (model, _) = make_model()
        model.select('Docs')
        caps = model.capabilities(model.file('Docs'))
        self.assertEqual(caps.selection_label, "Directory 'Docs'")
        self.assertFalse(caps.view_enabled)

    def test_several_selected(self):
        (model, _) = make_model()
        model.select('Mango')
        model.select('Docs')
        caps = model.capabilities(model.file('Docs'))
        self.assertEqual(caps.selection_label, "Selection")
        self.assertFalse(caps.rename_enabled)
        self.assertTrue(caps.delete_enabled)
        # The view items follow the file that the menu was opened over
        self.assertFalse(caps.view_enabled)
        self.assertTrue(model.capabilities(model.file('Mango')).view_enabled)

    def test_delete_needs_just_one_deletable_file(self):
        (model, _) = make_model()
        model.select('Locked')
        self.assertFalse(model.capabilities().delete_enabled)
        model.select('Mango')
        self.assertTrue(model.capabilities().delete_enabled)

    def test_a_read_only_directory_allows_nothing_which_changes_it(self):
        memfs = make_fs()
        memfs.writeable = False
        (model, _) = make_model(memfs)
        model.select('Mango')
        caps = model.capabilities()
        self.assertFalse(caps.mkdir_enabled)
        self.assertFalse(caps.rename_enabled)
        self.assertFalse(caps.delete_enabled)

    def test_a_window_without_the_operations_does_not_show_them(self):
        (model, _) = make_model(support_mkdir=False, support_delete=False, support_rename=False,
                                support_refresh=False)
        model.select('Mango')
        caps = model.capabilities()
        self.assertFalse(caps.mkdir_shown or caps.rename_shown or caps.delete_shown or caps.refresh_shown)
        self.assertFalse(caps.mkdir_enabled or caps.rename_enabled or caps.delete_enabled)

    def test_the_parent_is_offered_below_the_root(self):
        (model, _) = make_model(dirname='$.Docs')
        self.assertEqual(model.capabilities().parent, '$')


class MouseTests(unittest.TestCase):

    def buttons(self, riscos):
        (model, _) = make_model(mouse_model_riscos=riscos)
        click = model.click_to_button
        return [
            click('left'), click('left', control=True), click('right'), click('middle'),
            click('left', double=True), click('right', double=True),
            click('left', double=True, control=True), click('middle', double=True),
        ]

    def test_the_non_riscos_mouse_model(self):
        self.assertEqual(self.buttons(False),
                         ['SELECT', 'ADJUST', 'MENU', 'MENU', 'D-SELECT', 'D-MENU', 'D-ADJUST', 'NONE'])

    def test_the_riscos_mouse_model(self):
        self.assertEqual(self.buttons(True),
                         ['SELECT', 'SELECT', 'ADJUST', 'MENU', 'D-SELECT', 'D-ADJUST', 'D-SELECT', 'NONE'])


class ActivationTests(unittest.TestCase):

    def test_activating_a_directory_opens_it(self):
        (model, _) = make_model()
        activation = model.activate(model.file('Docs'))
        self.assertEqual(activation, explorer.Activation(explorer.OPEN_DIRECTORY, '$.Docs', False, False))

    def test_activating_a_directory_with_adjust_replaces_the_window(self):
        (model, _) = make_model()
        self.assertTrue(model.activate(model.file('Docs'), close=True).close)

    def test_activating_a_file_runs_it(self):
        (model, _) = make_model()
        activation = model.activate(model.file('Mango'), shift=True)
        self.assertEqual(activation.action, explorer.RUN_FILE)
        self.assertIs(activation.target, model.file('Mango'))
        self.assertTrue(activation.shift)


class OperationTests(unittest.TestCase):

    def test_mkdir(self):
        (model, recorder) = make_model()
        self.assertTrue(model.mkdir('New'))
        self.assertIn('New', names(model.files))
        self.assertTrue(model.file('New').isdir())
        self.assertEqual(recorder.errors, [])

    def test_mkdir_in_a_read_only_directory_is_reported(self):
        memfs = make_fs()
        memfs.writeable = False
        (model, recorder) = make_model(memfs)
        self.assertFalse(model.mkdir('New'))
        self.assertEqual(recorder.errors[0][0], 'Failed to create directory')
        self.assertNotIn('New', names(model.files))

    def test_rename(self):
        (model, recorder) = make_model()
        model.select('Mango')
        self.assertTrue(model.rename('Mango', 'Papaya'))
        self.assertEqual(names(model.files), ['apple', 'Docs', 'Locked', 'Papaya', 'Zebra'])
        # The selection followed the old name, which has gone
        self.assertEqual(model.selected(), [])
        self.assertEqual(recorder.errors, [])

    def test_rename_onto_an_existing_file_is_reported(self):
        (model, recorder) = make_model()
        self.assertFalse(model.rename('Mango', 'apple'))
        self.assertEqual(recorder.errors[0][0], 'Failed to rename')
        self.assertIn('already exists', recorder.errors[0][1])
        self.assertIn('Mango', names(model.files))

    def test_rename_of_a_missing_file_is_reported(self):
        (model, recorder) = make_model()
        self.assertFalse(model.rename('Nothere', 'Other'))
        self.assertEqual(recorder.errors[0][0], 'Failed to rename')

    def test_delete_asks_first(self):
        (model, recorder) = make_model()
        model.select('Mango')
        self.assertTrue(model.delete())
        self.assertEqual(recorder.questions,
                         [('Confirm delete object', "Are you sure you want to delete '$.Mango'?", True)])
        self.assertNotIn('Mango', names(model.files))

    def test_delete_is_not_done_if_not_confirmed(self):
        (model, recorder) = make_model(answer=False)
        model.select('Mango')
        self.assertFalse(model.delete())
        self.assertIn('Mango', names(model.files))

    def test_delete_by_name_without_asking(self):
        (model, recorder) = make_model()
        self.assertTrue(model.delete(['Mango', 'nothere'], ask=False))
        self.assertEqual(recorder.questions, [])
        self.assertNotIn('Mango', names(model.files))

    def test_a_file_which_will_not_delete_is_reported_and_the_rest_deleted(self):
        (model, recorder) = make_model()
        model.select('Locked')
        model.select('Mango')
        self.assertTrue(model.delete())
        self.assertEqual(len(recorder.questions), 2)
        self.assertEqual(recorder.errors[0][0], 'Failed to delete')
        self.assertEqual(names(model.files), ['apple', 'Docs', 'Locked', 'Zebra'])
        # What was selected and is still there stays selected
        self.assertEqual(names(model.selected()), ['Locked'])

    def test_the_defaults_report_nothing_and_confirm_nothing(self):
        model = explorer.FSExplorerModel(make_fs(), '$')
        model.select('Mango')
        self.assertFalse(model.delete())
        self.assertFalse(model.rename('Mango', 'apple'))
        self.assertIn('Mango', names(model.files))


class CascadeTests(unittest.TestCase):

    def test_successive_windows_step_down_and_across(self):
        self.assertEqual([explorer.cascade_offset(i) for i in range(3)],
                         [(16, 32), (32, 64), (48, 96)])

    def test_the_cascade_wraps(self):
        self.assertEqual(explorer.cascade_offset(8), (32, 48))
        self.assertEqual(explorer.cascade_offset(48), (16, 32))

    def test_the_steps_can_be_changed(self):
        self.assertEqual(explorer.cascade_offset(1, offset_x=10, offset_y=20), (20, 40))


class IndependenceTests(unittest.TestCase):

    def test_the_model_needs_no_toolkit(self):
        for name in ('wx', 'gi'):
            self.assertNotIn(name, sys.modules)


if __name__ == '__main__':
    unittest.main()
