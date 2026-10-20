"""
A file explorer window in GTK, in the style of the RISC OS filer.

The window is drawn from an `explorer.FSExplorerModel` (which holds the directory, the selection and
the rules) by an `IconPanel`, which draws every icon itself and works out which one a click is on
(`iconlayout`), instead of having a widget for each icon. The look is that of the RISC OS filer, so
the standard GTK icon and list views are not used. The icons are the SVG files in the `icons`
directory, drawn through GdkPixbuf if it can read SVG, and by a plain shape if it cannot.

Select, Adjust and Menu are the buttons of the RISC OS mouse model, or with the other mouse model,
left, Ctrl+left and right.

Needs PyGObject and GTK 3.
"""

import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo
try:
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
except (ValueError, ImportError):
    GdkPixbuf = None

import explorer
import iconlayout
from explorers import FSExplorersBase
from gtkinfo import GtkFileInfoFrame


class IconCache(object):
    """
    The icons for the file types, as pixbufs of a height. A file type with no icon of its own, or if
    SVG cannot be loaded, has none (the panel draws a plain shape then).
    """

    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')

    def __init__(self):
        self.pixbufs = {}

    def pixbuf(self, filetype, height):
        """
        @return: A GdkPixbuf.Pixbuf scaled to the height, or None if there is no icon to be had
        """
        key = (filetype, height)
        if key not in self.pixbufs:
            self.pixbufs[key] = self.load(filetype, height)
        return self.pixbufs[key]

    def load(self, filetype, target):
        if GdkPixbuf is None:
            return None
        path = os.path.join(self.icon_dir, explorer.icon_filename(filetype))
        if not os.path.exists(path):
            path = os.path.join(self.icon_dir, 'file_xxx.svg')
        try:
            # These SVGs have no viewBox, so the loader will not scale them: they are rendered at
            # their own size, and the pixbuf is scaled down.
            (_, width, height) = GdkPixbuf.Pixbuf.get_file_info(path)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)
            return pixbuf.scale_simple(max(1, int(round(width * float(target) / height))), target,
                                       GdkPixbuf.InterpType.BILINEAR)
        except Exception:
            # No loader for SVG, or the file will not load
            return None


def draw_fallback_icon(context, x, y, width, height, directory):
    """
    A plain icon, for when the real one cannot be drawn: a folder, or a page with a turned corner.
    """
    context.save()
    context.set_line_width(1)
    if directory:
        context.set_source_rgb(0.95, 0.80, 0.35)
        context.rectangle(x + 2, y + height * 0.25, width - 4, height * 0.65)
        context.fill_preserve()
        context.set_source_rgb(0.4, 0.3, 0.1)
        context.stroke()
        context.set_source_rgb(0.95, 0.80, 0.35)
        context.rectangle(x + 2, y + height * 0.12, width * 0.4, height * 0.15)
        context.fill_preserve()
        context.set_source_rgb(0.4, 0.3, 0.1)
        context.stroke()
    else:
        left = x + width * 0.2
        right = x + width * 0.8
        fold = width * 0.2
        context.move_to(left, y + 1)
        context.line_to(right - fold, y + 1)
        context.line_to(right, y + 1 + fold)
        context.line_to(right, y + height - 1)
        context.line_to(left, y + height - 1)
        context.close_path()
        context.set_source_rgb(1, 1, 1)
        context.fill_preserve()
        context.set_source_rgb(0.3, 0.3, 0.3)
        context.stroke()
    context.restore()


