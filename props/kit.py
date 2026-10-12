"""The cell-space kit the prop modules share.

Same helpers as `scenery`, with the one that has to know the scale:

    cline(d, x0, y0, x1, y1, colour, width)

A line width is in CELLS, and a width authored for a ten-cell tile is half as thick on a
twenty-cell tile -- which is a stroke the area-average eats. The prop modules are authored
on the base tile and scaled by `ART`, so their widths have to scale with it; measured on
the rescaled set, the thin pieces (dead bush, reeds, torch, ladder) fell to 19-22% ink
against 33-56% for the rest before this existed.

`scenery` is imported INSIDE the function: scenery imports these modules while it builds,
so the import has to be late or the two would chase each other.
"""

import weapons as wk


def cline(d, x0, y0, x1, y1, colour, width=1.0):
    import scenery as sc                      # late: see the module docstring
    return wk.cline(d, x0, y0, x1, y1, colour, width * sc.art_scale())


crect, cpoly, cellipse, circle = wk.crect, wk.cpoly, wk.cellipse, wk.circle
