#!/usr/bin/env python3
"""povoado -- four village / outdoors props for the artforge scenery set.

Same problem as every prop in scenery.py: a piece that STANDS ON A TILE, so its foot
is the centre of its bottom row, its box is in CELLS, and it is drawn with the cell
kit from weapons.py. The difference from the rocks and the barrels is what has to
read at a glance:

  * a WELL is a stone drum under an open mouth: if the mouth is missing it is a post,
    and if the drum is missing it is a puddle. The two together are the read.
  * a FOGUEIRA is a ring of stones + crossed wood + a bright flame. The flame alone is
    a smear on the dark page; the stones are what anchor it to the ground.
  * a PLACA is a post with BOARDS on it -- the boards are the read, and a post without
    them is a fence post.
  * a CERCA is POSTS PLUS TRAVESSAS. Neither survives alone: posts with no rails read
    as a row of sticks, rails with no posts as a plank in the air.

Three rules from the iterations (all mandatory, all encoded here):

  * NO STROKE THINNER THAN ~0.15 CELL. A thinner one is averaged away by the
    downsample and the piece arrives with a hole where the foot or the shaft was.
    Every band, joint and border below is at least a quarter of a cell.
  * LIGHT ON TOP/LEFT (metal_light), body (metal), SHADE BELOW/RIGHT and in the joints
    (metal_dark). A piece in one colour reads as a blob, not as a thing.
  * INK between 20% and 85% of the box. Under it the piece is a ghost, over it a brick.

Determinism: the only randomness is the hearth stones, drawn from a FIXED seed.

The manifest is NEW_PROPS, at the END of this file -- a table of callables has to follow
the definitions, so the four routines come first and the table closes the module.

Usage (staging file -- it defines the routines, it does not build the set):
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 - <<'EOF'
    import sys; sys.path.insert(0, '/Users/davizimmer/Projetos/artforge')
    import artforge as af, weapons as wk, scenery as sc
    from PIL import Image, ImageDraw
    sys.path.insert(0, '/Users/davizimmer/Projetos/artforge/tools/staging')
    import povoado as g
    EOF
"""

import math
import random

import weapons as wk
import scenery as sc

from props.kit import cline, crect, cpoly, cellipse, circle

G = sc.GROUND                       # the material table (grass, stone, wood, flame, ...)
HEARTH_SEED = 20261012              # the hearth stones: fixed, so the piece never drifts


# --- 1. the well ---------------------------------------------------------------
def p_well(d, w, h):
    """A stone drum with an open mouth, under a wooden frame.

    Read order, back to front: the frame beam, the two posts, then the drum and the
    mouth on top. The mouth is concentric flat ellipses -- a bright rim (the top
    surface, catching the light from above) closing on a dark hole -- because a well
    is recognised by its MOUTH, and a mouth drawn as one disc is a table.
    """
    cx = w / 2.0
    base = h - 0.5
    stone, wood, water = G["stone"], G["wood"], G["water"]
    # The hole is sunk BELOW the palette's own dark: the material's metal_dark lands
    # only ~20 luminance under the rim's shadow ring, which samples as one flat disc.
    # A well reads by its mouth, so the mouth has to be a bright ring around a real hole.
    deep = wk.shade(water["metal_dark"], 0.25)
    rim_cy = h * 0.56                                # the mouth, just above the middle

    # --- the frame behind: two posts and a beam over them ---------------------
    for side in (-1, 1):
        px = cx + side * w * 0.32
        crect(d, px - 0.7, h * 0.13, px + 0.7, rim_cy + 0.3, wood["metal"])
        crect(d, px - 0.7, h * 0.13, px - 0.2, rim_cy + 0.3, wood["metal_light"])
        crect(d, px + 0.3, h * 0.13, px + 0.7, rim_cy + 0.3, wood["metal_dark"])
    crect(d, cx - w * 0.42, h * 0.05, cx + w * 0.42, h * 0.14, wood["metal"])
    crect(d, cx - w * 0.42, h * 0.05, cx + w * 0.42, h * 0.095, wood["metal_light"])
    crect(d, cx - w * 0.42, h * 0.12, cx + w * 0.42, h * 0.14, wood["metal_dark"])

    # --- the drum: lit on the left, jointed down the middle, shaded on the right
    crect(d, cx - w * 0.32, rim_cy, cx + w * 0.32, base, stone["metal"])
    crect(d, cx - w * 0.32, rim_cy, cx - w * 0.19, base, stone["metal_light"])
    crect(d, cx + w * 0.21, rim_cy, cx + w * 0.32, base, stone["metal_dark"])
    for y in (rim_cy + h * 0.14, rim_cy + h * 0.28):                 # courses of masonry
        cline(d, cx - w * 0.30, y, cx + w * 0.30, y, stone["metal_dark"], 0.5)

    # --- the mouth: flat rings, the lit rim closing on the hole ---------------
    # The hole is ~2 cells tall on purpose: an ellipse under one cell never fills a
    # cell, so it averages against the lit rim on both sides and the well arrives as a
    # disc with a smudge on it instead of an opening.
    cellipse(d, cx, rim_cy, w * 0.41, h * 0.185, stone["metal"])        # the outer lip
    cellipse(d, cx, rim_cy, w * 0.35, h * 0.160, stone["metal_light"])  # the lit top face
    cellipse(d, cx, rim_cy, w * 0.30, h * 0.140, stone["metal_dark"])   # inner wall in shade
    cellipse(d, cx, rim_cy, w * 0.24, h * 0.110, deep)                  # the hole


