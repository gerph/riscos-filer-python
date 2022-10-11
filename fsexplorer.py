"""
FSExplorer views, using the fs interfaces.
"""

import os

import wx
from wx.svg import SVGimage
import wx.lib.scrolledpanel as scrolled


class SVGForFiletype(object):
    """
    Singleton class which caches the icons for the files.
    """
    FILETYPE_DIRECTORY = 0x1000
    FILETYPE_LOADEXEC = -1
    resource_dir = os.path.dirname(__file__)

    def __init__(self):
        self.filetype_svg = {}

    def get_svg(self, filetype):
        svg = self.filetype_svg.get(filetype)
        if not svg:
            if filetype == self.FILETYPE_DIRECTORY:
                filename = 'icons/directory.svg'
            elif filetype == self.FILETYPE_LOADEXEC:
                filename = 'icons/file_lxa.svg'
            else:
                filename = 'icons/file_{:03x}.svg'.format(filetype)
            if not os.path.exists(filename):
                filename = 'icons/file_xxx.svg'
            svg_filename = os.path.join(self.resource_dir, filename)
            svg = SVGimage.CreateFromFile(svg_filename)

            self.filetype_svg[filetype] = svg
        return svg


svg_for_filetype = SVGForFiletype()


class FSFileIcon(wx.Panel):

    inner_spacing = 4

    def __init__(self, frame, parent, icon_width, icon_height, fsfile, *args, **kwargs):
        kwargs['style'] = wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER
        super(FSFileIcon, self).__init__(parent, *args, **kwargs)

        text_height = 16

        self.frame = frame
        self.parent = parent
        self.icon_width = icon_width
        self.icon_height = icon_height
        self.bitmap_width = icon_width
        self.bitmap_height = icon_height - self.inner_spacing - text_height
        self.fsfile = fsfile

        self.selected = False

        self.icon_size = wx.Size(self.icon_width, self.icon_height)
        bitmap_size = wx.Size(self.bitmap_width, self.bitmap_height)
        self.statbmp = wx.BitmapButton(self, -1, style=wx.BORDER_NONE | wx.BU_EXACTFIT | wx.BU_NOTEXT)

        filetype = fsfile.filetype()
        if fsfile.isdir():
            filetype = svg_for_filetype.FILETYPE_DIRECTORY
        svg = svg_for_filetype.get_svg(filetype)
        aspect = float(svg.width) / svg.height
        bitmap_size = wx.Size(self.bitmap_height * aspect, self.bitmap_height)
        bmp = svg.ConvertToScaledBitmap(bitmap_size)

        self.statbmp.SetBitmap(bmp)
        self.statbmp.SetMinSize(bitmap_size)
        self.statbmp.SetMaxSize(bitmap_size)

        self.stattxt = wx.Button(self, -1, label=self.fsfile.leafname,
                                 style=wx.ALIGN_CENTRE_HORIZONTAL | wx.BORDER_NONE | wx.BU_EXACTFIT)
        self.stattxt.SetMaxSize(wx.Size(self.icon_width, text_height))
        self.stattxt.SetMinSize(wx.Size(self.icon_width, text_height))

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(self.statbmp, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)
        vsizer.AddSpacer(self.inner_spacing)
        vsizer.Add(self.stattxt, 0, wx.EXPAND | wx.ALL, 0)

        self.SetMaxSize(self.icon_size)
        self.SetMinSize(self.icon_size)
        self.SetSizerAndFit(vsizer)
        if not self.IsDoubleBuffered():
            self.SetDoubleBuffered(True)  # Reduce flicker on size event.

        for obj in (self.statbmp, self.stattxt):
            obj.Bind(wx.EVT_LEFT_DOWN, self.on_click)
            obj.Bind(wx.EVT_LEFT_DCLICK, self.on_click)
            obj.Bind(wx.EVT_RIGHT_DOWN, self.on_click)
            obj.Bind(wx.EVT_RIGHT_DCLICK, self.on_click)
            obj.Bind(wx.EVT_MIDDLE_DOWN, self.on_click)

    def select(self, state=None):
        if state is None:
            state = not self.selected
        else:
            state = bool(state)
        if self.selected != state:
            self.selected = state

            if state:
                self.SetBackgroundColour(self.parent.selection_colour)
            else:
                self.SetBackgroundColour(None)

            # Ensure that the buttons aren't highlighted too.
            self.statbmp.SetBackgroundColour(None)
            self.stattxt.SetBackgroundColour(None)
            self.Refresh()

    def on_click(self, event):
        print("Click %r" % (self.fsfile,))
        #for name in dir(event):
        #    if not name.startswith('_'):
        #        print("  %s: %r" % (name, getattr(event, name)))
        double = event.LeftDClick() or event.RightDClick()
        print("Double: %r" % (double,))

        button = -1
        # Buttons: 0 => left, 1 => right, 2 => middle, -1 => other
        if double:
            if event.LeftDClick():
                button = 0
            elif event.RightDClick():
                button = 1
        else:
            if event.LeftDown():
                button = 0
            elif event.RightDown():
                button = 1
            elif event.MiddleDown():
                button = 2

        if double:
            # Double click
            if button == 0:
                # Run object
                # (deselect item first)
                self.select(False)
                self.frame.on_file_run(self.fsfile, close=False)

            elif button == 1:
                # Run object and close window
                self.frame.on_file_run(self.fsfile, close=True)
        else:
            if button == 0:
                self.frame.select_all(False)
                self.select()
            elif button == 1:
                self.select()
            elif button == 2:
                # FIXME: Menu over an icon window
                self.frame.on_file_menu(self.fsfile)


