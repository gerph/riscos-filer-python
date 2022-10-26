"""
FSExplorer views, using the fs interfaces.
"""

import os.path

import wx
from wx.svg import SVGimage
import wx.lib.scrolledpanel as scrolled

from fsinfo import FSFileInfoFrame


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

        self.SetMaxSize(self.icon_size)
        self.SetMinSize(self.icon_size)

        self.sizer = self.SetupSizer()
        self.icons = self.GetButtonIcons()

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

    def GetButtonIcons(self):
        return [self.sprite_icon, self.text_icon]

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
        # Ensure that we get focus when we do this (and raise as otherwise we don't get keys)
        self.frame.Raise()
        self.frame.SetFocus()

        button = self.frame.click_event_to_button(event)

        if self.frame.debug:
            print("File Click: Button=%r" % (button,))

        if button == 'D-SELECT':
            # Run object
            # (deselect item first)
            self.select(False)
            self.frame.OnFileActivate(self.fsfile, close=False)

        elif button == 'D-ADJUST':
            # Run object and close window
            self.frame.OnFileActivate(self.fsfile, close=True)

        elif button == 'SELECT':
            self.frame.DeselectAll()
            self.select()

        elif button == 'ADJUST':
            self.select()

        elif button == 'MENU':
            if not self.selected:
                self.frame.DeselectAll()
                self.select()
            self.frame.on_file_menu(self.fsfile)


class LeftAlignedIcons(object):

    def __init__(self, parent, text=None, total_width=0, text_icon=None):
        self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.parent = parent
        self.icons = []
        self.text_width = 0
        self.text_height = 0

        # The main text icon
        if text is not None:
            text_icon = wx.Button(self.parent, -1, label=text.replace('&', '&&'),
                                  style=wx.BU_LEFT | wx.ALIGN_LEFT | wx.BORDER_NONE)

            dc = wx.ScreenDC()
            size = dc.GetTextExtent(text)
            self.text_width = size[0] + 4
            self.text_height = size[1]

            size = wx.Size(self.text_width, self.text_height)
            text_icon.SetMaxSize(size)
            text_icon.SetMinSize(size)

        else:
            (self.text_width, self.text_height) = text_icon.GetMaxSize()

        self.text_icon = text_icon
        self.icons.append(self.text_icon)
        self.hsizer.Add(self.text_icon, 0, 0, 0)

        # The padding that sits beside it
        padding_width = total_width - self.text_width
        if padding_width > 0:
            padding = wx.Button(self.parent, -1, label='',
                                size=wx.Size(padding_width, self.text_height),
                                style=wx.BU_LEFT | wx.ALIGN_LEFT | wx.BORDER_NONE | wx.BU_EXACTFIT)
            self.hsizer.Add(padding, 0, wx.EXPAND | wx.ALL)
            self.icons.append(padding)


class FSFileLargeIcon(FSFileIcon):
    pass