# --- 2. the campfire -----------------------------------------------------------
def p_campfire(d, w, h):
    """Hearth stones in a ring, wood crossed over them, and a clear flame above.

    The stones are drawn BACK TO FRONT (sorted by y) so the near ones overlap the far
    ones: that is the only cue that the ring lies in the ground plane. The flame is a
    teardrop in the flame metal with a bright core in flame_light -- the light is what
    makes it a flame and not an orange blob.
    """
    cx = w / 2.0
    base = h - 0.5
    rng = random.Random(HEARTH_SEED)
    stone, wood, flame = G["stone"], G["wood"], G["flame"]

    # --- the ring of hearth stones -------------------------------------------
    ring = []
    for k in range(11):
        a = math.tau * k / 11.0
        ring.append((cx + math.cos(a) * w * 0.37, base - 0.95 - math.sin(a) * h * 0.12))
    ring.sort(key=lambda p: p[1])                     # back first, near ones last
    for (sx, sy) in ring:
        r = 0.60 + rng.uniform(-0.05, 0.05)
        circle(d, sx, sy, r, stone["metal"])
        circle(d, sx - r * 0.26, sy - r * 0.30, r * 0.50, stone["metal_light"])
        circle(d, sx + r * 0.28, sy + r * 0.26, r * 0.46, stone["metal_dark"])

    # --- the logs, crossed ----------------------------------------------------
    for (x0, y0, x1, y1) in ((cx - w * 0.30, base - 1.95, cx + w * 0.30, base - 1.05),
                             (cx + w * 0.30, base - 1.95, cx - w * 0.30, base - 1.05)):
        cline(d, x0, y0, x1, y1, wood["metal"], 1.2)
        cline(d, x0, y0 - 0.42, x1, y1 - 0.42, wood["metal_light"], 0.5)

    # --- the flame: a teardrop with a bright core -----------------------------
    # A cone (widest at the base) reads as a tree; a flame bulges a third of the way
    # up and tapers BOTH ways.
    ftop = h * 0.05
    cpoly(d, [(cx, ftop),
              (cx + w * 0.13, base - 3.50), (cx + w * 0.21, base - 2.50),
              (cx + w * 0.11, base - 1.50),
              (cx - w * 0.11, base - 1.50), (cx - w * 0.21, base - 2.50),
              (cx - w * 0.13, base - 3.50)], flame["metal"])
    cpoly(d, [(cx, ftop + h * 0.16),
              (cx + w * 0.09, base - 3.20), (cx + w * 0.13, base - 2.50),
              (cx + w * 0.06, base - 1.80),
              (cx - w * 0.06, base - 1.80), (cx - w * 0.13, base - 2.50),
              (cx - w * 0.09, base - 3.20)], flame["metal_light"])
    # embers among the stones
    for dx in (-w * 0.22, w * 0.19):
        circle(d, cx + dx, base - 1.45, 0.42, flame["metal_dark"])