class IconPanel(Gtk.DrawingArea):
    """
    Draws the icons of the model, and turns the pointer into events for the frame.
    """

    min_text_width = 96
    text_padding = 4
    inner_spacing = 4
    large_icon_height = 56
    small_icon_height = 20
    background = (0xed / 255.0, 0xed / 255.0, 0xed / 255.0)
    selection = (192 / 255.0, 192 / 255.0, 192 / 255.0)
    # The widest the columns of the full information format can be, as text
    fullinfo_templates = ("XXXXXXXXXX bytes", "MMMMMMMM", "00:00:00.00 00 MMM 0000")

    def __init__(self, frame, icons):
        super(IconPanel, self).__init__()
        self.frame = frame
        self.icons = icons
        self.layout = iconlayout.IconLayout(cell_width=self.min_text_width, cell_height=self.large_icon_height)
        self.title_height = 0
        self.text_height = 12
        self.columns = ()
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.set_can_focus(True)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("size-allocate", self.on_size_allocate)
        self.rebuild()

    # --- Layout

    def text_size(self, text, font=None):
        layout = self.create_pango_layout(text)
        if font:
            layout.set_font_description(font)
        return layout.get_pixel_size()

    def title_font(self):
        return Pango.FontDescription("Sans 28")

    def rebuild(self):
        """
        Work out the sizes of the cells for the model's files, and place them.
        """
        model = self.frame.model
        text_width = self.min_text_width
        for fsfile in model.files:
            text_width = max(text_width, self.text_size(fsfile.leafname)[0] + self.text_padding)
        self.text_height = self.text_size("M_^")[1]

        self.columns = ()
        if model.display_format == 'large':
            cell = (text_width, self.large_icon_height)
        else:
            cell_width = text_width + self.inner_spacing + self.small_icon_height
            if model.display_format != 'small':
                widths = [self.text_size(template)[0] + self.text_padding for template in self.fullinfo_templates]
                self.columns = tuple(widths)
                for width in widths:
                    cell_width += self.inner_spacing + width
            cell = (cell_width, max(self.text_height, self.small_icon_height))
        self.text_width = text_width
        self.layout = iconlayout.IconLayout(cell_width=cell[0], cell_height=cell[1])

        self.title_height = 0
        if self.frame.has_title_area and self.frame.title_text():
            self.title_height = self.text_size(self.frame.title_text(), self.title_font())[1] + 32
        self.place()
        self.queue_draw()

    def place(self):
        width = self.get_allocated_width() or self.frame.default_width
        height = self.layout.layout(len(self.frame.model.files), width, top=self.title_height)
        self.set_size_request(-1, height)

    def on_size_allocate(self, widget, allocation):
        height = self.layout.height
        self.place()
        if self.layout.height != height:
            self.queue_draw()

    def rect_of(self, leafname):
        """
        The rectangle (x, y, width, height) of the icon of a file, or None.
        """
        for (index, fsfile) in enumerate(self.frame.model.files):
            if fsfile.leafname == leafname:
                return self.layout.rects[index]
        return None

    # --- Drawing

    def on_draw(self, widget, context):
        model = self.frame.model
        context.set_source_rgb(*self.background)
        context.paint()

        if self.title_height:
            layout = self.create_pango_layout(self.frame.title_text())
            layout.set_font_description(self.title_font())
            (width, height) = layout.get_pixel_size()
            context.set_source_rgb(0, 0, 0)
            context.move_to((self.get_allocated_width() - width) / 2.0, 8)
            PangoCairo.show_layout(context, layout)
            context.set_source_rgb(0.5, 0.5, 0.5)
            context.rectangle(8, self.title_height - 12, self.get_allocated_width() - 16, 1)
            context.fill()

        for (index, fsfile) in enumerate(model.files):
            self.draw_icon(context, fsfile, self.layout.rects[index], model.is_selected(fsfile.leafname))
        return False

    def draw_icon(self, context, fsfile, rect, selected):
        (x, y, width, height) = rect
        model = self.frame.model
        if selected:
            context.set_source_rgb(*self.selection)
            context.rectangle(x, y, width, height)
            context.fill()

        filetype = explorer.icon_filetype(fsfile)
        if model.display_format == 'large':
            image_height = max(8, self.large_icon_height - self.inner_spacing - self.text_height)
            self.draw_image(context, fsfile, filetype, x + (width - self.text_width) / 2.0,
                            y, self.text_width, image_height)
            self.draw_text(context, fsfile.leafname, x, y + image_height + self.inner_spacing,
                           width, centre=True)
        else:
            size = self.small_icon_height
            self.draw_image(context, fsfile, filetype, x, y + (height - size) / 2.0, size, size)
            left = x + size + self.inner_spacing
            self.draw_text(context, fsfile.leafname, left, y + (height - self.text_height) / 2.0, self.text_width)
            if self.columns:
                left += self.text_width
                for (text, width) in zip((fsfile.format_size(), fsfile.format_filetype(), fsfile.format_timestamp()),
                                         self.columns):
                    left += self.inner_spacing
                    self.draw_text(context, text, left, y + (height - self.text_height) / 2.0, width)
                    left += width

    def draw_image(self, context, fsfile, filetype, x, y, width, height):
        pixbuf = self.icons.pixbuf(filetype, int(height))
        if pixbuf is None:
            draw_fallback_icon(context, x, y, width, height, fsfile.isdir())
            return
        left = x + (width - pixbuf.get_width()) / 2.0
        Gdk.cairo_set_source_pixbuf(context, pixbuf, left, y)
        context.paint()

    def draw_text(self, context, text, x, y, width, centre=False):
        layout = self.create_pango_layout(text)
        layout.set_width(int(width * Pango.SCALE))
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        if centre:
            layout.set_alignment(Pango.Alignment.CENTER)
        context.set_source_rgb(0, 0, 0)
        context.move_to(x, y)
        PangoCairo.show_layout(context, layout)

    # --- The pointer

    BUTTONS = {1: 'left', 2: 'middle', 3: 'right'}

    def on_button_press(self, widget, event):
        button = self.BUTTONS.get(event.button)
        if button is None or event.type == Gdk.EventType.TRIPLE_BUTTON_PRESS:
            return False
        self.grab_focus()
        double = (event.type == Gdk.EventType._2BUTTON_PRESS)
        control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        self.frame.pointer_event(self.layout.hit(event.x, event.y), button, double, control, shift, event)
        return True


