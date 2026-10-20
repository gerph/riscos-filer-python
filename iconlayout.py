"""
Where the icons of an explorer window go.

An explorer that draws its own icons (as the GTK one does, rather than having a widget for each)
needs to know where each icon is, to draw it and to tell which one a click is on. That is all
arithmetic on the sizes of the cells, so it is here with no toolkit: the toolkit measures its
text and icons, makes the cells that big, and asks where they go.

The icons are in rows, left to right and then down, wrapping at the width of the panel; every
cell is the same size, as they are in the RISC OS filer.
"""


class IconLayout(object):
    """
    The positions of a number of equally sized cells in a panel of a given width.
    """

    def __init__(self, cell_width, cell_height, spacing=8, margin=8):
        """
        @param cell_width:  Width of every cell
        @param cell_height: Height of every cell
        @param spacing:     Space between one cell and the next, across and down
        @param margin:      Space between the cells and the edge of the panel (and the top)
        """
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.spacing = spacing
        self.margin = margin
        self.rects = []
        self.columns = 1
        self.height = 0

    def layout(self, count, panel_width, top=0):
        """
        Place the cells.

        @param count:       Number of cells
        @param panel_width: Width available
        @param top:         Space to leave above the cells (for a title)

        @return: The height the panel needs, so that all the cells are visible
        """
        usable = panel_width - 2 * self.margin
        self.columns = max(1, (usable + self.spacing) // (self.cell_width + self.spacing))
        self.rects = []
        for index in range(count):
            (row, column) = divmod(index, self.columns)
            self.rects.append((self.margin + column * (self.cell_width + self.spacing),
                               top + self.margin + row * (self.cell_height + self.spacing),
                               self.cell_width, self.cell_height))
        rows = (count + self.columns - 1) // self.columns
        self.height = top + 2 * self.margin
        if rows:
            self.height += rows * self.cell_height + (rows - 1) * self.spacing
        return self.height

    def hit(self, x, y):
        """
        Which cell is at a position.

        @return: Index of the cell, or None if the position is not in a cell
        """
        # The cells are in a grid, so the one it can be is worked out; the spaces between are no cell
        if not self.rects:
            return None
        first = self.rects[0]
        column = (x - first[0]) // (self.cell_width + self.spacing)
        row = (y - first[1]) // (self.cell_height + self.spacing)
        if x < first[0] or y < first[1] or column >= self.columns:
            return None
        index = row * self.columns + column
        if index >= len(self.rects):
            return None
        (left, top, width, height) = self.rects[index]
        if left <= x < left + width and top <= y < top + height:
            return index
        return None
