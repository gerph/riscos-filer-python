"""
FSExplorer views, using the fs interfaces.
"""

import os.path

import wx
from wx.svg import SVGimage
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.ultimatelistctrl as ULC


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

    min_icon_width = 64
    icon_padding = 4
    default_icon_height = 56
    inner_spacing = 4

    def __init__(self, frame, parent, text_width, text_height, fsfile, *args, **kwargs):
        kwargs['style'] = wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER

        self.frame = frame
        self.parent = parent
        self.max_text_width = text_width
        self.max_text_height = text_height
        self.requested_icon_height = kwargs.pop('icon_height', self.default_icon_height)
        self.requested_text_width = max(self.min_icon_width, text_width)
        self.fsfile = fsfile

        super(FSFileIcon, self).__init__(parent, *args, **kwargs)

        self.selected = False
        self.sprite_icon = None

        self.text_size = self.GetTextSize()
        self.bitmap_size = self.GetSpriteSize()
        self.icon_size = self.GetIconSize()

        self.sprite_icon = self.GetSpriteIcon()
        self.text_icon = self.GetTextIcon()

        self.icons = (self.sprite_icon, self.text_icon)

        self.SetMaxSize(self.icon_size)
        self.SetMinSize(self.icon_size)

        self.sizer = self.SetupSizer()

        for obj in self.icons:
            obj.Bind(wx.EVT_LEFT_DOWN, self.on_click)
            obj.Bind(wx.EVT_LEFT_DCLICK, self.on_click)
            obj.Bind(wx.EVT_RIGHT_DOWN, self.on_click)
            obj.Bind(wx.EVT_RIGHT_DCLICK, self.on_click)
            obj.Bind(wx.EVT_MIDDLE_DOWN, self.on_click)

    def SetupSizer(self):
        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(self.sprite_icon, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)
        vsizer.AddSpacer(self.inner_spacing)
        vsizer.Add(self.text_icon, 0, wx.EXPAND | wx.ALL, 0)

        self.SetSizerAndFit(vsizer)
        if not self.IsDoubleBuffered():
            self.SetDoubleBuffered(True)  # Reduce flicker on size event.

        return vsizer

    def GetIconSize(self):
        width = max(self.text_size[0], self.bitmap_size[0])
        height = self.text_size[1] + self.inner_spacing + self.bitmap_size[1]
        return wx.Size(width, height)

    def GetTextSize(self):
        return wx.Size(self.requested_text_width, self.max_text_height)

    def GetSpriteSize(self):
        bitmap_width = self.requested_text_width
        bitmap_height = self.requested_icon_height - self.inner_spacing - self.text_size[1]
        return wx.Size(bitmap_width, bitmap_height)

    def GetSpriteIcon(self):
        sprite_icon = wx.BitmapButton(self, -1, style=wx.BORDER_NONE | wx.BU_EXACTFIT | wx.BU_NOTEXT)

        filetype = self.fsfile.filetype()
        if self.fsfile.isdir():
            filetype = svg_for_filetype.FILETYPE_DIRECTORY
        svg = svg_for_filetype.get_svg(filetype)
        aspect = float(svg.width) / svg.height
        actual_size = wx.Size(self.bitmap_size[1] * aspect, self.bitmap_size[1])
        bmp = svg.ConvertToScaledBitmap(actual_size)

        sprite_icon.SetBitmap(bmp)
        sprite_icon.SetMinSize(actual_size)
        sprite_icon.SetMaxSize(actual_size)
        return sprite_icon

    def GetTextIcon(self):
        text_icon = wx.Button(self, -1, label=self.fsfile.leafname,
                              style=wx.ALIGN_CENTRE_HORIZONTAL | wx.BORDER_NONE | wx.BU_EXACTFIT)
        text_icon.SetMaxSize(self.text_size)
        text_icon.SetMinSize(self.text_size)
        return text_icon

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
            self.sprite_icon.SetBackgroundColour(None)
            self.text_icon.SetBackgroundColour(None)
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


class FSFileLargeIcon(FSFileIcon):
    pass


