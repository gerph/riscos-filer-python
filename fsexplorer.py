"""
FSExplorer views, using the fs interfaces.
"""

import os.path

import wx
from wx.svg import SVGimage
import wx.lib.scrolledpanel as scrolled

import explorer
from explorers import FSExplorersBase
from fsinfo import FSFileInfoFrame


class SVGForFiletype(object):
    """
    Singleton class which caches the icons for the files.
    """
    FILETYPE_DIRECTORY = 0x1000
    FILETYPE_APPLICATION = 0x2000
    FILETYPE_LOADEXEC = -1
    resource_dir = os.path.dirname(__file__)

    def __init__(self):
        self.filetype_svg = {}

    def get_svg(self, filetype, leafname):
        svg = self.filetype_svg.get(filetype)
        if not svg:
            if filetype == self.FILETYPE_DIRECTORY:
                filename = 'icons/directory.svg'
            elif filetype == self.FILETYPE_APPLICATION:
                # We could use the leafname here.
                filename = 'icons/application.svg'
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
        self.icons.append(self)

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
        return wx.Size(int(width), int(height))

    def GetTextSize(self):
        return wx.Size(self.requested_text_width, self.max_text_height)

    def GetSpriteSize(self):
        bitmap_width = self.requested_text_width
        bitmap_height = self.requested_icon_height - self.inner_spacing - self.text_size[1]
        return wx.Size(int(bitmap_width), int(bitmap_height))

    def GetSpriteIcon(self):
        sprite_icon = wx.BitmapButton(self, -1, style=wx.BORDER_NONE | wx.BU_EXACTFIT | wx.BU_NOTEXT)

        filetype = self.fsfile.filetype()
        if self.fsfile.isdir():
            if self.fsfile.leafname.startswith('!'):
                filetype = svg_for_filetype.FILETYPE_APPLICATION
            else:
                filetype = svg_for_filetype.FILETYPE_DIRECTORY
        svg = svg_for_filetype.get_svg(filetype, self.fsfile.leafname)
        aspect = float(svg.width) / svg.height
        actual_size = wx.Size(int(self.bitmap_size[1] * aspect), int(self.bitmap_size[1]))
        bmp = svg.ConvertToScaledBitmap(actual_size)

        sprite_icon.SetBitmap(bmp)
        sprite_icon.SetMinSize(actual_size)
        sprite_icon.SetMaxSize(actual_size)
        return sprite_icon

    def GetTextIcon(self):
        text_icon = wx.Button(self, -1, label=self.fsfile.leafname,
                              style=wx.BORDER_NONE | wx.BU_EXACTFIT)
        text_icon.SetMaxSize(self.text_size)
        text_icon.SetMinSize(self.text_size)
        text_icon.SetForegroundColour((0, 0, 0))
        return text_icon

    def show_selected(self, state):
        """
        Show the icon as selected or not. The selection itself is held by the frame's model.
        """
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

        leafname = self.fsfile.leafname
        if button == 'D-SELECT':
            # Run object
            # (deselect item first)
            self.frame.SelectFile(leafname, False)
            self.frame.OnFileActivate(self.fsfile, close=False)

        elif button == 'D-ADJUST':
            # Run object and close window
            self.frame.OnFileActivate(self.fsfile, close=True)

        elif button == 'SELECT':
            self.frame.DeselectAll()
            self.frame.SelectFile(leafname, True)

        elif button == 'ADJUST':
            self.frame.SelectFile(leafname, None)

        elif button == 'MENU':
            if not self.frame.model.is_selected(leafname):
                self.frame.DeselectAll()
                self.frame.SelectFile(leafname, True)
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

        text_icon.SetForegroundColour((0, 0, 0))

        self.text_icon = text_icon
        self.icons.append(self.text_icon)
        self.hsizer.Add(self.text_icon, 0, 0, 0)

        # The padding that sits beside it
        padding_width = total_width - self.text_width
        if padding_width > 0:
            padding = wx.Button(self.parent, -1, label='',
                                size=wx.Size(int(padding_width), int(self.text_height)),
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
        return wx.Size(int(width), int(height))

    def GetSpriteSize(self):
        return wx.Size(int(self.requested_icon_height), int(self.requested_icon_height))

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
        return wx.Size(int(width), int(height))

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


class FSExplorerDropTarget(wx.FileDropTarget):

    def __init__(self, frame):
        super(FSExplorerDropTarget, self).__init__()
        self.frame = frame

    def OnDropFiles(self, x, y, filenames):
        """
        Called when the native explorer drops files here.
        """
        handled = False
        for filepath in filenames:
            handled = handled or self.frame.on_dropped_file(filepath)
        return handled


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
        self.SetBackgroundColour('#ededed')
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
        if self.text_width:
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

        self.drop_target = FSExplorerDropTarget(self.parent)
        self.SetDropTarget(self.drop_target)

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
                self._title_widget.SetForegroundColour((0, 0, 0))
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
    default_sort_order = 'name'
    support_mkdir = True
    support_delete = True
    support_rename = True
    support_refresh = True
    support_dropfile = False

    def __init__(self, fs, dirname, *args, **kwargs):
        self.fs = fs
        self.explorers = kwargs.pop('explorers', None)
        self.panel = None
        self._title_text = None
        self._title_widget = None
        self._frametitle_text = None
        self.debug = False

        self.shift_down = False
        self.control_down = False

        # The model holds what the window shows. It raises if the directory cannot be read, before
        # any window has been made.
        self.model = explorer.FSExplorerModel(
                fs, dirname,
                display_format=kwargs.pop('display_format', None) or self.default_display_format,
                sort_order=kwargs.pop('sort_order', None) or self.default_sort_order,
                mouse_model_riscos=self.mouse_model_riscos,
                support_mkdir=self.support_mkdir,
                support_delete=self.support_delete,
                support_rename=self.support_rename,
                support_refresh=self.support_refresh,
                report_error=lambda title, message: self.ReportError(title, message),
                confirm=lambda title, message, cancel_default=False: self.Confirm(title, message,
                                                                                  cancel_default=cancel_default))

        kwargs['title'] = self.GetFrameTitleText()
        if 'size' not in kwargs:
            kwargs['size'] = (self.default_width, self.default_height)

        super(FSExplorerFrame, self).__init__(*args, **kwargs)

        self.create_panel()

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Build up the menu we'll use
        self.menu_display = wx.Menu()
        self.menuitem_display_large = None
        self.menuitem_display_small = None
        self.menuitem_display_fullinfo = None
        self.menuitem_display_sortname = None
        self.menuitem_display_sortsize = None
        self.menuitem_display_sortfiletype = None
        self.menuitem_display_sorttimestamp = None
        self.add_menu_display(self.menu_display)
        self.menu_selection = wx.Menu()
        self.menuitem_file_delete = None
        self.menuitem_file_rename = None
        self.add_menu_file_selection(self.menu_selection)

        self.menu = wx.Menu()
        self.menu.Append(-1, 'Display', self.menu_display)
        self.menuitem_selection = self.menu.Append(-1, 'Selection', self.menu_selection)
        self.menuitem_clearselection = None
        self.add_menu_selection(self.menu)
        self.menuitem_openparent = None
        self.add_menu_dirop(self.menu)

    @property
    def dirname(self):
        return self.model.dirname

    @property
    def fsdir(self):
        return self.model.fsdir

    @property
    def files(self):
        return self.model.files

    @property
    def display_format(self):
        return self.model.display_format

    @property
    def sort_order(self):
        return self.model.sort_order

    # The window protocol, which the registry of windows (FSExplorersBase) uses.

    def show_window(self):
        self.Show(True)

    def raise_window(self):
        self.Raise()

    def close_window(self):
        self.Close()

    def click_event_to_button(self, event):
        """
        Convert from a click event to an action that we can perform.

        @param event:   The event to process

        @return: button name, in RISC OS terms, preceded by 'D-' for double click
        """
        double = event.LeftDClick() or event.RightDClick()
        button = None
        if double:
            if event.LeftDClick():
                button = 'left'
            elif event.RightDClick():
                button = 'right'
        else:
            if event.LeftDown():
                button = 'left'
            elif event.RightDown():
                button = 'right'
            elif event.MiddleDown():
                button = 'middle'

        # The model takes the click as a RISC OS button, with either mouse model
        self.model.mouse_model_riscos = self.mouse_model_riscos
        return self.model.click_to_button(button, double=double, control=self.control_down)

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

    def add_menuitem(self, menu, name, func,kind=wx.ITEM_NORMAL):
        menuitem = menu.Append(-1, name, kind=kind)
        self.Bind(wx.EVT_MENU, func, menuitem)
        return menuitem

    def add_menu_display(self, menu):
        """
        Add menu items for the 'Display' submenu.
        """
        self.menuitem_display_large = self.add_menuitem(menu, 'Large icons', kind=wx.ITEM_CHECK, func=lambda event: self.SetDisplayFormat('large'))
        self.menuitem_display_small = self.add_menuitem(menu, 'Small icons', kind=wx.ITEM_CHECK, func=lambda event: self.SetDisplayFormat('small'))
        self.menuitem_display_fullinfo = self.add_menuitem(menu, 'Full info', kind=wx.ITEM_CHECK, func=lambda event: self.SetDisplayFormat('fullinfo'))

        menu.AppendSeparator()

        self.menuitem_display_sortname = self.add_menuitem(menu, 'Sort by name', kind=wx.ITEM_CHECK, func=lambda event: self.SetSortOrder('name'))
        self.menuitem_display_sortsize = self.add_menuitem(menu, 'Sort by size', kind=wx.ITEM_CHECK, func=lambda event: self.SetSortOrder('size'))
        self.menuitem_display_sortfiletype = self.add_menuitem(menu, 'Sort by file type', kind=wx.ITEM_CHECK, func=lambda event: self.SetSortOrder('filetype'))
        self.menuitem_display_sorttimestamp = self.add_menuitem(menu, 'Sort by date/time', kind=wx.ITEM_CHECK, func=lambda event: self.SetSortOrder('timestamp'))

    def add_menu_selection(self, menu):
        """
        Add menu items related to making a selection.
        """
        self.add_menuitem(menu, 'Select all\tctrl-A', lambda event: self.SelectAll())
        self.menuitem_clearselection = self.add_menuitem(menu, 'Clear selection', lambda event: self.DeselectAll())

    def add_menu_file_selection(self, menu):
        """
        Add menu items related to a file selection.

        The file menu in the original Filer looks like this:

            Copy        ->
            Rename      ->
            Delete
            Access      ->
            Count
            Help
            Info        ->
            Find
            Set type    ->
            Stamp
            Share...

        We only implement some of these, but we'll try to keep them in the same order.
        """
        if self.support_rename:
            self.menuitem_file_rename = self.add_menuitem(menu, 'Rename...', lambda event: self.ShowRename())
        if self.support_delete:
            self.menuitem_file_delete = self.add_menuitem(menu, 'Delete', lambda event: self.OnSelectionDelete())
        self.add_menuitem(menu, 'Info', lambda event: self.OnSelectionInfo())

    def add_menu_dirop(self, menu):
        if self.support_mkdir:
            self.menuitem_newdir = self.add_menuitem(menu, 'New directory...\tctrl-N', lambda event: self.ShowCreateDirectory())
        else:
            self.menuitem_newdir = None
        self.menuitem_openparent = self.add_menuitem(menu, 'Open parent', lambda event: self.OpenParentDirectory())
        if self.support_refresh:
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
            if self.support_refresh:
                wx.CallAfter(self.RefreshDirectory)

        elif keycode == ord('N') and self.control_down:
            # ctrl-N
            if self.model.capabilities().mkdir_enabled:
                self.ShowCreateDirectory()

        event.Skip()

    def on_dropped_file(self, native_filename):
        if not self.support_dropfile:
            return False

        if self.debug:
            print("Drop dropped on explorer: '%s'" % (native_filename,))

        # FIXME: Dropped files not supported yet
        return False

    def GetTitleText(self):
        if self._title_text:
            return self._title_text
        return self.model.title()

    def SetTitleText(self, title):
        if self._title_widget:
            self._title_text = title
            self._title_widget.SetLabel(title)

    def GetFrameTitleText(self):
        text = self._frametitle_text or self.GetTitleText()
        if self.model.stale:
            # The directory could not be read when it was last refreshed, so what is shown is old
            text += " (not available)"
        return text

    def SetFrameTitleText(self, text):
        self._frametitle_text = text
        self.UpdateFrameTitleText()

    def UpdateFrameTitleText(self):
        text = self.GetFrameTitleText()
        self.SetTitle(text)

    def create_panel(self):
        """
        Make the panel of icons from the model, replacing any there was.
        """
        if self.panel:
            self.panel.Destroy()
            self.panel = None

        # Make a title area and sizer for the upper part of the panel
        self.panel = FSExplorerPanel(self, display_format=self.display_format)
        self.Layout()

        # The selection is held by the model, and the new icons show it
        self.show_selection()

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

    def redraw(self):
        """
        Draw the window again from the model.
        """
        self.create_panel()
        self.UpdateFrameTitleText()

    def RefreshDirectory(self):
        """
        Read the directory again. If it cannot be read, that is reported and the window keeps the
        files that it had.
        """
        if self.model.refresh():
            self.redraw()

    def on_close(self, event):
        if self.explorers:
            self.explorers.window_has_closed(self.dirname)
        # This event is informational, so we pass on.
        event.Skip()

    def ReportError(self, title, message):
        """
        Report an error from the FSExplorer.
        """
        error_frame = wx.MessageDialog(None,
                                       message,
                                       caption=title,
                                       style=wx.OK | wx.ICON_ERROR | wx.CENTRE,
                                       pos=wx.DefaultPosition)
        error_frame.ShowModal()

    def Confirm(self, title, message, cancel_default=False):
        """
        Offer the user an OK/Cancel box to make a choice from.

        @param title:       The dialogue title
        @param message:     Message for the user
        @param cancel_default:  True if the default operation should be to cancel.

        @return: True if OK selected, False if CANCEL selected
        """
        style = wx.OK | wx.CANCEL | wx.ICON_QUESTION | wx.CENTRE
        if cancel_default:
            style |= wx.CANCEL_DEFAULT
        error_frame = wx.MessageDialog(None,
                                       message,
                                       caption=title,
                                       style=style,
                                       pos=wx.DefaultPosition)
        response = error_frame.ShowModal()
        return (response == wx.ID_OK)

    def ShowCreateDirectory(self):
        leafname = wx.GetTextFromUser("New directory name:",
                                      caption="Create new directory",
                                      default_value="Directory",
                                      parent=self, centre=True)

        if not leafname:
            # If they didn't give anything, just ignore as if they cancelled it.
            return

        if self.model.mkdir(leafname):
            self.redraw()

    def ShowRename(self):
        fsfile = self.GetSelectedFiles()[0]
        if self.debug:
            print("Rename request for '{}'".format(fsfile))

        leafname = wx.GetTextFromUser("Rename file:",
                                      caption="New filename (within the current directory)",
                                      default_value=fsfile.leafname,
                                      parent=self, centre=True)

        if not leafname:
            # If they didn't give anything, just ignore as if they cancelled it.
            return

        if self.debug:
            print("Rename from '{}' to '{}'".format(fsfile.leafname, leafname))

        if self.model.rename(fsfile.leafname, leafname):
            self.redraw()

    def ChangeDirectory(self, dirname):
        """
        Show another directory in this window. If it cannot be read, that is reported and the window
        keeps showing the directory that it had.

        @return: True if the directory was changed
        """
        old_dirname = self.dirname
        if not self.model.change_directory(dirname):
            return False
        if self.explorers:
            self.explorers.window_has_closed(old_dirname)
        self.redraw()
        return True

    def SetDisplayFormat(self, display_format):
        if self.model.set_display_format(display_format):
            self.redraw()

    def SetSortOrder(self, sort_order):
        if self.model.set_sort_order(sort_order):
            self.redraw()

    def show_selection(self):
        """
        Make the icons show the selection that the model holds.
        """
        if self.panel:
            for (leafname, fsicon) in self.panel.icons.items():
                fsicon.show_selected(self.model.is_selected(leafname))

    def SelectFile(self, leafname, state=True):
        """
        @param state:   True to select, False to deselect, None to toggle
        """
        if self.model.select(leafname, state):
            self.show_selection()

    def SelectAll(self, state=True):
        if state:
            self.model.select_all()
        else:
            self.model.deselect_all()
        self.show_selection()

    def DeselectAll(self):
        self.SelectAll(state=False)

    def ApplySelectedFiles(self, func):
        # The files are taken first, as the function may change the directory
        for fsfile in self.model.selected():
            func(fsfile)

    def GetSelectedFileIcons(self):
        return [self.panel.icons[fsfile.leafname] for fsfile in self.model.selected()]

    def GetSelectedFiles(self):
        return self.model.selected()

    def on_file_menu(self, fsfile):
        if self.debug:
            print("Menu: %r" % (fsfile,))

        # The model says what the menu offers, given the selection
        caps = self.model.capabilities(fsfile)
        self.menuitem_selection.Enable(caps.selection_enabled)
        self.menuitem_selection.SetItemLabel(caps.selection_label)
        self.menuitem_clearselection.Enable(caps.clear_enabled)

        # Display submenu ticking
        self.menuitem_display_large.Check(self.display_format == 'large')
        self.menuitem_display_small.Check(self.display_format == 'small')
        self.menuitem_display_fullinfo.Check(self.display_format == 'fullinfo')
        self.menuitem_display_sortname.Check(self.sort_order == 'name')
        self.menuitem_display_sortsize.Check(self.sort_order == 'size')
        self.menuitem_display_sortfiletype.Check(self.sort_order == 'filetype')
        self.menuitem_display_sorttimestamp.Check(self.sort_order == 'timestamp')

        if self.menuitem_newdir:
            self.menuitem_newdir.Enable(caps.mkdir_enabled)
        if self.menuitem_file_delete:
            self.menuitem_file_delete.Enable(caps.delete_enabled)
        if self.menuitem_file_rename:
            self.menuitem_file_rename.Enable(caps.rename_enabled)

        # Only show the parent if there is one
        self.menuitem_openparent.Enable(bool(caps.parent))

        self.update_menu(caps)
        self.PopupMenu(self.menu)

    def update_menu(self, caps):
        """
        Overloadable: Change the menu items that a subclass added, ready for the menu to be shown.

        @param caps:    The `explorer.Capabilities` for the menu
        """
        pass

    def GetNextFramePos(self, counter=0):
        """
        Return a position on the screen for the next window to open at.
        """
        # We would like frames to appear in different positions when they're opened
        # as part of a sequence.
        (offset_x, offset_y) = explorer.cascade_offset(counter, self.open_offset_x, self.open_offset_y)
        pos = self.GetPosition()
        return (pos.x + offset_x, pos.y + offset_y)

    def OnFileActivate(self, fsfile, close=False, shift=None):
        if self.debug:
            print("Activate: %r" % (fsfile,))
        if shift is None:
            shift = self.shift_down
        activation = self.model.activate(fsfile, close=close, shift=shift)
        if activation.action == explorer.OPEN_DIRECTORY:
            self.OnFileOpenDir(fsfile, close=activation.close)
        else:
            self.OnFileRun(fsfile, activation.shift)

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
                openwindow.raise_window()
                if close:
                    self.close_window()
                return

        if close:
            self.ChangeDirectory(target)
        else:
            pos = self.GetNextFramePos()
            self.OpenExplorer(target, pos=pos)

    def OpenExplorer(self, target, pos=None):
        """
        Open a window for a directory, or raise the one there is. A directory which cannot be read
        is reported, and no window is opened.
        """
        if not pos:
            pos = self.GetNextFramePos()
        try:
            self.explorers.open_window(target, pos,
                                       display_format=self.display_format,
                                       sort_order=self.sort_order)
        except Exception as exc:
            self.ReportError("Failed to open directory", str(exc))

    def MenuHasOpenParent(self):
        return self.model.parent_dirname()

    def OpenParentDirectory(self, pos=None):
        target = self.MenuHasOpenParent()
        if target:
            self.OpenExplorer(target, pos)

    def OnSelectionInfo(self):
        def open_each(fsfile):
            self.OnFileInfo(fsfile, counter=open_each.counter)
            open_each.counter += 1
        open_each.counter = 0

        self.ApplySelectedFiles(open_each)

    def OnSelectionDelete(self):
        # FIXME: This may open many windows, which is not ideal.
        if self.model.delete():
            self.redraw()

    def OnFileInfo(self, fsfile, counter=0):
        if self.debug:
            print("Info: %r" % (fsfile,))
        pos = self.GetNextFramePos(counter)
        try:
            if self.explorers:
                self.explorers.open_fileinfo(fsfile.filename, pos=pos)
            else:
                fsfileinfo = FSFileInfoFrame(self, fsfile, pos=pos)
                fsfileinfo.Show()
        except Exception as exc:
            self.ReportError("Failed to show information", str(exc))

    def OnFileDelete(self, fsfile):
        if self.debug:
            print("Delete: %r" % (fsfile,))

        # FIXME: Configurable confirmation warning?
        if self.model.delete([fsfile.leafname]):
            self.redraw()


class FSExplorers(FSExplorersBase):
    """
    An object that tracks the explorer frames.
    """
    explorer_frame_cls = FSExplorerFrame
    fileinfo_frame_cls = FSFileInfoFrame

    # The default size of a window, or None to use the explorer_frame_cls values
    default_width = None
    default_height = None

    def __init__(self, fs):
        super(FSExplorers, self).__init__(fs)
        self.default_width = self.default_width or self.explorer_frame_cls.default_width
        self.default_height = self.default_height or self.explorer_frame_cls.default_height

    def create_explorer(self, dirname, pos=None, display_format=None, sort_order=None):
        return self.explorer_frame_cls(self.fs, dirname, None, -1,
                                       explorers=self,
                                       pos=pos,
                                       size=(self.default_width, self.default_height),
                                       display_format=display_format,
                                       sort_order=sort_order)

    def create_fileinfo(self, filename, pos=None):
        fsfile = self.fs.fileinfo(filename)
        return self.fileinfo_frame_cls(self, fsfile, pos=pos, explorers=self)