class FSExplorerPanel(scrolled.ScrolledPanel):

    def __init__(self, *args, **kwargs):
        kwargs['style'] = wx.VSCROLL
        super(FSExplorerPanel, self).__init__(*args, **kwargs)
        self.SetupScrolling(scroll_x=False)
        self.Bind(wx.EVT_SIZE, self.on_size)

        self.selection_colour = wx.Colour(192, 192, 192)

    def on_size(self, evt):
        size = self.GetSize()
        vsize = self.GetVirtualSize()
        self.SetVirtualSize((size[0], vsize[1]))

        evt.Skip()


class FSExplorers(object):
    """
    An object that tracks the explorer frames.
    """

    def __init__(self):
        self.open_windows = {}

    def update_closed(self, dirname):
        del self.open_windows[dirname]

    def update_opened(self, dirname, window):
        self.open_windows[dirname] = window

    def find_window(self, dirname):
        return self.open_windows.get(dirname, None)


class FSExplorerFrame(wx.Frame):

    icon_spacing = 8
    icon_width = 96
    icon_height = 56
    has_title_area = True
    open_offset_x = 16
    open_offset_y = 32
    default_width = 640
    default_height = 480

    def __init__(self, fs, dirname, *args, **kwargs):
        self.fs = fs
        self.dirname = dirname
        self.fsdir = self.fs.dir(dirname)
        self.explorers = kwargs.pop('explorers', None)
        self.icons = {}
        self.panel = None

        kwargs['title'] = self.dirname

        super(FSExplorerFrame, self).__init__(*args, **kwargs)

        self.create_panel()

    def create_title_region(self):
        region = None
        if self.has_title_area:
            stx = wx.StaticText(self.panel, -1, "Directory: {}".format(self.dirname))
            stx.SetFont(wx.Font(28, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            sln = wx.StaticLine(self.panel)
            region = wx.BoxSizer(wx.VERTICAL)
            region.Add(stx, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 8)
            region.Add(sln, 0, wx.EXPAND|wx.ALL, 8)
        return region

    def create_panel(self):
        if self.panel:
            self.panel.Destroy()
            self.panel = None

        # Make a title area and sizer for the upper part of the panel
        self.panel = FSExplorerPanel(self)
        upper = self.create_title_region()

        # FIXME: Update the icon width?

        filer_sizer = wx.WrapSizer(orient=wx.HORIZONTAL)
        for fsfile in self.fsdir.files:
            btn = FSFileIcon(self, self.panel, self.icon_width, self.icon_height, fsfile)
            filer_sizer.Add(btn, 0, wx.ALL, self.icon_spacing)
            self.icons[fsfile.leafname] = btn

        self.panel.Sizer = wx.BoxSizer(wx.VERTICAL)
        if upper:
            self.panel.Sizer.Add(upper, 0, wx.EXPAND)
        self.panel.Sizer.Add(filer_sizer, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 8)

        self.Layout()

        if self.explorers:
            self.explorers.update_opened(self.dirname, self)

    def Close(self):
        super(FSExplorerFrame, self).Close()
        if self.explorers:
            self.explorers.update_closed(self.dirname)

    def change_directory(self, dirname):
        if self.panel:
            if self.explorers:
                self.explorers.update_closed(self.dirname)

        self.dirname = dirname
        self.fsdir = self.fs.dir(dirname)
        self.icons = {}
        self.create_panel()

    def select_file(self, leafname, state):
        fsicon = self.icons.get(leafname, None)
        if fsicon:
            fsicon.select(state)

    def select_all(self, state=True):
        for fsicon in self.icons.values():
            fsicon.select(state)

    def on_file_menu(self, fsfile):
        print("Menu: %r" % (fsfile,))

    def on_file_run(self, fsfile, close=False):
        print("Run: %r" % (fsfile,))
        if fsfile.isdir():
            target = fsfile.filename
            if self.explorers:
                openwindow = self.explorers.find_window(target)
                if openwindow:
                    openwindow.Raise()
                    if close:
                        self.Close()
                    return

            if close:
                self.change_directory(target)
            else:
                pos = self.GetPosition()
                pos = (pos.x + self.open_offset_x, pos.y + self.open_offset_y)
                win = FSExplorerFrame(self.fs, fsfile.filename, None, -1,
                                      explorers=self.explorers,
                                      pos=pos,
                                      size=(self.default_width, self.default_height))
                win.Show(True)