class FSFileSmallIcon(FSFileIcon):
    icon_height = 20

    def __init__(self, frame, parent, text_width, text_height, fsfile, *args, **kwargs):
        kwargs['icon_height'] = self.icon_height
        super(FSFileSmallIcon, self).__init__(frame, parent, text_width, text_height, fsfile, *args, **kwargs)

    def SetupSizer(self):
        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(self.sprite_icon, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hsizer.AddSpacer(self.inner_spacing)
        hsizer.Add(self.text_icon, 0, 0, 0)

        padding_width = self.icon_size[0] - self.bitmap_size[0] - self.inner_spacing - self.text_size[0]
        if padding_width > 0:
            padding = wx.Button(self, -1, label='',
                                size=wx.Size(padding_width, self.text_size[1]),
                                style=wx.BU_LEFT | wx.ALIGN_LEFT | wx.BORDER_NONE | wx.BU_EXACTFIT)
            hsizer.Add(padding, 0, wx.EXPAND | wx.ALL)

        self.SetSizerAndFit(hsizer)
        if not self.IsDoubleBuffered():
            self.SetDoubleBuffered(True)  # Reduce flicker on size event?

        return hsizer

    def GetIconSize(self):
        width = self.requested_text_width + self.inner_spacing + self.bitmap_size[0]
        height = max(self.text_size[1], self.bitmap_size[1])
        return wx.Size(width, height)

    def GetSpriteSize(self):
        return wx.Size(self.requested_icon_height, self.requested_icon_height)

    def GetTextSize(self):
        dc = wx.ScreenDC()
        size = dc.GetTextExtent(self.fsfile.leafname)
        return wx.Size(size[0] + 4, size[1])

    def GetTextIcon(self):
        text_icon = wx.Button(self, -1, label=self.fsfile.leafname,
                              style=wx.BU_LEFT | wx.ALIGN_LEFT | wx.BORDER_NONE)

        text_icon.SetMaxSize(self.text_size)
        text_icon.SetMinSize(self.text_size)

        return text_icon


class FSExplorerPanel(scrolled.ScrolledPanel):

    min_text_width = 96
    icon_padding = 4
    icon_spacing = 4
    icon_height = 56
    default_display_format = 'large'

    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.display_format = kwargs.pop('display_format', self.default_display_format)

        kwargs['style'] = wx.VSCROLL
        super(FSExplorerPanel, self).__init__(parent, *args, **kwargs)
        self.SetupScrolling(scroll_x=False)
        self.Bind(wx.EVT_SIZE, self.on_size)

        self.selection_colour = wx.Colour(192, 192, 192)

        self.icons = {}

        upper = self.create_title_region()

        filer_sizer = wx.WrapSizer(orient=wx.HORIZONTAL)
        self.text_width = {}

        # Get the size of the icons
        dc = wx.ScreenDC()
        for fsfile in self.parent.files:
            # FIXME: Should we have ensured that these names were presentation encoding?
            size = dc.GetTextExtent(fsfile.leafname)
            self.text_width[fsfile.leafname] = size[0] + self.icon_padding

        size = dc.GetTextExtent("M_^")
        text_height = size[1]

        text_width = self.min_text_width
        text_width = max(text_width, *self.text_width.values())

        for fsfile in self.parent.files:
            if self.display_format == 'large':
                btn = FSFileLargeIcon(self.parent, self, text_width, text_height, fsfile)
            else:
                btn = FSFileSmallIcon(self.parent, self, text_width, text_height, fsfile)
            filer_sizer.Add(btn, 0, wx.ALL, self.icon_spacing)
            self.icons[fsfile.leafname] = btn

        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        if upper:
            self.Sizer.Add(upper, 0, wx.EXPAND)
        self.Sizer.Add(filer_sizer, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 8)

        self.Layout()

    def on_size(self, evt):
        size = self.GetSize()
        vsize = self.GetVirtualSize()
        self.SetVirtualSize((size[0], vsize[1]))

        evt.Skip()

    def create_title_region(self):
        region = None
        if self.parent.has_title_area:
            title = self.parent.GetTitleText()
            if title:
                self._title_widget = wx.StaticText(self, -1, title)
                self._title_widget.SetFont(wx.Font(28, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                sln = wx.StaticLine(self)
                region = wx.BoxSizer(wx.VERTICAL)
                region.Add(self._title_widget, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 8)
                region.Add(sln, 0, wx.EXPAND|wx.ALL, 8)
        return region


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


class FSFileInfoPanel(wx.Panel):

    outer_border = 8

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
        width = self.list.GetColumnWidth(0) + self.list.GetColumnWidth(1)
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

        maxwidth = 96
        maxheight = 8
        index = 0
        fields = []
        for field, generator in self.field_generators:
            value = generator(self.fsfile)
            size = dc.GetTextExtent(field)
            maxwidth = max(maxwidth, size[0])
            maxheight = max(maxheight, size[1])
            fields.append((field, value))

        self.list.SetUserLineHeight(int(maxheight * 1.5))

        for field, value in fields:
            self.list.InsertStringItem(index, field)
            self.list.SetStringItem(index, 1, value)
            index += 1

        # The wx.LIST_AUTOSIZE doesn't seem to work here, so we calculate
        # the field widths ourselves.
        self.list.SetColumnWidth(0, maxwidth)
        self.list.SetColumnWidth(1, ULC.ULC_AUTOSIZE_FILL)

    def format_filetype(self, fsfile):
        return "&{:03X}".format(fsfile.filetype())

    def format_size(self, fsfile):
        return "{} bytes".format(fsfile.size())

    def format_timestamp(self, fsfile):
        return "UNKNOWN"


class FSFileInfoFrame(wx.Frame):

    def __init__(self, parent, fsfile, *args, **kwargs):
        self.parent = parent
        self.fsfile = fsfile
        kwargs['title'] = "File info: {}".format(fsfile.filename)

        super(FSFileInfoFrame, self).__init__(None, *args, **kwargs)

        self.panel = FSFileInfoPanel(self, fsfile)

        self.SetMaxClientSize(self.panel.GetBestSize())
        self.SetClientSize(self.panel.GetBestSize())


class FSExplorerFrame(wx.Frame):

    has_title_area = True
    open_offset_x = 16
    open_offset_y = 32
    default_width = 640
    default_height = 480
    mouse_model_riscos = False
    default_display_format = 'large'

    def __init__(self, fs, dirname, *args, **kwargs):
        self.fs = fs
        self.dirname = dirname
        self.fsdir = self.fs.dir(dirname)
        self.explorers = kwargs.pop('explorers', None)
        self.display_format = kwargs.pop('display_format', self.default_display_format)
        self.panel = None
        self._title_text = None
        self._title_widget = None
        self._frametitle_text = None
        self.debug = False
        self.files = []

        self.shift_down = False
        self.control_down = False

        kwargs['title'] = self.GetFrameTitleText()
        if 'size' not in kwargs:
            kwargs['size'] = (self.default_width, self.default_height)

        super(FSExplorerFrame, self).__init__(*args, **kwargs)

        self.create_panel()

        # We track keys so that the right events can be delivered for running
        # or opening files with control keys pressed.
        self.panel.Bind(wx.EVT_KEY_DOWN, lambda event: self.on_key(event, down=True))
        self.panel.Bind(wx.EVT_KEY_UP, lambda event: self.on_key(event, down=False))
        # We want regular characters for the cases where we're controlling by
        # the keyboard.
        self.panel.Bind(wx.EVT_CHAR, self.on_key_char)

        # Build up the menu we'll use
        self.display_menu = wx.Menu()
        self.add_menu_display(self.display_menu)
        self.selection_menu = wx.Menu()
        self.add_menu_file_selection(self.selection_menu)

        self.menu = wx.Menu()
        self.menu.Append(-1, 'Display', self.display_menu)
        self.menu.Append(-1, 'Selection', self.selection_menu)
        self.add_menu_selection(self.menu)

    def add_menuitem(self, menu, name, func):
        menuitem = menu.Append(-1, name, kind=wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, func, menuitem)

    def add_menu_display(self, menu):
        """
        Add menu items for the 'Display' submenu.
        """
        self.add_menuitem(menu, 'Large icons', lambda event: self.SetDisplayFormat('large'))
        self.add_menuitem(menu, 'Small icons', lambda event: self.SetDisplayFormat('small'))

    def add_menu_selection(self, menu):
        """
        Add menu items related to making a selection.
        """
        self.add_menuitem(menu, 'Select all', lambda event: self.SelectAll())
        self.add_menuitem(menu, 'Clear selection', lambda event: self.DeselectAll())

    def add_menu_file_selection(self, menu):
        """
        Add menu items related to a file selection
        """
        # FIXME: Make this able to grey items if they are inappropriate
        self.add_menuitem(menu, 'Info...', lambda event: self.OnSelectionInfo())

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
        event.Skip()

    def on_key_char(self, event):
        """
        Handle any extra key codes - don't have any yet.
        """
        keycode = event.GetKeyCode()
        event.Skip()

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

    def create_panel(self):
        if self.panel:
            self.panel.Destroy()
            self.panel = None

        self.files = sorted(self.fsdir.files, key=lambda f: f.leafname.lower())

        # Make a title area and sizer for the upper part of the panel
        self.panel = FSExplorerPanel(self, display_format=self.display_format)
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
        self.create_panel()
        self.UpdateFrameTitleText()

    def SetDisplayFormat(self, display_format):
        self.display_format = display_format
        self.create_panel()
        # The title text might be affected by the display format
        self.UpdateFrameTitleText()

    def SelectFile(self, leafname, state=True):
        fsicon = self.panel.icons.get(leafname, None)
        if fsicon:
            fsicon.select(state)

    def SelectAll(self, state=True):
        for fsicon in self.panel.icons.values():
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
                              size=(self.default_width, self.default_height),
                              display_format=self.display_format)
        win.Show(True)

    def OnSelectionInfo(self):
        for fsicon in self.panel.icons.values():
            if fsicon.selected:
                self.OnFileInfo(fsicon.fsfile)

    def OnFileInfo(self, fsfile):
        if self.debug:
            print("Info: %r" % (fsfile,))
        fsfileinfo = FSFileInfoFrame(self, fsfile)
        fsfileinfo.Show()
