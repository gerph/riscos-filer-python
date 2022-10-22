"""
Interfaces for file information windows.
"""

import wx
import wx.lib.agw.ultimatelistctrl as ULC


class FSFileInfoPanel(wx.Panel):

    outer_border = 8
    inner_spacing = 24

    def __init__(self, parent, fsfile):
        self.parent = parent
        self.fsfile = fsfile

        super(FSFileInfoPanel, self).__init__(parent, -1, style=wx.SUNKEN_BORDER)

        self.list = ULC.UltimateListCtrl(self,
                                         agwStyle=wx.LC_REPORT
                                                  | wx.LC_NO_HEADER
                                                  | ULC.ULC_NO_HIGHLIGHT
                                                  | ULC.ULC_USER_ROW_HEIGHT
                                         )

        bgcolour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_APPWORKSPACE)
        self.SetBackgroundColour(bgcolour)

        self.field_generators = [
                ('Leafname', lambda fsfile: fsfile.leafname),
                ('File type', lambda fsfile: self.format_filetype(fsfile)),
                ('Size', lambda fsfile: self.format_size(fsfile)),
                ('Date/time', lambda fsfile: self.format_timestamp(None)),
            ]

        self.populate_info()

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, self.outer_border)
        self.SetSizer(self.sizer)
        self.SetAutoLayout(True)

    def GetBestSize(self):
        width = self.list.GetColumnWidth(0) + self.inner_spacing + self.list.GetColumnWidth(1)
        height = (self.list.GetUserLineHeight() + 1) * self.list.GetItemCount()
        return wx.Size(width + self.outer_border * 2,
                       height + self.outer_border * 2)

    def SetBackgroundColour(self, colour):
        super(FSFileInfoPanel, self).SetBackgroundColour(colour)
        self.list.SetBackgroundColour(colour)

    def populate_info(self):

        info = ULC.UltimateListItem()
        info._mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT
        info._format = wx.LIST_FORMAT_RIGHT
        info._text = "Property"
        self.list.InsertColumnInfo(0, info)

        info = ULC.UltimateListItem()
        info._format = wx.LIST_FORMAT_LEFT
        info._mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT
        info._text = "Value"
        self.list.InsertColumnInfo(1, info)

        dc = wx.ScreenDC()
        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT))

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
            maxheight = max(maxheight, field_size[1])
            fields.append((field, value))

        self.list.SetUserLineHeight(int(maxheight * 1.5))

        for field, value in fields:
            self.list.InsertStringItem(index, field)
            self.list.SetStringItem(index, 1, value)
            index += 1

        # The wx.LIST_AUTOSIZE doesn't seem to work here, so we calculate
        # the field widths ourselves.
        self.list.SetColumnWidth(0, maxfieldwidth)
        self.list.SetColumnWidth(1, ULC.ULC_AUTOSIZE_FILL)

    def format_filetype(self, fsfile):
        if fsfile.isdir():
            return "Directory"
        return "&{:03X}".format(fsfile.filetype())

    def format_size(self, fsfile):
        return "{} bytes".format(fsfile.size())

    def format_timestamp(self, fsfile):
        return "UNKNOWN"


class FSFileInfoFrame(wx.Frame):

    # Allow more space for the title text (eg for the buttons in the title)
    title_extra_size = 80

    def __init__(self, parent, fsfile, *args, **kwargs):
        self.parent = parent
        self.fsfile = fsfile
        kwargs['title'] = "File info: {}".format(fsfile.filename)

        super(FSFileInfoFrame, self).__init__(None, *args, **kwargs)

        self.panel = FSFileInfoPanel(self, fsfile)

        size = self.panel.GetBestSize()
        # Allow for the size of the title
        dc = wx.ScreenDC()
        title_size = dc.GetTextExtent(kwargs['title'])
        size = wx.Size(max(title_size[0] + self.title_extra_size, size[0]), size[1])

        self.SetMaxClientSize(size)
        self.SetClientSize(size)
