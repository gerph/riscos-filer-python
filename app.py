#!/usr/bin/env python

import os.path

import wx

import fs
import fsnative
import fsexplorer


class DemoFrame(wx.Frame):
    """ This window displays a button """
    def __init__(self, title="Example of RISC OS Filer"):
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

        self.explorers = fsexplorer.FSExplorers()
        self.fs = fsnative.FSNative(os.path.expanduser('~'))

        win = fsexplorer.FSExplorerFrame(self.fs, '/', self, -1, size=(640, 480), explorers=self.explorers)
        win.Show(True)

    def OnQuit(self,Event):
        self.Destroy()

    def OnOpen(self,Event):
        win = fsexplorer.FSExplorerFrame(self.fs, '/', self, -1, size=(640, 480), explorers=self.explorers)
        win.Show(True)


class MyApp(wx.App):
    def __init__(self, *args, **kwargs):
        super(MyApp, self).__init__(*args, **kwargs)

    def OnInit(self):

        frame = DemoFrame()
        frame.Show()

        return True


app = MyApp(False)
app.MainLoop()