class FSFileSmallIcon(FSFileIcon):
    icon_height = 20

    def __init__(self, frame, parent, text_width, text_height, fsfile, *args, **kwargs):
        kwargs['icon_height'] = self.icon_height
        self.filename_icons = []
        super(FSFileSmallIcon, self).__init__(frame, parent, text_width, text_height, fsfile, *args, **kwargs)

    def SetupSizer(self):
        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(self.sprite_icon, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        hsizer.AddSpacer(self.inner_spacing)

        self.filename_icons = LeftAlignedIcons(self, text_icon=self.text_icon, total_width=self.requested_text_width)
        hsizer.Add(self.filename_icons.hsizer, 0, 0, 0)
        self.AddExtraIcons(hsizer)

        self.SetSizerAndFit(hsizer)
        if not self.IsDoubleBuffered():
            self.SetDoubleBuffered(True)  # Reduce flicker on size event?

        return hsizer

    def AddExtraIcons(self, hsizer):
        pass

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

    def GetButtonIcons(self):
        icons = [self.sprite_icon]
        icons.extend(self.filename_icons.icons)
        return icons


class FSFileFullInfoIcon(FSFileSmallIcon):
    # FIXME: This is not at all efficient - we should really rethink how these rows are drawn
    # as lots of objects really makes it slow.
    filetype_template_string = "MMMMMMMM"
    timestamp_template_string = "00:00:00.00 00 MMM 0000"
    size_template_string = "XXXXXXXXXX bytes"

    cached_filetype_size = None
    cached_timestamp_size = None
    cached_size_size = None

    def __init__(self, frame, parent, text_width, text_height, fsfile, *args, **kwargs):
        super(FSFileFullInfoIcon, self).__init__(frame, parent, text_width, text_height, fsfile, *args, **kwargs)
        self.filetype_size = None
        self.size_icons = None
        self.timestamp_icons = None
        self.filetype_icons = None

    def GetSizeSize(self):
        if not self.cached_size_size:
            dc = wx.ScreenDC()
            size = dc.GetTextExtent(self.size_template_string)
            self.__class__.cached_size_size = wx.Size(size[0] + 4, size[1])
        return self.cached_size_size

    def GetFiletypeSize(self):
        if not self.cached_filetype_size:
            dc = wx.ScreenDC()
            size = dc.GetTextExtent(self.filetype_template_string)
            self.__class__.cached_filetype_size = wx.Size(size[0] + 4, size[1])
        return self.cached_filetype_size

    def GetTimestampSize(self):
        if not self.cached_timestamp_size:
            dc = wx.ScreenDC()
            size = dc.GetTextExtent(self.timestamp_template_string)
            self.__class__.cached_timestamp_size = wx.Size(size[0] + 4, size[1])
        return self.cached_timestamp_size

    def GetIconSize(self):
        width = self.requested_text_width + self.inner_spacing + self.bitmap_size[0]
        width += self.inner_spacing + self.GetSizeSize()[0]
        width += self.inner_spacing + self.GetFiletypeSize()[0]
        width += self.inner_spacing + self.GetTimestampSize()[0]
        height = max(self.text_size[1], self.bitmap_size[1])
        return wx.Size(width, height)

    def GetButtonIcons(self):
        icons = [self.sprite_icon]
        icons.extend(self.filename_icons.icons)
        icons.extend(self.size_icons.icons)
        icons.extend(self.filetype_icons.icons)
        icons.extend(self.timestamp_icons.icons)
        return icons

    def AddExtraIcons(self, hsizer):
        self.size_icons = LeftAlignedIcons(self, text=self.fsfile.format_size(), total_width=self.GetSizeSize()[0])
        hsizer.Add(self.size_icons.hsizer, 0, 0, 0)
        hsizer.AddSpacer(self.inner_spacing)

        self.filetype_icons = LeftAlignedIcons(self, text=self.fsfile.format_filetype(), total_width=self.GetFiletypeSize()[0])
        hsizer.Add(self.filetype_icons.hsizer, 0, 0, 0)
        hsizer.AddSpacer(self.inner_spacing)

        self.timestamp_icons = LeftAlignedIcons(self, text=self.fsfile.format_timestamp(), total_width=self.GetTimestampSize()[0])
        hsizer.Add(self.timestamp_icons.hsizer, 0, 0, 0)
        hsizer.AddSpacer(self.inner_spacing)


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
            elif self.display_format == 'small':
                btn = FSFileSmallIcon(self.parent, self, text_width, text_height, fsfile)
            else:
                btn = FSFileFullInfoIcon(self.parent, self, text_width, text_height, fsfile)
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

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Build up the menu we'll use
        self.menu_display = wx.Menu()
        self.add_menu_display(self.menu_display)
        self.menu_selection = wx.Menu()
        self.add_menu_file_selection(self.menu_selection)

        self.menu = wx.Menu()
        self.menu.Append(-1, 'Display', self.menu_display)
        self.menuitem_selection = self.menu.Append(-1, 'Selection', self.menu_selection)
        self.menuitem_clearselection = None
        self.add_menu_selection(self.menu)
        self.menuitem_openparent = None
        self.add_menu_dirop(self.menu)

    def click_event_to_button(self, event):
        """
        Convert from a click event to an action that we can perform.

        @param event:   The event to process

        @return: button name, in RISC OS terms, preceeded by 'D-' for double click
        """
        double = event.LeftDClick() or event.RightDClick()
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
        if not self.mouse_model_riscos:
            # The non-RISC OS mouse model is:
            #   ctrl+left toggles items
            #   right opens menu
            if button == 'ADJUST':
                # Right button means Menu
                button = 'MENU'

            elif button == 'SELECT' and self.control_down:
                # If they had control down, we change this to the Adjust button (1)
                button = 'ADJUST'

        if button != 'NONE':
            if double:
                button = 'D-' + button

        return button

    def on_click(self, event):
        # Ensure that we get focus when we do this (and raise as otherwise we don't get keys)
        self.Raise()
        self.SetFocus()

        button = self.click_event_to_button(event)

        if self.debug:
            print("Window Click: Button%r" % (button,))

        if button in ('D-SELECT', 'D-ADJUST', 'SELECT'):
            # A plain click on the background should deselect everything,
            # but not if adjust is pressed. Adjust is 'amend the selection'
            # so amending on nothing should leave things alone.
            self.DeselectAll()

        elif button == 'ADJUST':
            # Do nothing
            pass

        elif button == 'MENU':
            self.on_file_menu(None)

    def add_menuitem(self, menu, name, func):
        menuitem = menu.Append(-1, name, kind=wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, func, menuitem)
        return menuitem

    def add_menu_display(self, menu):
        """
        Add menu items for the 'Display' submenu.
        """
        self.add_menuitem(menu, 'Large icons', lambda event: self.SetDisplayFormat('large'))
        self.add_menuitem(menu, 'Small icons', lambda event: self.SetDisplayFormat('small'))
        self.add_menuitem(menu, 'Full info', lambda event: self.SetDisplayFormat('fullinfo'))

    def add_menu_selection(self, menu):
        """
        Add menu items related to making a selection.
        """
        self.add_menuitem(menu, 'Select all\tctrl-A', lambda event: self.SelectAll())
        self.menuitem_clearselection = self.add_menuitem(menu, 'Clear selection', lambda event: self.DeselectAll())

    def add_menu_file_selection(self, menu):
        """
        Add menu items related to a file selection
        """
        self.add_menuitem(menu, 'Info...', lambda event: self.OnSelectionInfo())

    def add_menu_dirop(self, menu):
        self.menuitem_openparent = self.add_menuitem(menu, 'Open parent', lambda event: self.OpenParentDirectory())
        self.add_menuitem(menu, 'Refresh directory\tctrl-R', lambda event: self.RefreshDirectory())

    def on_key(self, event, down):
        keycode = event.GetKeyCode()
        if self.debug:
            print("Key: code = %r, down = %r" % (keycode, down))
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
        if self.debug:
            print("KeyChar: code = %r" % (keycode,))

        if keycode == ord('A') and self.control_down:
            # ctrl-A
            self.SelectAll()

        elif keycode == ord('R') and self.control_down:
            # ctrl-R
            wx.CallAfter(self.RefreshDirectory)

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

    def create_panel(self, keep_selection=True):
        last_selection = set()
        if self.panel:
            # Construct a list of the last selected icons in the panel
            if keep_selection:
                for fsicon in self.panel.icons.values():
                    if fsicon.selected:
                        last_selection.add(fsicon.fsfile.leafname)

            self.panel.Destroy()
            self.panel = None

        self.files = sorted(self.fsdir.files, key=lambda f: f.leafname.lower())

        # Make a title area and sizer for the upper part of the panel
        self.panel = FSExplorerPanel(self, display_format=self.display_format)
        self.Layout()

        # Now re-select the old selection
        for leafname in last_selection:
            self.SelectFile(leafname)

        # We track keys so that the right events can be delivered for running
        # or opening files with control keys pressed.
        self.panel.Bind(wx.EVT_KEY_DOWN, lambda event: self.on_key(event, down=True))
        self.panel.Bind(wx.EVT_KEY_UP, lambda event: self.on_key(event, down=False))
        # We want regular characters for the cases where we're controlling by
        # the keyboard.
        self.panel.Bind(wx.EVT_CHAR, self.on_key_char)
        self.panel.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.panel.Bind(wx.EVT_LEFT_DCLICK, self.on_click)
        self.panel.Bind(wx.EVT_RIGHT_DOWN, self.on_click)
        self.panel.Bind(wx.EVT_RIGHT_DCLICK, self.on_click)
        self.panel.Bind(wx.EVT_MIDDLE_DOWN, self.on_click)

        if self.explorers:
            self.explorers.window_has_closed(self.dirname)
            self.explorers.window_has_opened(self.dirname, self)

    def RefreshDirectory(self):
        self.fs.invalidate_dir(self.dirname)
        self.fsdir.invalidate()
        self.create_panel()

    def on_close(self, event):
        if self.explorers:
            self.explorers.window_has_closed(self.dirname)
        # This event is informational, so we pass on.
        event.Skip()

    def ChangeDirectory(self, dirname):
        if self.panel:
            if self.explorers:
                self.explorers.window_has_closed(self.dirname)

        self.dirname = dirname
        self.fsdir = self.fs.dir(dirname)
        self.create_panel(keep_selection=False)
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

    def ApplySelectedFiles(self, func):
        for fsicon in self.panel.icons.values():
            if fsicon.selected:
                func(fsicon.fsfile)

    def GetSelectedFileIcons(self):
        selection = [fsicon for fsicon in self.panel.icons.values() if fsicon.selected]
        return selection

    def on_file_menu(self, fsfile):
        if self.debug:
            print("Menu: %r" % (fsfile,))

        # Prepare the menu to display files
        selection = self.GetSelectedFileIcons()
        if len(selection) == 0:
            # No files selected, so we need to grey out the selection menu
            self.menuitem_selection.Enable(False)
            self.menuitem_selection.SetItemLabel("Selection")
            self.menuitem_clearselection.Enable(False)
        else:
            self.menuitem_selection.Enable(True)
            if len(selection) == 1:
                self.menuitem_selection.SetItemLabel("File '{}'".format(selection[0].fsfile.leafname))
            else:
                self.menuitem_selection.SetItemLabel("File ''")
            self.menuitem_clearselection.Enable(True)

        # Only show the parent if there is one
        self.menuitem_openparent.Enable(bool(self.MenuHasOpenParent()))

        self.PopupMenu(self.menu)

    def GetNextFramePos(self, counter=0):
        """
        Return a position on the screen for the next window to open at.
        """
        # We would like frames to appear in different positions when they're opened
        # as part of a sequence.
        counterx = (counter % 8) + ((counter / 8) % 6)
        countery = (counter % 8) + (((counter / 8) % 6) / 2.0)

        pos = self.GetPosition()
        pos = (pos.x + int(self.open_offset_x * (counterx + 1)),
               pos.y + int(self.open_offset_y * (countery + 1)))
        return pos

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
            pos = self.GetNextFramePos()
            self.OpenExplorer(target, pos=pos)

    def OpenExplorer(self, target, pos=None):
        if not pos:
            pos = self.GetNextFramePos()
        self.explorers.open_window(target, pos, self.display_format)

    def MenuHasOpenParent(self):
        target = self.fs.dirname(self.dirname)
        if self.fs.normalise_name(target) == self.fs.normalise_name(self.dirname):
            return None
        return target

    def OpenParentDirectory(self, pos=None):
        target = MenuHasOpenParent()
        if target:
            self.OpenExplorer(target, pos)

    def OnSelectionInfo(self):
        def open_each(fsfile):
            self.OnFileInfo(fsfile, counter=open_each.counter)
            open_each.counter += 1
        open_each.counter = 0

        self.ApplySelectedFiles(open_each)

    def OnFileInfo(self, fsfile, counter=0):
        if self.debug:
            print("Info: %r" % (fsfile,))
        pos = self.GetNextFramePos(counter)
        if self.explorers:
            self.explorers.open_fileinfo(fsfile.filename, pos=pos)
        else:
            fsfileinfo = FSFileInfoFrame(self, fsfile, pos=pos)
            fsfileinfo.Show()


class FSExplorers(object):
    """
    An object that tracks the explorer frames.
    """
    explorer_frame_cls = FSExplorerFrame
    fileinfo_frame_cls = FSFileInfoFrame

    # The default size of a window, or None to use the explorer_frame_cls values
    default_width = None
    default_height = None

    def __init__(self, fs):
        self.fs = fs
        self.open_windows = {}
        self.open_fileinfos = {}
        self.default_width = self.default_width or self.explorer_frame_cls.default_width
        self.default_height = self.default_height or self.explorer_frame_cls.default_height

    def fsfile_key(self, filename):
        """
        Return a key for the file that has been requested.

        For systems like Windows or RISC OS, this will be a case insensitive name,
        but for Linux might be an identity.
        """
        filenamekey = self.fs.normalise_name(filename)
        return filenamekey

    def window_has_closed(self, dirname):
        filenamekey = self.fsfile_key(dirname)
        if filenamekey in self.open_windows:
            del self.open_windows[filenamekey]

    def window_has_opened(self, dirname, window):
        filenamekey = self.fsfile_key(dirname)
        if filenamekey in self.open_windows:
            # If there was a window already, force it to close so that we don't get multiple windows on the screen.
            # Shouldn't happen if these functions are called consistently.
            self.open_windows[filenamekey].Close()
        self.open_windows[filenamekey] = window

    def fileinfo_has_closed(self, filename):
        filenamekey = self.fsfile_key(filename)
        if filenamekey in self.open_fileinfos:
            del self.open_fileinfos[filenamekey]

    def fileinfo_has_opened(self, filename, window):
        filenamekey = self.fsfile_key(filename)
        if filenamekey in self.open_fileinfos:
            # If there was a window already, force it to close so that we don't get multiple windows on the screen.
            # Shouldn't happen if these functions are called consistently.
            self.open_fileinfos[filenamekey].Close()

        self.open_fileinfos[filenamekey] = window

    def find_window(self, dirname):
        filenamekey = self.fsfile_key(dirname)
        return self.open_windows.get(filenamekey, None)

    def open_window(self, dirname, pos=None, display_format=None):
        win = self.find_window(dirname)
        if win:
            win.Raise()
        else:
            win = self.explorer_frame_cls(self.fs, dirname, None, -1,
                                          explorers=self,
                                          pos=pos,
                                          size=(self.default_width, self.default_height),
                                          display_format=display_format)
            win.Show(True)

        return win

    def find_fileinfo(self, filename):
        filenamekey = self.fsfile_key(filename)
        return self.open_fileinfos.get(filenamekey, None)

    def open_fileinfo(self, filename, pos=None):
        win = self.find_fileinfo(filename)
        if win:
            win.Raise()
        else:
            fsfile = self.fs.fileinfo(filename)
            fsfileinfo = self.fileinfo_frame_cls(self, fsfile, pos=pos, explorers=self)
            fsfileinfo.Show()
