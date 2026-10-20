# RISC OS-like file explorer (Filer) in Python

## Introduction

The modules in this repository provide a means by which a scrollable window can be
created which shows files in a similar style to the RISC OS filer. The scrollable
window is implemented in WxPython.

The code was originally written to allow RISC OS Pyromaniac to browse the
file system of the provided OS. It has been extracted to a separate module
as it may be more generally useful.

## Structure

In order to display the explorer window, the source for the files to display must be
provided. This source is based on the `FSBase`, `FSDirectoryBase` and `FSFileBase`
classes in the `fs` module. These classes abstract access to the file system.

The `FSBase` class provides core access to the file system mostly dealing with the
handling of filenames and obtaining access to a directory. The file system can have
different schemes for file names, to allow both POSIX and RISC OS filename conventions
to be used.

The `FSDirectoryBase` class provides enumeration of the files in a directory and
their details. The objects provide access to the files through the `FSFileBase`
objects.

The `FSFileBase` class provides information and access to the files on the file
system.

These 3 classes should be subclassed to get access to the actual file system. The
`fsnative` module provides subclasses for access to the POSIX file system. Within
RISC OS Pyromaniac, similar subclasses provide access to the RISC OS file system.

The `fsexplorer` module contains an `FSExplorerFrame` which provides the implementation
of the file explorer interface. This frame can show the files and open directories
and files. The RISC OS semantics of opening a new window are followed unless the
alternate mouse operation is performed (right-click in RISC OS model, or
control/command left click in the non-RISC OS model). Selections are available and
multiple files can be selected. Activating files by double click is supported but
does nothing in the default implementation.

An `FSExplorers` object may be passed to the `FSExplorerFrame` on creation, to
track the existing explorer windows that have been opened. This allows them to be
raised if they are re-opened whilst they are open. The tracking does not depend on a
toolkit (`explorers.FSExplorersBase`): a window provides `show_window()`,
`raise_window()` and `close_window()`, and the toolkit's subclass makes the windows.

The `explorer` module contains `FSExplorerModel`, which is everything about an explorer
window that does not depend on a toolkit: the directory and its files in the display order,
the display format and sort order, the selection, what the menu offers, how clicks are taken
as RISC OS buttons, and creating a directory, renaming and deleting. It does not import a
toolkit. A window draws the model and passes clicks and menu choices to it, and the model
returns whether the window needs to be drawn again. Failures (including a directory that
has gone) are reported through a function that is passed in, and the model keeps what it
had, so the window stays usable. The tests in `tests` run against a file system held in
memory, and need no toolkit.

The icons for the files are provided in the `icons` directory.

## GTK

The `gtkexplorer` module provides the same explorer for GTK 3 (PyGObject): `GtkExplorerFrame`, with
`GtkExplorers` to track the windows, and `gtkinfo` for the file information window. To look like the
RISC OS filer, the icons are drawn by the window itself rather than by the standard GTK icon or list
views (`iconlayout` works out where they go, with no toolkit). The SVG icons are loaded through GdkPixbuf
if it can read SVG, and a plain shape is drawn if it cannot. The mouse models and the menu are those
of the WxWidgets explorer.

`gtkapp.py` is an example which browses a directory with no emulator; `--riscos-mouse` selects the RISC OS
mouse model.


## Example

An example app, `app.py` is provided, which demonstrates the use of the frame, and
which is used for manually testing the behaviour.
