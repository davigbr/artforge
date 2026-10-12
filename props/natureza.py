#!/usr/bin/env python3
"""natureza -- four natural / underground props for artforge, staged for review.

Same problem as the scenery props, so the same rules: cell-space drawing only (the
kit comes from weapons.py, borrowed rather than forked), a foot on the tile, three
shades per material. What is new here is that three of them are TALL and narrow and one
is SHORT and wide, and that is where the sampling punishes a drawing:

  * a spine, a shard's edge, a rib -- anything much thinner than half a cell is
    averaged away by the area average, and the piece arrives with a hole in it;
  * one colour reads as a stain, so light goes up/left, dark goes down/right and on
    the joints;
  * ink has to land between 20% and 85% of the box: below it the piece is a ghost,
    above it a solid block with no silhouette left;
  * the silhouette has to BREAK. Two shapes drawn from the same mass merge into one
    lump at sampling even when the geometry says they are separate, so every limb
    here is set a clear cell away from the body it grows out of.

Nothing here touches scenery.py. This is a staging file: it defines the four routines
and the table, and the parent set is expected to pick the entries up from NEW_PROPS.

Usage:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/staging/natureza.py
"""

import os
import random
import sys

from PIL import Image, ImageDraw

# The staging dir is not on the path when this file is imported by an audit, and the
# project root is not either when it is run straight off the disk -- find the root by
# looking for artforge.py rather than trusting a relative hop count.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = _HERE
while _ROOT != os.path.dirname(_ROOT) and not os.path.exists(os.path.join(_ROOT, "artforge.py")):
    _ROOT = os.path.dirname(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import artforge as af          # noqa: E402
import scenery as sc           # noqa: E402
import weapons as wk           # noqa: E402

# --- the kit: cells only, never supersampled pixels -------------------------------
from props.kit import cline, crect, cpoly, cellipse, circle       # noqa: E402
shade = af.shade

# The only random source any routine here is allowed to touch, and it is seeded: two
# runs of the same box have to produce the same grid or the audit cannot compare them.
RNG_SEED = 20261015


def m(name):
    """The scenery ground palette for a material: metal / metal_light / metal_dark."""
    return sc.GROUND[name]


# --- 1. cactus -------------------------------------------------------------------
def p_cactus(d, w, h):
    """A saguaro: one column with two arms, and the arms are what makes it a cactus
    and not a green post.

    The arms stand a clear cell off the trunk. Drawn touching it -- which is what the
    first pass did -- the arm and the trunk average into a single seven-cell bar at
    head height and the piece reads as a lump with a bump; the gap column, dimmed by
    the trunk's own edge or empty, is what makes the silhouette say "arm".
    """
    cx = w / 2.0
    base = h - 0.7
    c = m("grass")
    lit, mid, dark = c["metal_light"], c["metal"], c["metal_dark"]

    def limb(x0, y0, x1, y1, edge):
        """A ribbed column: lit left face, dark right face, body between."""
        crect(d, x0, y0, x1, y1, mid)
        crect(d, x0, y0, x0 + edge, y1, lit)
        crect(d, x1 - edge, y0, x1, y1, dark)

    def bend(x0, y0, x1, y1):
        """The horizontal elbow: a cylinder on its side, lit on top."""
        crect(d, x0, y0, x1, y1, mid)
        crect(d, x0, y0, x1, y0 + 0.45, lit)
        crect(d, x0, y1 - 0.45, x1, y1, dark)

    # Both the trunk and the arms sit ON cell boundaries on purpose. An edge at a
    # fractional x is spread over two columns by the area average, and a one-cell arm
    # spread over two columns is no arm at all -- it is the dim smudge that made the
    # gap between arm and trunk disappear.
    tx0, tx1 = cx - 1.5, cx + 1.5                              # trunk: three whole cells
    limb(tx0, h * 0.16, tx1, base, 0.6)

    limb(cx - 3.5, h * 0.20, cx - 2.5, h * 0.62, 0.42)         # left arm, low
    bend(cx - 3.5, h * 0.56, tx0 + 0.5, h * 0.66)

    limb(cx + 2.5, h * 0.09, cx + 3.5, h * 0.44, 0.42)         # right arm, high
    bend(tx1 - 0.5, h * 0.38, cx + 3.5, h * 0.48)

    # areoles: a few lit spots down the trunk. Sparse on purpose -- four of them read
    # as a cactus, ten of them read as noise.
    rng = random.Random(RNG_SEED)
    for k in range(4):
        y = h * (0.72 + 0.070 * k)
        x = cx + rng.choice((-0.60, 0.05))
        crect(d, x, y, x + 0.55, y + 0.5, lit)

    crect(d, tx0 + 0.6, h * 0.16, tx1 - 0.6, h * 0.16 + 0.7, lit)    # lit crown
    crect(d, cx - 1.6, base - 0.6, cx + 1.6, base, dark)             # the root shadow


# --- 2. crystal ------------------------------------------------------------------
def p_crystal(d, w, h):
    """A cluster of shards: one tall, two short, each one a kite with facets.

    A prism painted in a single tone is a blue smear, so each shard is faceted -- left
    face lit, right face dark -- and the shards are spaced a clear cell apart. Set
    edge to edge (the first pass) the three silhouettes fuse into one wide wedge, and
    a wedge is not a crystal.

    Every tip carries a lit cap: with an eight-cell box the true centre falls ON a
    column boundary, so a mathematically sharp point is split between two cells and
    averaged down to nothing -- the cap is what keeps the point a point.
    """
    cx = w / 2.0
    base = h - 0.5
    c = m("water")
    lit, mid, dark = c["metal_light"], c["metal"], c["metal_dark"]
    tip = shade(lit, 1.25)

    def shard(x, tip_y, bot_y, half):
        waist = bot_y - (bot_y - tip_y) * 0.34        # where the shard is widest
        cpoly(d, [(x, tip_y), (x + half, waist), (x + half * 0.80, bot_y),
                  (x - half * 0.80, bot_y), (x - half, waist)], mid)
        cpoly(d, [(x, tip_y), (x - half, waist), (x - half * 0.80, bot_y),
                  (x - half * 0.22, bot_y), (x - half * 0.18, waist)], lit)
        cpoly(d, [(x, tip_y), (x + half, waist), (x + half * 0.80, bot_y),
                  (x + half * 0.22, bot_y), (x + half * 0.18, waist)], dark)
        crect(d, x - 0.5, tip_y, x + 0.5, tip_y + 1.1, tip)        # the lit tip
        crect(d, x - half * 0.55, waist * 0.6, x + half * 0.10, bot_y - 0.4, lit)

    r = m("rock")
    cellipse(d, cx, base - 0.15, w * 0.34, 0.6, r["metal_dark"])
    cellipse(d, cx - w * 0.08, base - 0.32, w * 0.22, 0.42, r["metal"])

    shard(cx - 2.75, h * 0.28, base - 0.6, 0.85)                   # left, short
    shard(cx + 2.60, h * 0.36, base - 0.5, 0.75)                   # right, shorter
    shard(cx, h * 0.04, base - 0.2, 1.25)                          # the tall one


# --- 3. stalagmite ---------------------------------------------------------------
def p_stalagmite(d, w, h):
    """A cave-floor spike: one dominant cone, two smaller spires, drip bands.

    The bands are what separate this from the crystal at a glance -- both are tall
    points, so the stalagmite leans on the GROWTH LINES instead: the layers of
    calcite are drawn as full-width bars, dark below a lit lip, so they survive the
    sampling instead of thinning into a dotted line.
    """
    cx = w / 2.0
    base = h - 0.6
    c = m("stone")
    lit, mid, dark = c["metal_light"], c["metal"], c["metal_dark"]

    def cone(x, tip_y, bot_y, half, bands):
        ws = bot_y - tip_y

        def hw_at(y):
            return half * max(0.0, (y - tip_y) / ws)

        cpoly(d, [(x, tip_y), (x + half, bot_y), (x - half, bot_y)], mid)
        cpoly(d, [(x, tip_y), (x - half, bot_y), (x - half * 0.18, bot_y)], lit)
        cpoly(d, [(x, tip_y), (x + half, bot_y), (x + half * 0.20, bot_y)], dark)
        for f in bands:
            y = tip_y + ws * f
            hw = hw_at(y)
            if hw < 0.75:
                continue
            crect(d, x - hw * 0.95, y, x + hw * 0.95, y + 0.75, dark)
            crect(d, x - hw * 0.72, y - 0.8, x + hw * 0.10, y - 0.10, lit)
        crect(d, x - 0.5, tip_y, x + 0.5, tip_y + 1.1, lit)        # the lit tip

    cone(cx, h * 0.05, base - 0.4, 2.00, (0.30, 0.50, 0.70, 0.88))
    # The two companions are set right out at the box edges and are given height enough
    # to clear the wide part of the big cone. Beside a four-cell cone base there is no
    # room for them to be 'near': anywhere closer and the area average folds them into
    # the big one and the piece is one plain spike (which is what the first pass was).
    cone(cx - 3.45, h * 0.44, base - 0.9, 0.90, (0.55,))
    cone(cx + 3.45, h * 0.50, base - 0.9, 0.80, (0.60,))

    cellipse(d, cx - 0.9, base - 0.10, w * 0.32, 0.5, dark)        # rubble at the foot
    cellipse(d, cx + 1.7, base - 0.05, w * 0.14, 0.4, dark)


# --- 4. bones --------------------------------------------------------------------
def p_bones(d, w, h):
    """Two long bones, crossed, in a five-row box -- the tightest piece here.

    This one was rewritten three times and every rewrite was about the SAMPLING, not
    about the drawing:

      * 10x5 cells is 66 x 55 px on screen. A skull with two sockets needs five cells of
        width to have a bridge between the eyes, and spending five of ten on a skull
        leaves nothing for the bones -- the piece came out as a potato with a tail.
      * `plaster`'s three tones are 255 / 202 / 186 once boosted, i.e. nearly one
        colour: the palette's own `metal_dark` cannot shade bone at all. The rim here is
        a `shade()` of it, the same move weapons.py makes for a helm's vision slit.
      * the crossed pair is the one bone silhouette that survives the box: the read is
        the X plus the thickening at the four ends, and both of those are large shapes.
        A bone laid flat is a plank; a single bone on a shallow diagonal is a tail.
    """
    c = m("plaster")
    lit, mid, dark = c["metal_light"], c["metal"], c["metal_dark"]
    rim = shade(dark, 0.62)

    # Two long bones, crossed. At ten by five cells there is room for the skull OR for
    # the bones, not both -- and a skull squeezed into three rows averages into a blob
    # (measured: the sockets came out mid grey and the piece read as a potato). The
    # crossed bones are the one bone silhouette that survives the box intact, because
    # the read is the X plus the thickening at the four ends.
    #
    # The ends sit on x = 2.1 and x = 8.0 with a 1.10 knob: the left edge of the ink
    # then starts at x = 1.0 and the right at x = 9.1, which puts the centre of ink at
    # x = 5.05 -- the middle of the box. That matters because to_cells RE-CENTRES a
    # piece by whole cells when its ink is not centred, and a piece that is half a cell
    # out gets pushed a whole cell and loses the knob at the far edge.
    ax0, ax1 = 2.1, w * 0.80
    ay0, ay1 = h * 0.88, h * 0.12
    for (x0, y0, x1, y1) in ((ax0, ay0, ax1, ay1), (ax0, ay1, ax1, ay0)):
        cline(d, x0, y0, x1, y1, mid, 0.85)
        cline(d, x0, y0 - 0.28, x1, y1 - 0.28, lit, 0.55)
        cline(d, x0, y0 + 0.26, x1, y1 + 0.26, rim, 0.52)
        for (kx, ky) in ((x0, y0), (x1, y1)):
            circle(d, kx, ky, 1.10, mid)                          # the knobs
            circle(d, kx - 0.24, ky - 0.42, 0.56, lit)
            circle(d, kx + 0.32, ky + 0.38, 0.50, rim)


# --- the table, exactly the values the review asked for --------------------------
# id, label, species, box in cells, routine, contact-shadow radius, material, foot
NEW_PROPS = [
    ("prop.cactus", "Cacto", "cactus", (9, 11), p_cactus, 3.0, "grass", "sand"),
    ("prop.crystal", "Cristal", "crystal", (8, 12), p_crystal, 2.8, "water", "rock"),
    ("prop.stalagmite", "Estalagmite", "stalagmite", (8, 12), p_stalagmite, 3.0, "stone",
     "rock"),
    ("prop.bones", "Ossada", "bones", (10, 5), p_bones, 3.0, "plaster", "dirt"),
]


# --- the review contact sheet (not the parent's job to build this) ---------------
def review():
    """Draw the four pieces, apply each one's own contact patch exactly the way the
    scenery set does, and print the ASCII plus the ink figure."""
    for (pid, label, species, (w, h), routine, shadow_r, material, foot) in NEW_PROPS:
        img = Image.new("RGB", (int(round(w * af.UX)), int(round(h * af.UY))), (0, 0, 0))
        d = ImageDraw.Draw(img)
        routine(d, w, h)
        crect(d, w * 0.34, h - 0.75, w * 0.66, h - 0.05, m(foot)["metal_dark"])
        built = wk.to_cells(img, w, h)
        rows = built["rows"]
        ink = sum(1 for r in rows for ch in r["g"] if ch != " ")
        bottom = [i for i, ch in enumerate(rows[h - 1]["g"]) if ch != " "]
        print("%-16s %-11s %dx%d  tinta %5.0f%%  chao %s  sombra %.1f  %s"
              % (pid, label, w, h, 100.0 * ink / (w * h),
                 "ok" if bottom else "VAZIO", shadow_r, material))
        for r in rows:
            print("|%s|" % r["g"])
        print()


if __name__ == "__main__":
    review()
