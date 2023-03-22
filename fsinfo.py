"""
Interfaces for file information windows.
"""

import sys

import wx


class FSFileInfoPanel(wx.Panel):

    outer_border = 8
    inner_spacing = 4

    def __init__(self, parent, fsfile):
        self.parent = parent
        self.fsfile = fsfile

        super(FSFileInfoPanel, self).__init__(parent, -1, style=wx.SUNKEN_BORDER)

        self.list = wx.ListCtrl(self,
                                style=wx.LC_REPORT
                                      | wx.LC_NO_HEADER
                                      #| wx.LC_VRULES
                                      )

        bgcolour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_APPWORKSPACE)
        self.SetBackgroundColour(bgcolour)

        self.field_generators = [
                ('Leafname', lambda fsfile: fsfile.leafname),
                ('File type', lambda fsfile: fsfile.format_filetype()),
                ('Size', lambda fsfile: fsfile.format_size()),
                ('Date/time', lambda fsfile: fsfile.format_timestamp()),
            ]

        # will be overridden in populate_info
        self.text_height = 8

        self.scrollsize_x = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
        self.scrollsize_y = wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y)

        self.populate_info()

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, self.outer_border)
        self.SetSizer(self.sizer)
        self.SetAutoLayout(True)

    def GetBestSize(self):
        if False:
            width = self.list.GetColumnWidth(0) + self.inner_spacing + self.list.GetColumnWidth(1)
            height = (self.list.GetUserLineHeight() + 1) * self.list.GetItemCount()
            return wx.Size(int(width + self.outer_border * 2),
                           int(height + self.outer_border * 2))
        else:
            # The bottom item
            rect = self.list.GetItemRect(self.list.GetItemCount() - 1)

            width = rect.Width + self.inner_spacing
            height = (rect.Height + self.inner_spacing) * self.list.GetItemCount()

            return wx.Size(int(width + self.outer_border * 2),
                           int(height + self.outer_border * 2))

    def SetBackgroundColour(self, colour):
        super(FSFileInfoPanel, self).SetBackgroundColour(colour)
        self.list.SetBackgroundColour(colour)

    def populate_info(self):

        self.list.InsertColumn(0, "Property", wx.LIST_FORMAT_RIGHT)
        self.list.InsertColumn(1, "Value")

        dc = wx.ScreenDC()
        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))

        maxfieldwidth = 96
        maxvaluewidth = 96
        maxheight = 8
        index = 0
        fields = []
        for field, generator in self.field_generators:
            value = generator(self.fsfile)
            field_size = dc.GetTextExtent(field)
            value_size = dc.GetTextExtent(value)
            maxfieldwidth = max(maxfieldwidth, field_size[0])
            maxvaluewidth = max(maxvaluewidth, value_size[0])
            #print("Size field %r/%r => %r/%r" % (field, value, field_size, value_size))
            maxheight = max(maxheight, field_size[1])
            fields.append((field, value))

        self.text_height = maxheight

        for field, value in fields:
            self.list.InsertItem(index, field)
            self.list.SetItem(index, 1, value)
            index += 1

        self.list.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self.list.SetColumnWidth(1, wx.LIST_AUTOSIZE)


class FSFileInfoFrame(wx.Frame):

    # Allow more space for the title text (eg for the buttons in the title)
    title_extra_size = 80
    frame_border = 3
    if sys.platform == 'win32':
        frame_border += 6

    def __init__(self, parent, fsfile, *args, **kwargs):
        self.parent = parent
        self.fsfile = fsfile
        self.explorers = kwargs.pop('explorers', None)
        kwargs['title'] = "File info: {}".format(fsfile.filename)

        super(FSFileInfoFrame, self).__init__(None, *args, **kwargs)

        self.panel = FSFileInfoPanel(self, fsfile)

        #print("Best = %r, client= %r, size=%r, virtual=%r" % (self.panel.GetBestSize(), self.panel.GetClientSize(), self.panel.GetSize(), self.panel.GetVirtualSize()))
        size = self.panel.GetBestSize()
        # Allow for the size of the title
        dc = wx.ScreenDC()
        title_size = dc.GetTextExtent(kwargs['title'])
        size = wx.Size(int(max(title_size[0] + self.title_extra_size, size[0] + self.frame_border)),
                       int(size[1] + self.frame_border))

        #print("title = %r, best_size = %r" % (title_size, size))

        self.SetMaxClientSize(size)
        self.SetClientSize(size)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.panel, 1, wx.EXPAND | wx.ALL, 0)
        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        if self.explorers:
            self.explorers.fileinfo_has_opened(self.fsfile.filename, self)

    def on_close(self, event):
        if self.explorers:
            self.explorers.fileinfo_has_closed(self.fsfile.filename)
        # This event is informational, so we pass on.
        event.Skip()
