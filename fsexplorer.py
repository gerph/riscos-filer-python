"""
FSExplorer views, using the fs interfaces.
"""

import os.path

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
            svg_filename = os.path.join(self.resource_dir, filename)
            if not os.path.exists(svg_filename):
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
        double = event.LeftDClick() or event.RightDClick()
        if self.frame.debug:
            print("Click: %r, Double: %r" % (self.fsfile, double))

        # Ensure that we get focus when we do this.
        self.frame.SetFocus()

        button = 'NONE'
        if double:
            if event.LeftDClick():
                button = 'SELECT'
            elif event.RightDClick():
                button = 'ADJUST'
        else:
            if event.LeftDown():
                button = 'SELECT'
            elif event.RightDown():
                button = 'ADJUST'
            elif event.MiddleDown():
                button = 'MENU'

        # Now let's transform these if we're use the non-RISC OS mouse model
        if not self.frame.mouse_model_riscos:
            # The non-RISC OS mouse model is:
            #   ctrl+left toggles items
            #   right opens menu
            if button == 'ADJUST':
                # Right button means Menu
                button = 'MENU'

            elif button == 'SELECT' and self.frame.control_down:
                # If they had control down, we change this to the Adjust button (1)
                button = 'ADJUST'

        if self.frame.debug:
            print("Mouse: double=%r button=%r" % (double, button))

        if double:
            # Double click
            if button == 'SELECT':
                # Run object
                # (deselect item first)
                self.select(False)
                self.frame.OnFileActivate(self.fsfile, close=False)

            elif button == 'ADJUST':
                # Run object and close window
                self.frame.OnFileActivate(self.fsfile, close=True)
        else:
            if button == 'SELECT':
                self.frame.DeselectAll()
                self.select()

            elif button == 'ADJUST':
                self.select()

            elif button == 'MENU':
                if not self.selected:
                    self.select()
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
    mouse_model_riscos = False

    def __init__(self, fs, dirname, *args, **kwargs):
        self.fs = fs
        self.dirname = dirname
        self.fsdir = self.fs.dir(dirname)
        self.explorers = kwargs.pop('explorers', None)
        self.icons = {}
        self.panel = None
        self._title_text = None
        self._title_widget = None
        self._frametitle_text = None
        self.debug = False

        self.shift_down = False
        self.control_down = False

        kwargs['title'] = self.GetFrameTitleText()
        if 'size' not in kwargs:
            kwargs['size'] = (self.default_width, self.default_height)

        super(FSExplorerFrame, self).__init__(*args, **kwargs)

        self.create_panel()

        # We track keys so that the right events can be delivered for running
        # or opening files.
        self.panel.Bind(wx.EVT_KEY_DOWN, lambda event: self.on_key(event, down=True))
        self.panel.Bind(wx.EVT_KEY_UP, lambda event: self.on_key(event, down=False))

        # Build up the menu we'll use
        self.menu = wx.Menu()
        self.add_menu_selection(self.menu)

    def add_menuitem(self, menu, name, func):
        menuitem = menu.Append(-1, name, kind=wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, func, menuitem)

    def add_menu_selection(self, menu):
        self.add_menuitem(menu, 'Select all', lambda event: self.SelectAll())
        self.add_menuitem(menu, 'Clear selection', lambda event: self.DeselectAll())

    def on_key(self, event, down):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_SHIFT:
            if self.debug:
                print("Key: Shift: %r" % (down,))
            self.shift_down = down
        elif keycode == wx.WXK_CONTROL:
            if self.debug:
                print("Key: Control: %r" % (down,))
            self.control_down = down

    def GetTitleText(self):
        if self._title_text:
            return self._title_text
        return "Directory: {}".format(self.dirname)

    def SetTitleText(self, title):
        if self._title_widget:
            self._title_text = title
            self._title_widget.SetLabel(title)

    def GetFrameTitleText(self):
        if self._frametitle_text:
            return self._frametitle_text
        return self.GetTitleText()

    def SetFrameTitleText(self, text):
        self._frametitle_text = text
        self.UpdateFrameTitleText()

    def UpdateFrameTitleText(self):
        text = self.GetFrameTitleText()
        self.SetTitle(text)

    def create_title_region(self):
        region = None
        if self.has_title_area:
            title = self.GetTitleText()
            if title:
                self._title_widget = wx.StaticText(self.panel, -1, title)
                self._title_widget.SetFont(wx.Font(28, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                sln = wx.StaticLine(self.panel)
                region = wx.BoxSizer(wx.VERTICAL)
                region.Add(self._title_widget, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 8)
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
        files = sorted(self.fsdir.files, key=lambda f: f.leafname.lower())
        for fsfile in files:
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

    def ChangeDirectory(self, dirname):
        if self.panel:
            if self.explorers:
                self.explorers.update_closed(self.dirname)

        self.dirname = dirname
        self.fsdir = self.fs.dir(dirname)
        self.icons = {}
        self.create_panel()
        self.UpdateFrameTitleText()

    def SelectFile(self, leafname, state=True):
        fsicon = self.icons.get(leafname, None)
        if fsicon:
            fsicon.select(state)

    def SelectAll(self, state=True):
        for fsicon in self.icons.values():
            fsicon.select(state)

    def DeselectAll(self):
        self.SelectAll(state=False)

    def on_file_menu(self, fsfile):
        if self.debug:
            print("Menu: %r" % (fsfile,))
        self.PopupMenu(self.menu)

    def OnFileActivate(self, fsfile, close=False, shift=None):
        if self.debug:
            print("Activate: %r" % (fsfile,))
        if shift is None:
            shift = self.shift_down
        if fsfile.isdir():
            self.OnFileOpenDir(fsfile, close=close)
        else:
            self.OnFileRun(fsfile, shift)

    def OnFileRun(self, fsfile, shift):
        if self.debug:
            print("Run: %r" % (fsfile,))

    def OnFileOpenDir(self, fsfile, close=False):
        if self.debug:
            print("OpenDir: %r" % (fsfile,))
        target = fsfile.filename
        if self.explorers:
            openwindow = self.explorers.find_window(target)
            if openwindow:
                openwindow.Raise()
                if close:
                    self.Close()
                return

        if close:
            self.ChangeDirectory(target)
        else:
            pos = self.GetPosition()
            pos = (pos.x + self.open_offset_x, pos.y + self.open_offset_y)
            self.OpenExplorer(target, pos=pos)

    def OpenExplorer(self, target, pos):
        win = FSExplorerFrame(self.fs, target, None, -1,
                              explorers=self.explorers,
                              pos=pos,
                              size=(self.default_width, self.default_height))
        win.Show(True)