# --- 3. the signpost -----------------------------------------------------------
def p_signpost(d, w, h):
    """A thick post carrying two boards.

    The boards are drawn with a dark EDGE and a lit top face: at this width a board in
    one tone is a bar, and the edge is what makes it a plank nailed to a post. The
    post is a full 1.3 cells wide on purpose -- the earlier thin version was averaged
    away and the boards ended up floating.
    """
    cx = w / 2.0
    base = h - 0.5
    wood, plank, iron = G["wood"], G["plank"], G["iron"]
    pw = max(0.6, w * 0.10)

    # --- the post -------------------------------------------------------------
    crect(d, cx - pw, h * 0.06, cx + pw, base, wood["metal"])
    crect(d, cx - pw, h * 0.06, cx - pw * 0.25, base, wood["metal_light"])
    crect(d, cx + pw * 0.35, h * 0.06, cx + pw, base, wood["metal_dark"])

    # --- two boards -----------------------------------------------------------
    for (y0, y1, x0, x1) in ((h * 0.10, h * 0.30, w * 0.05, w * 0.95),
                             (h * 0.42, h * 0.58, w * 0.20, w * 0.95)):
        crect(d, x0, y0, x1, y1, plank["metal_dark"])            # the board's own edge
        crect(d, x0 + 0.4, y0 + 0.45, x1 - 0.4, y1 - 0.4, plank["metal"])
        crect(d, x0 + 0.4, y0 + 0.45, x1 - 0.4, y0 + 1.05, plank["metal_light"])
        crect(d, x0 + 0.4, y1 - 1.0, x1 - 0.4, y1 - 0.4, plank["metal_dark"])
        for k in range(3):                                        # grain
            gx = x0 + (x1 - x0) * (0.20 + 0.28 * k)
            cline(d, gx, y0 + 0.7, gx, y1 - 0.7, plank["metal_dark"], 0.4)
        circle(d, cx, (y0 + y1) * 0.5, 0.5, iron["metal"])        # the nail head
        circle(d, cx - 0.18, (y0 + y1) * 0.5 - 0.22, 0.26, iron["metal_light"])


# --- 4. the fence --------------------------------------------------------------
def p_fence(d, w, h):
    """Three pointed posts and two travessas between them.

    The rails go DOWN FIRST and the posts over them: a rail that crosses in front of a
    post breaks the post's outline and the fence stops reading as a fence. The posts
    keep a lit left face and a shaded right face, the rails a lit top and a shaded
    underside -- one light, from above and to the left, on every part.
    """
    base = h - 0.5
    wood = G["wood"]

    # --- the travessas (rails), behind the posts ------------------------------
    for y in (h * 0.32, h * 0.56):
        th = h * 0.14
        crect(d, w * 0.03, y, w * 0.97, y + th, wood["metal"])
        crect(d, w * 0.03, y, w * 0.97, y + th * 0.32, wood["metal_light"])
        crect(d, w * 0.03, y + th * 0.66, w * 0.97, y + th, wood["metal_dark"])

    # --- the posts, pointed, in front ----------------------------------------
    for px in (w * 0.14, w * 0.50, w * 0.86):
        half = 0.8
        crect(d, px - half, h * 0.10, px + half, base, wood["metal"])
        crect(d, px - half, h * 0.10, px - half * 0.30, base, wood["metal_light"])
        crect(d, px + half * 0.35, h * 0.10, px + half, base, wood["metal_dark"])
        tip = h * 0.01
        cpoly(d, [(px - half, h * 0.115), (px + half, h * 0.115), (px, tip)], wood["metal"])
        cpoly(d, [(px - half, h * 0.115), (px, h * 0.115), (px, tip)], wood["metal_light"])
        cpoly(d, [(px + half * 0.35, h * 0.115), (px + half, h * 0.115), (px, tip)],
              wood["metal_dark"])


# --- the table ------------------------------------------------------------------
# Same shape as scenery.PROPS: (id, label, species, (w, h), routine, shadow_r,
# material, foot). These four are meant to be appended to it.
NEW_PROPS = [
    ("prop.well", "Poço", "well", (12, 9), p_well, 4.0, "stone", "dirt"),
    ("prop.campfire", "Fogueira", "campfire", (11, 8), p_campfire, 3.6, "flame", "dirt"),
    ("prop.signpost", "Placa", "signpost", (8, 12), p_signpost, 2.4, "wood", "dirt"),
    ("prop.fence", "Cerca", "fence", (12, 8), p_fence, 3.6, "wood", "dirt"),
]
