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

ONE THING TO KNOW BEFORE COPYING A SELF-TEST: the modules under props/ were verified with
`weapons.to_cells`, which CENTRES the ink in the box -- right for an item icon, wrong for a
piece of the world. The set samples with `scenery.to_ground`, which does not move the
drawing, because a prop's anchor is its FOOT. A routine authored foot-on-the-last-row is
correct either way; a self-test that uses the centring sampler is not testing the same
thing the set ships, so re-check against `to_ground` before believing it.
"""

import weapons as wk


def cline(d, x0, y0, x1, y1, colour, width=1.0):
    import scenery as sc                      # late: see the module docstring
    return wk.cline(d, x0, y0, x1, y1, colour, width * sc.art_scale())


crect, cpoly, cellipse, circle = wk.crect, wk.cpoly, wk.cellipse, wk.circle
