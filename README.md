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
raised if they are re-opened whilst they are open.

The icons for the files are provided in the `icons` directory.


## Example

An example app, `app.py` is provided, which demonstrates the use of the frame, and
which is used for manually testing the behaviour.