class GtkExplorerFrame(Gtk.Window):
    """
    An explorer window for a directory.
    """

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

    def __init__(self, fs, dirname, parent=None, explorers=None, display_format=None, sort_order=None,
                 pos=None, size=None, icons=None):
        """
        @param fs:              `FSBase` for the file system
        @param dirname:         Directory to show; raises, before there is a window, if it cannot be read
        @param parent:          Window to place this by, or None
        @param explorers:       Registry of the open windows (`explorers.FSExplorersBase`), or None
        @param display_format:  'large', 'small' or 'fullinfo'
        @param sort_order:      'name', 'size', 'filetype' or 'timestamp'
        @param pos:             Tuple (x, y) to open at, or None
        @param size:            Tuple (width, height) to open with, or None
        @param icons:           The `IconCache` to share with other windows, or None
        """
        # The model raises, before any window is made, if the directory cannot be read
        model = explorer.FSExplorerModel(
                fs, dirname,
                display_format=display_format or self.default_display_format,
                sort_order=sort_order or self.default_sort_order,
                mouse_model_riscos=self.mouse_model_riscos,
                support_mkdir=self.support_mkdir,
                support_delete=self.support_delete,
                support_rename=self.support_rename,
                support_refresh=self.support_refresh,
                report_error=lambda title, message: self.report_error(title, message),
                confirm=lambda title, message, cancel_default=False: self.confirm(title, message,
                                                                                  cancel_default=cancel_default))
        super(GtkExplorerFrame, self).__init__()
        self.model = model
        self.fs = fs
        self.parent_frame = parent
        self.explorers = explorers
        self.icons = icons or IconCache()
        self._title_text = None
        self._frametitle_text = None
        self.debug = False
        self.menu = None

        self.set_default_size(*(size or (self.default_width, self.default_height)))
        if pos:
            self.move(int(pos[0]), int(pos[1]))

        self.panel = IconPanel(self, self.icons)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.panel)
        self.add(scroll)

        self.update_title()
        self.connect("delete-event", self.on_delete)
        self.connect("key-press-event", self.on_key_press)
        self.register()

    # --- Properties of the model

    @property
    def dirname(self):
        return self.model.dirname

    @property
    def files(self):
        return self.model.files

    @property
    def display_format(self):
        return self.model.display_format

    @property
    def sort_order(self):
        return self.model.sort_order

    # --- Titles

    def title_text(self):
        """
        The title shown at the top of the window, in the panel.
        """
        return self._title_text or self.model.title()

    def set_title_text(self, title):
        self._title_text = title
        self.redraw()

    def frame_title_text(self):
        text = self._frametitle_text or self.title_text()
        if self.model.stale:
            # The directory could not be read when it was last refreshed, so what is shown is old
            text += " (not available)"
        return text

    def set_frame_title_text(self, text):
        self._frametitle_text = text
        self.update_title()

    def update_title(self):
        self.set_title(self.frame_title_text())

    # --- Drawing and the registry

    def register(self):
        if self.explorers:
            self.explorers.window_has_closed(self.dirname)
            self.explorers.window_has_opened(self.dirname, self)

    def redraw(self):
        """
        Draw the window again from the model.
        """
        self.panel.rebuild()
        self.update_title()

    def on_delete(self, widget, event):
        if self.explorers:
            self.explorers.window_has_closed(self.dirname)
        self.destroy()
        return True

    # The window protocol, which the registry of windows (explorers.FSExplorersBase) uses.

    def show_window(self):
        self.show_all()
        self.present()

    def raise_window(self):
        self.present()

    def close_window(self):
        self.on_delete(self, None)

    # --- The selection

    def select_file(self, leafname, state=True):
        """
        @param state:   True to select, False to deselect, None to toggle
        """
        if self.model.select(leafname, state):
            self.panel.queue_draw()

    def select_all(self, state=True):
        if state:
            self.model.select_all()
        else:
            self.model.deselect_all()
        self.panel.queue_draw()

    def deselect_all(self):
        self.select_all(state=False)

    def selected_files(self):
        return self.model.selected()

    def apply_selected_files(self, func):
        # The files are taken first, as the function may change the directory
        for fsfile in self.model.selected():
            func(fsfile)

    # --- The pointer and keys

    def pointer_event(self, index, button, double, control, shift=False, event=None):
        """
        A click on the panel.

        @param index:   Index of the icon it is on, or None if it is on the background
        @param button:  'left', 'middle' or 'right'
        @param double:  True for a double click
        @param control: True if Control was held
        @param shift:   True if Shift was held
        @param event:   The GDK event, to place a menu by (or None)
        """
        self.model.mouse_model_riscos = self.mouse_model_riscos
        action = self.model.click_to_button(button, double=double, control=control)
        if self.debug:
            print("Click: Button=%r" % (action,))

        if index is None:
            # A plain click on the background should deselect everything,
            # but not if adjust is pressed. Adjust is 'amend the selection'
            # so amending on nothing should leave things alone.
            if action in ('D-SELECT', 'D-ADJUST', 'SELECT'):
                self.deselect_all()
            elif action == 'MENU':
                self.on_file_menu(None, event)
            return

        fsfile = self.model.files[index]
        leafname = fsfile.leafname
        if action == 'D-SELECT':
            # Run object (deselect item first)
            self.select_file(leafname, False)
            self.on_file_activate(fsfile, close=False, shift=shift)

        elif action == 'D-ADJUST':
            # Run object and close window
            self.on_file_activate(fsfile, close=True, shift=shift)

        elif action == 'SELECT':
            self.deselect_all()
            self.select_file(leafname, True)

        elif action == 'ADJUST':
            self.select_file(leafname, None)

        elif action == 'MENU':
            if not self.model.is_selected(leafname):
                self.deselect_all()
                self.select_file(leafname, True)
            self.on_file_menu(fsfile, event)

    def on_key_press(self, widget, event):
        control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        key = Gdk.keyval_to_lower(event.keyval)
        if control and key == Gdk.KEY_a:
            self.select_all()
            return True
        if control and key == Gdk.KEY_r:
            if self.support_refresh:
                GLib.idle_add(self.refresh_directory)
            return True
        if control and key == Gdk.KEY_n:
            if self.model.capabilities().mkdir_enabled:
                self.show_create_directory()
            return True
        return False

    # --- The menu

    def menu_item(self, menu, label, callback=None, accel=None, check=None, enabled=True):
        """
        Add an item to a menu.

        @param accel:   Text for the accelerator shown beside the label (like 'ctrl-A'), or None
        @param check:   None for an ordinary item, otherwise whether the check item is ticked
        """
        if check is None:
            item = Gtk.MenuItem()
        else:
            item = Gtk.CheckMenuItem()
            item.set_active(bool(check))
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        box.pack_start(text, True, True, 0)
        if accel:
            hint = Gtk.Label(label=accel)
            hint.get_style_context().add_class('dim-label')
            box.pack_end(hint, False, False, 0)
        item.add(box)
        # What the item says, for anything which wants to describe the menu
        item.explorer_label = label
        item.explorer_accel = accel
        item.set_sensitive(bool(enabled))
        if callback:
            item.connect("activate", lambda item: callback())
        menu.append(item)
        return item

    def build_menu(self, caps):
        """
        Make the menu, given what the model says it offers.
        """
        menu = Gtk.Menu()

        display = Gtk.Menu()
        self.menu_item(display, 'Large icons', lambda: self.set_display_format('large'),
                       check=self.display_format == 'large')
        self.menu_item(display, 'Small icons', lambda: self.set_display_format('small'),
                       check=self.display_format == 'small')
        self.menu_item(display, 'Full info', lambda: self.set_display_format('fullinfo'),
                       check=self.display_format == 'fullinfo')
        display.append(Gtk.SeparatorMenuItem())
        for (label, order) in (('Sort by name', 'name'), ('Sort by size', 'size'),
                               ('Sort by file type', 'filetype'), ('Sort by date/time', 'timestamp')):
            self.menu_item(display, label, lambda order=order: self.set_sort_order(order),
                           check=self.sort_order == order)
        self.submenu_item(menu, 'Display', display)

        selection = Gtk.Menu()
        self.add_selection_items(selection, caps)
        if caps.rename_shown:
            self.menu_item(selection, 'Rename...', self.show_rename, enabled=caps.rename_enabled)
        if caps.delete_shown:
            self.menu_item(selection, 'Delete', self.on_selection_delete, enabled=caps.delete_enabled)
        self.menu_item(selection, 'Info', self.on_selection_info)
        selection_item = self.submenu_item(menu, caps.selection_label, selection)
        selection_item.set_sensitive(caps.selection_enabled)

        self.menu_item(menu, 'Select all', self.select_all, accel='ctrl-A')
        self.menu_item(menu, 'Clear selection', self.deselect_all, enabled=caps.clear_enabled)
        if caps.mkdir_shown:
            self.menu_item(menu, 'New directory...', self.show_create_directory, accel='ctrl-N',
                           enabled=caps.mkdir_enabled)
        self.menu_item(menu, 'Open parent', self.open_parent_directory, enabled=bool(caps.parent))
        if caps.refresh_shown:
            self.menu_item(menu, 'Refresh directory', self.refresh_directory, accel='ctrl-R')
        menu.show_all()
        return menu

    def submenu_item(self, menu, label, submenu):
        item = Gtk.MenuItem(label=label)
        item.explorer_label = label
        item.explorer_accel = None
        item.set_submenu(submenu)
        menu.append(item)
        return item

    def add_selection_items(self, menu, caps):
        """
        Overloadable: Add the items which a subclass has at the top of the selection menu.
        """
        pass

    def on_file_menu(self, fsfile, event=None):
        """
        Open the menu, over a file or (with None) the window.
        """
        if self.debug:
            print("Menu: %r" % (fsfile,))
        self.menu = self.build_menu(self.model.capabilities(fsfile))
        self.popup_menu(self.menu, event)

    def popup_menu(self, menu, event=None):
        """
        Overloadable: Show the menu at the pointer.
        """
        if event is not None:
            menu.popup_at_pointer(event)
        else:
            menu.popup_at_pointer(None)

    # --- Operations

    def report_error(self, title, message):
        """
        Overloadable: Report a failure to the user.
        """
        dialog = Gtk.MessageDialog(transient_for=self, message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK, title=title, text=message)
        dialog.run()
        dialog.destroy()

    def confirm(self, title, message, cancel_default=False):
        """
        Overloadable: Offer the user an OK/Cancel box to make a choice from.

        @return: True if OK selected, False if CANCEL selected
        """
        dialog = Gtk.MessageDialog(transient_for=self, message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL, title=title, text=message)
        if cancel_default:
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def ask_text(self, title, prompt, default=''):
        """
        Overloadable: Ask the user for some text.

        @return: The text, or None if they cancelled
        """
        dialog = Gtk.Dialog(title=title, transient_for=self)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_border_width(8)
        box.set_spacing(6)
        box.pack_start(Gtk.Label(label=prompt), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        text = entry.get_text()
        dialog.destroy()
        return text if response == Gtk.ResponseType.OK else None

    def show_create_directory(self):
        leafname = self.ask_text("Create new directory", "New directory name:", "Directory")
        if not leafname:
            # If they didn't give anything, just ignore as if they cancelled it.
            return
        if self.model.mkdir(leafname):
            self.redraw()

    def show_rename(self):
        selection = self.selected_files()
        if not selection:
            return
        fsfile = selection[0]
        leafname = self.ask_text("New filename (within the current directory)", "Rename file:", fsfile.leafname)
        if not leafname:
            return
        if self.model.rename(fsfile.leafname, leafname):
            self.redraw()

    def refresh_directory(self):
        """
        Read the directory again. If it cannot be read, that is reported and the window keeps the
        files that it had.
        """
        if self.model.refresh():
            self.redraw()

    def change_directory(self, dirname):
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
        self.register()
        self.redraw()
        return True

    def set_display_format(self, display_format):
        if self.model.set_display_format(display_format):
            self.redraw()

    def set_sort_order(self, sort_order):
        if self.model.set_sort_order(sort_order):
            self.redraw()

    def next_frame_pos(self, counter=0):
        """
        Where the next window opens, stepping from this one.
        """
        (offset_x, offset_y) = explorer.cascade_offset(counter, self.open_offset_x, self.open_offset_y)
        (x, y) = self.get_position()
        return (x + offset_x, y + offset_y)

    def on_file_activate(self, fsfile, close=False, shift=False):
        activation = self.model.activate(fsfile, close=close, shift=shift)
        if activation.action == explorer.OPEN_DIRECTORY:
            self.on_file_open_dir(fsfile, close=activation.close)
        else:
            self.on_file_run(fsfile, activation.shift)

    def on_file_run(self, fsfile, shift):
        """
        Overloadable: Run a file. Does nothing by default.
        """
        pass

    def on_file_open_dir(self, fsfile, close=False):
        target = fsfile.filename
        if self.explorers:
            openwindow = self.explorers.find_window(target)
            if openwindow:
                openwindow.raise_window()
                if close:
                    self.close_window()
                return

        if close:
            self.change_directory(target)
        else:
            self.open_explorer(target, pos=self.next_frame_pos())

    def open_explorer(self, target, pos=None):
        """
        Open a window for a directory, or raise the one there is. A directory which cannot be read
        is reported, and no window is opened.
        """
        if not pos:
            pos = self.next_frame_pos()
        try:
            self.explorers.open_window(target, pos,
                                       display_format=self.display_format,
                                       sort_order=self.sort_order)
        except Exception as exc:
            self.report_error("Failed to open directory", str(exc))

    def open_parent_directory(self, pos=None):
        target = self.model.parent_dirname()
        if target:
            self.open_explorer(target, pos)

    def on_selection_info(self):
        def open_each(fsfile):
            self.on_file_info(fsfile, counter=open_each.counter)
            open_each.counter += 1
        open_each.counter = 0

        self.apply_selected_files(open_each)

    def on_selection_delete(self):
        if self.model.delete():
            self.redraw()

    def on_file_info(self, fsfile, counter=0):
        pos = self.next_frame_pos(counter)
        try:
            if self.explorers:
                self.explorers.open_fileinfo(fsfile.filename, pos=pos)
            else:
                GtkFileInfoFrame(self, fsfile, pos=pos).show_window()
        except Exception as exc:
            self.report_error("Failed to show information", str(exc))

    # The window protocol of the operations that drive the main window (the sysrqs, in Pyromaniac)

    def refresh(self):
        self.refresh_directory()

    def open_directory(self, dirname):
        self.open_explorer(dirname)

    def activate(self, fsfile):
        self.on_file_activate(fsfile)

    def show_info(self, fsfile):
        self.on_file_info(fsfile)


class GtkExplorers(FSExplorersBase):
    """
    The registry of the explorer windows and information windows that are open.
    """
    explorer_frame_cls = GtkExplorerFrame
    fileinfo_frame_cls = GtkFileInfoFrame

    def __init__(self, fs):
        super(GtkExplorers, self).__init__(fs)
        self.icons = IconCache()

    def create_explorer(self, dirname, pos=None, display_format=None, sort_order=None):
        return self.explorer_frame_cls(self.fs, dirname, explorers=self, pos=pos,
                                       display_format=display_format, sort_order=sort_order,
                                       icons=self.icons)

    def create_fileinfo(self, filename, pos=None):
        fsfile = self.fs.fileinfo(filename)
        return self.fileinfo_frame_cls(self, fsfile, explorers=self, pos=pos)
