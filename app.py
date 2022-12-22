#!/usr/bin/env python
"""
Example application showing the behaviour of the filer interface.
"""

import argparse
import os.path
import sys

import wx

import fs
import fsnative
import fsexplorer


show_inspector = True


class DemoFrame(wx.Frame):
    """ This window displays a button """
    def __init__(self, title="Example of RISC OS Filer", directory='~'):
        super(DemoFrame, self).__init__(None , -1, title)

        MenuBar = wx.MenuBar()

        FileMenu = wx.Menu()

        item = FileMenu.Append(wx.ID_EXIT, "&Exit")
        self.Bind(wx.EVT_MENU, self.OnQuit, item)

        item = FileMenu.Append(wx.ID_ANY, "&Open root")
        self.Bind(wx.EVT_MENU, self.OnOpen, item)

        MenuBar.Append(FileMenu, "&File")

        self.SetMenuBar(MenuBar)

        vbox = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(self, label="Quit")
        btn.Bind(wx.EVT_BUTTON, self.OnQuit )
        vbox.Add(btn)

        btn = wx.Button(self, label="Open root")
        btn.Bind(wx.EVT_BUTTON, self.OnOpen )
        vbox.Add(btn)

        self.SetSizer(vbox)

        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.fs = fsnative.FSNative(os.path.expanduser(directory))
        self.explorers = fsexplorer.FSExplorers(self.fs)

        win = fsexplorer.FSExplorerFrame(self.fs, '/', self, -1, size=(640, 480), explorers=self.explorers)
        win.Show(True)

    def OnQuit(self,Event):
        self.Destroy()

    def OnOpen(self,Event):
        win = fsexplorer.FSExplorerFrame(self.fs, '/', self, -1, size=(640, 480), explorers=self.explorers)
        win.Show(True)


class MyApp(wx.App):
    def __init__(self, *args, **kwargs):
        self.options = kwargs.pop('options')
        super(MyApp, self).__init__(*args, **kwargs)

    def OnInit(self):

        frame = DemoFrame(directory=self.options.directory)
        frame.Show()

        if self.options.inspector:
            import wx.lib.inspection
            wx.lib.inspection.InspectionTool().Show()

        return True


def setup_argparse():
    parser = argparse.ArgumentParser(usage="%s [<options>] [<directory>]" % (os.path.basename(sys.argv[0]),))
    parser.add_argument('--inspector', action='store_true', default=False,
                        help="Displat the WxPython inspector")
    parser.add_argument('directory', nargs='?', default='~',
                        help="Directory to display")

    return parser


def main():
    parser = setup_argparse()

    options = parser.parse_args()

    app = MyApp(options=options)
    app.MainLoop()


if __name__ == '__main__':
    sys.exit(main())
