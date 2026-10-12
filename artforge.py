#!/usr/bin/env python3
"""artforge -- generate isometric text-art pieces (props, tiles, actors) for a
character-grid game engine such as isoforge.

Pipeline (the house one, from the pirate-ship page): draw the piece with PIL on a
supersampled canvas, area-average it down to the character grid, pick the glyph
from the luminance over a ramp, keep the average colour per cell. A piece is what
the engine receives: a small grid of (glyph, colour) plus an ANCHOR -- the cell
where the piece touches the ground.

Two rules learned the hard way, both encoded below:

  * Draw in CELL units, never in raw supersampled pixels. A character cell is
    UX = CELL_W * SS pixels wide at SS=4; anything thinner than ~0.6 cell is
    averaged away and the trunk simply disappears from the finished piece.
  * Auto-level the luminance per piece before choosing glyphs. A dark palette
    (bark, foliage) sits low on the ramp and comes out as sparse punctuation;
    stretching the piece to its own p10..p99 spread is what makes a mass read as
    a mass. The engine gets the glyphs already baked, so this costs nothing at
    run time.

Usage:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 artforge.py [--seed N] [--preview]

Outputs:
    assets/trees.json   the catalogue (the contract with the engine)
    trees.html          the contact sheet to look at

Code is English (identifiers, comments, JSON keys); the copy the reader sees on
the page is Portuguese.
"""

import argparse
import json
import math
import os
import random

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_JSON = os.path.join(ASSETS, "trees.json")
OUT_HTML = os.path.join(HERE, "trees.html")

VERSION = "0.2.0"
DEFAULT_SEED = 20261012

# --- cell geometry, measured in the browser (SF Mono 11 px, line-height 1) ----
CELL_W, CELL_H = 6.62, 11.0
CELL_ASPECT = CELL_H / CELL_W          # ~1.66: a cell is taller than it is wide
SS = 4                                 # supersampling
UX = CELL_W * SS                       # one cell wide, in supersampled pixels
UY = CELL_H * SS                       # one cell tall

# --- ramp and curve ----------------------------------------------------------
RAMP = " .'-:_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@"
GLYPH_GAMMA = 1.15
QUANT = 4                              # colour quantisation, groups equal runs

# Cells darker than this are empty: the page lets its own background show
# through, exactly like an engine treats a transparent cell.
EMPTY_LUM = 9.0
LEVEL_LO, LEVEL_HI = 0.08, 0.99        # per-piece luminance percentiles


# --- colour ------------------------------------------------------------------
def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def boost(c, sat=1.24, gain=1.60, lift=15):
    """Ink boost. A glyph only covers part of its cell, so the perceived
    brightness sits well below the declared colour; every art colour goes
    through this exactly once, at authoring time.

    The numbers are the engine's (isometric-browser-engine), not the weaker ones
    from the look test: measured on this catalogue, gain 1.06 / lift 5 left the
    inked cells at p50 luminance 73 with a p10 of 17 -- a thin subject (a bare
    tree, a palm trunk) simply disappeared against a dark page."""
    m = (c[0] + c[1] + c[2]) / 3.0
    out = []
    for i in range(3):
        v = (m + (c[i] - m) * sat) * gain + lift
        out.append(0 if v < 0 else (255 if v > 255 else int(round(v))))
    return tuple(out)


def shade(c, k):
    return tuple(max(0, min(255, int(round(v * k)))) for v in c)


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def quant(c, q=QUANT):
    return tuple(min(255, int(round(v / q)) * q) for v in c)


def hexcol(c):
    return "#%02x%02x%02x" % c


# --- drawing helpers (supersampled pixel space) ------------------------------
def ell(d, cx, cy, rx, ry, color):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=color)


def poly(d, pts, color):
    d.polygon(pts, fill=color)


# --- iso conventions ----------------------------------------------------------
# The camera looks DOWN at the scene, and that is the whole difference between a
# piece that reads as isometric and one that reads as a flat sticker:
#   * anything horizontal -- a crown seen from above, a shadow, a trunk's
#     footprint -- projects as an ellipse WIDER THAN TALL, the same 2:1 as the
#     tile diamond;
#   * a rounded body shows a LIT TOP face and a darker rim, never a flat disc;
#   * a vertical trunk is NOT foreshortened, so a tall tree is a tall trunk under
#     a wide flat crown.
ISO_FLAT = 0.5


def flat(d, cx, cy, rx, color, ratio=ISO_FLAT):
    """A disc lying in the ground plane, as the projection shows it."""
    ell(d, cx, cy, rx, rx * ratio, color)


def foot(d, cx, gy, half, color):
    """Trunk base. A trunk cut off by the ground line reads as a flat sticker; an
    elliptical base at the ground is what puts it in the plane."""
    ell(d, cx, gy - half * 0.34, half * 1.5, half * 0.78, color)


def blob(d, cx, cy, rx, ry, color):
    """A body: flat fill, a lifted patch up-left (the light), a sunk patch
    down-right. Without the two patches the mass samples down to a disc."""
    ell(d, cx, cy, rx, ry, color)
    ell(d, cx - rx * 0.26, cy - ry * 0.30, rx * 0.60, ry * 0.56, shade(color, 1.30))
    ell(d, cx + rx * 0.30, cy + ry * 0.32, rx * 0.52, ry * 0.46, shade(color, 0.74))


def leaf_mass(d, rng, cx, cy, rx, pal):
    """A crown the way an isometric camera sees it: a squashed disc with a lit top
    face, a darker rim, and a fringe that spreads SIDEWAYS -- the vertical is the
    foreshortened axis, and an upright fringe is exactly the mistake that makes a
    tree read as 2D. Only the horizontal radius is asked for: the projection
    decides the other one."""
    ry = rx * ISO_FLAT
    ell(d, cx, cy + ry * 0.20, rx, ry, pal["leaf_dark"])
    ell(d, cx, cy, rx * 0.97, ry * 0.94, pal["leaf"])
    ell(d, cx, cy - ry * 0.44, rx * 0.74, ry * 0.54, mix(pal["leaf"], pal["leaf_light"], 0.55))
    ell(d, cx - rx * 0.26, cy - ry * 0.52, rx * 0.34, ry * 0.28, pal["leaf_light"])
    for _ in range(36):
        a = rng.uniform(0, math.tau)
        px = cx + math.cos(a) * rx * rng.uniform(0.84, 1.10)
        py = cy + math.sin(a) * ry * rng.uniform(0.84, 1.10)
        r = rng.uniform(0.26, 0.55) * UY * 0.5
        # Light from ABOVE, slightly left: the whole top edge of the disc is lit and
        # the whole bottom edge is in shade. Weighting the right side down instead
        # (a purely lateral light) is what left the topmost row of the crown dimmer
        # than the row under it -- and "the top face is the brightest" is the cue
        # that says the camera is looking down at the mass.
        lit = -math.sin(a) - math.cos(a) * 0.35
        col = shade(pal["leaf"], 1.45 if lit > 0.55 else (0.58 if lit < -0.35 else 1.0))
        ell(d, px, py, r, r, col)


# --- species -----------------------------------------------------------------
# Every routine draws into a box of PXW x PXH supersampled pixels, ground at
# ground_y, trunk centred on cx. All sizes are expressed in CELLS (UX wide,
# UY tall), which is what keeps a trunk visible after the downsample.

def pal_trunk(brown):
    b = boost(brown)
    return {"trunk": b, "trunk_dark": shade(b, 0.68), "trunk_light": shade(b, 1.26)}


def tapered_trunk(d, cx, gy, top_y, half_base, half_top, t, flare=1.45):
    poly(d, [(cx - half_base * flare, gy), (cx + half_base * flare, gy),
             (cx + half_top, top_y), (cx - half_top, top_y)], t["trunk_dark"])
    poly(d, [(cx - half_base, gy), (cx + half_base, gy),
             (cx + half_top * 0.82, top_y), (cx - half_top * 0.82, top_y)], t["trunk"])
    poly(d, [(cx - half_base, gy), (cx - half_base * 0.42, gy),
             (cx - half_top * 0.40, top_y), (cx - half_top * 0.82, top_y)], t["trunk_light"])


def sp_oak(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    top_y = gy - h * 0.70 * UY
    foot(d, cx, gy, 0.62 * UX, t["trunk_dark"])
    tapered_trunk(d, cx, gy, top_y, 0.62 * UX, 0.34 * UX, t)
    for side in (-1, 1):
        d.line([(cx, gy - h * 0.30 * UY), (cx + side * w * 0.30 * UX, gy - h * 0.52 * UY)],
               fill=t["trunk_dark"], width=int(0.5 * UX))
    # A wide, flat cluster of masses. With the vertical foreshortened, a species
    # has to differ in the WIDTH of the crown and in how the masses layer, not in
    # how tall the blob is. Drawn back to front, so the near ones occlude.
    rx = w * 0.42 * UX
    cy = gy - h * 0.64 * UY
    leaf_mass(d, rng, cx - rx * 0.78, cy - rx * 0.06, rx * 0.56, pal)
    leaf_mass(d, rng, cx + rx * 0.76, cy - rx * 0.10, rx * 0.54, pal)
    leaf_mass(d, rng, cx + rx * 0.06, cy - rx * 0.32, rx * 0.66, pal)
    leaf_mass(d, rng, cx - rx * 0.18, cy + rx * 0.16, rx * 0.74, pal)
    leaf_mass(d, rng, cx + rx * 0.36, cy + rx * 0.12, rx * 0.58, pal)


def sp_pine(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    foot(d, cx, gy, 0.42 * UX, t["trunk_dark"])
    tapered_trunk(d, cx, gy, gy - h * 0.34 * UY, 0.44 * UX, 0.30 * UX, t)
    tiers = 6
    span_top = gy - h * 0.95 * UY
    span_bot = gy - h * 0.16 * UY
    band = (span_bot - span_top) / tiers
    for i in range(tiers):
        f = i / float(tiers - 1)                       # 0 at the base, 1 at the tip
        y1 = span_bot - i * band * 0.92
        y0 = max(span_top, y1 - band * 1.50)
        half = (0.52 * w * UX) * (1.0 - f) ** 1.15 + 0.06 * w * UX
        # Lit from above: the TIP is the highest surface, so it is the brightest,
        # and each tier darkens toward the base -- the tier above shades the one
        # below. The other way round (dark tip, bright base) reads as a flat
        # triangle seen head-on.
        col = mix(pal["leaf_dark"], pal["leaf_light"], 0.25 + 0.55 * f)
        # cone body, lit on the left slope
        poly(d, [(cx - half, y1), (cx + half, y1), (cx + half * 0.18, y0), (cx - half * 0.18, y0)],
             mix(col, pal["leaf_dark"], 0.34))
        poly(d, [(cx - half, y1), (cx, y1), (cx, y0), (cx - half * 0.18, y0)],
             mix(col, pal["leaf_light"], 0.30))
        # The bottom rim of the tier is an ELLIPSE. It is the only place where the
        # projection shows on a conifer, and it is what makes the tiers read as
        # stacked discs seen from above instead of a flat triangle.
        flat(d, cx, y1, half, mix(col, pal["leaf_light"], 0.22))
        flat(d, cx, y1 + band * 0.16, half * 0.92, mix(col, pal["leaf_dark"], 0.58))
    ell(d, cx, span_top + 0.08 * UY, 0.20 * UX, 0.11 * UY, mix(pal["leaf_light"], (255, 255, 255), 0.35))


def sp_birch(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    trunk_h = h * 0.62 * UY
    half = 0.52 * UX
    foot(d, cx, gy, half, t["trunk_dark"])
    poly(d, [(cx - half * 1.7, gy), (cx + half * 1.7, gy),
             (cx + half * 0.8, gy - trunk_h), (cx - half * 0.8, gy - trunk_h)], t["trunk_dark"])
    d.rectangle([cx - half, gy - trunk_h, cx + half, gy], fill=(232, 230, 216))
    d.rectangle([cx - half, gy - trunk_h, cx - half * 0.30, gy], fill=(248, 246, 234))
    for i in range(6):
        y = gy - trunk_h * (0.10 + 0.15 * i)
        d.line([(cx - half, y), (cx + half * 0.9, y)], fill=(74, 70, 62), width=int(0.34 * UY))
    for side in (-1, 1):
        d.line([(cx, gy - trunk_h * 0.70), (cx + side * w * 0.26 * UX, gy - trunk_h - 0.3 * UY)],
               fill=(90, 84, 72), width=int(0.42 * UX))
    cy = gy - trunk_h - 0.9 * UY
    rx = w * 0.34 * UX
    leaf_mass(d, rng, cx - rx * 0.66, cy + rx * 0.14, rx * 0.52, pal)
    leaf_mass(d, rng, cx + rx * 0.64, cy + rx * 0.06, rx * 0.50, pal)
    leaf_mass(d, rng, cx, cy - rx * 0.26, rx * 0.62, pal)


def sp_dead(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    top_y = gy - h * 0.66 * UY
    foot(d, cx, gy, 0.70 * UX, t["trunk_dark"])
    tapered_trunk(d, cx, gy, top_y, 0.70 * UX, 0.38 * UX, t)
    legs = ((152, 0.46, 0.52), (28, 0.50, 0.58), (122, 0.40, 0.74), (58, 0.38, 0.80),
            (176, 0.30, 0.36), (6, 0.28, 0.40))
    for (a, ln, start) in legs:
        rad = math.radians(a)
        sx = cx
        sy = gy - h * start * UY
        ex = sx + math.cos(rad) * w * ln * UX
        ey = sy - math.sin(rad) * h * ln * 0.52 * UY
        mx = (sx + ex) * 0.5 + rng.uniform(-0.4, 0.4) * UX
        my = (sy + ey) * 0.5 + rng.uniform(-0.3, 0.3) * UY
        # A branch thinner than ~0.6 cell is averaged away: the piece arrives as
        # a faint smudge and the tree reads as a pole.
        wide = int(0.62 * UX)
        d.line([(sx, sy), (mx, my)], fill=t["trunk"], width=wide)
        d.line([(mx, my), (ex, ey)], fill=t["trunk_dark"], width=max(2, wide - int(0.14 * UX)))
        for fork in (-1, 1):
            fex = ex + fork * 0.18 * w * UX
            fey = ey - 0.30 * h * 0.42 * UY
            d.line([(ex, ey), (fex, fey)], fill=t["trunk_dark"], width=max(2, wide - int(0.22 * UX)))


def sp_bush(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    for i in range(3):
        bx = cx + (i - 1) * w * 0.14 * UX
        d.line([(bx, PXH), (bx + rng.uniform(-0.3, 0.3) * UX, PXH - h * 0.70 * UY)],
               fill=t["trunk"], width=int(0.44 * UX))
    # A shrub is a mound in the ground plane: wide, low, and its bottom edge on the
    # ground line. Its silhouette is the widest of any species per unit of height.
    rx = w * 0.42 * UX
    ry = rx * ISO_FLAT
    leaf_mass(d, rng, cx, gy - ry * 0.94, rx, pal)
    leaf_mass(d, rng, cx - rx * 0.88, gy - ry * 0.52, rx * 0.50, pal)
    leaf_mass(d, rng, cx + rx * 0.86, gy - ry * 0.58, rx * 0.52, pal)


def sp_palm(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    top_y = gy - h * 0.74 * UY
    bend = w * 0.08 * UX
    foot(d, cx, gy, 0.66 * UX, t["trunk_dark"])
    steps = 16
    for i in range(steps + 1):
        f = i / float(steps)
        x = cx + bend * f * f
        y = gy + (top_y - gy) * f
        half = (0.62 - 0.18 * f) * UX
        seg = mix(t["trunk_dark"], t["trunk"], min(1.0, f * 1.3))
        d.rectangle([x - half * 1.6, y - 0.22 * UY, x + half * 1.6, y + 0.22 * UY], fill=t["trunk_dark"])
        d.rectangle([x - half, y - 0.20 * UY, x + half, y + 0.20 * UY], fill=seg)
        if i % 2 == 0:
            d.rectangle([x - half, y - 0.20 * UY, x - half * 0.30, y + 0.20 * UY], fill=t["trunk_light"])
    hx, hy = cx + bend, top_y
    fronds = 9
    for i in range(fronds):
        a = math.radians(-168 + i * (156.0 / (fronds - 1)))
        ln = w * (0.60 if i % 2 == 0 else 0.50) * UX
        # The fan lies in the horizontal plane, so its VERTICAL spread is the
        # foreshortened one (ISO_FLAT) and the horizontal is not.
        droop = 0.30 * h * 0.42 * UY * ISO_FLAT if i in (0, fronds - 1) else 0.0
        ex = hx + math.cos(a) * ln
        ey = hy + math.sin(a) * ln * ISO_FLAT + droop
        # A frond drawn as a needle tapering to a point samples down to a few
        # scattered cells and the crown stops reading as a fan. Blunt blades do.
        thick = 0.50 * UY
        tip = thick * 0.42
        col = pal["leaf_light"] if i % 2 == 0 else pal["leaf"]
        poly(d, [(hx, hy + thick * 0.5), (ex, ey - tip), (ex, ey + tip), (hx, hy - thick * 0.5)], col)
        poly(d, [(hx, hy), (ex, ey - tip * 0.45), (ex, ey + tip * 0.45)],
             mix(col, pal["leaf_dark"], 0.55))
    # the skirt: dead fronds hanging under the crown, which is what joins the
    # fan to the trunk instead of leaving it floating above it
    for side in (-1, 1):
        poly(d, [(hx, hy), (hx + side * 0.9 * UX, hy + 0.5 * UY),
                 (hx + side * 1.5 * UX, hy + 1.5 * UY), (hx + side * 0.5 * UX, hy + 0.9 * UY)],
             pal["leaf_dark"])
    # the hub is a disc in the ground plane, not a ball
    flat(d, hx, hy, 0.52 * UX, t["trunk_dark"])
    flat(d, hx, hy, 0.34 * UX, pal["leaf_dark"])


def sp_willow(d, rng, w, h, PXW, PXH, cx, gy, pal):
    t = pal_trunk(pal["brown"])
    top_y = gy - h * 0.48 * UY
    foot(d, cx, gy, 0.62 * UX, t["trunk_dark"])
    tapered_trunk(d, cx, gy, top_y, 0.62 * UX, 0.36 * UX, t)
    cy = gy - h * 0.56 * UY
    rx = w * 0.44 * UX
    leaf_mass(d, rng, cx, cy, rx, pal)
    # The curtain hangs in the vertical, which this projection does NOT shorten --
    # it is the one part of a willow that keeps its length in this view, and that
    # is what still tells a willow from an oak.
    for _ in range(54):
        a = rng.uniform(0, math.tau)
        sx = cx + math.cos(a) * rx * rng.uniform(0.50, 1.02)
        ln = h * rng.uniform(0.22, 0.50) * UY * (1.0 - 0.30 * abs(math.cos(a)))
        drift = rng.uniform(-0.5, 0.5) * UX
        col = pal["leaf_light"] if rng.random() < 0.32 else pal["leaf_dark"]
        d.line([(sx, cy + rx * ISO_FLAT * 0.5), (sx + drift, cy + rx * ISO_FLAT * 0.5 + ln)],
               fill=col, width=int(0.34 * UX))


SPECIES = [
    # id, Portuguese label, drawing routine, base cell size at "medium", palette,
    # contact-shadow horizontal radius in cells (medium) -- the prop's footprint
    ("oak", "carvalho", sp_oak, (12, 14),
     {"brown": (96, 68, 44), "leaf": (54, 96, 44), "leaf_light": (104, 148, 62),
      "leaf_dark": (28, 58, 30)}, 4.6),
    ("pine", "pinheiro", sp_pine, (11, 16),
     {"brown": (88, 62, 40), "leaf": (38, 78, 56), "leaf_light": (86, 130, 82),
      "leaf_dark": (20, 44, 34)}, 4.2),
    ("birch", "bétula", sp_birch, (10, 13),
     {"brown": (104, 92, 74), "leaf": (96, 132, 52), "leaf_light": (152, 182, 84),
      "leaf_dark": (52, 84, 34)}, 3.6),
    ("dead", "árvore seca", sp_dead, (11, 13),
     {"brown": (110, 96, 80), "leaf": (90, 86, 76), "leaf_light": (140, 134, 118),
      "leaf_dark": (60, 56, 50)}, 3.8),
    ("bush", "arbusto", sp_bush, (11, 6),
     {"brown": (90, 66, 42), "leaf": (48, 88, 44), "leaf_light": (98, 140, 60),
      "leaf_dark": (26, 52, 28)}, 4.8),
    ("palm", "palmeira", sp_palm, (13, 17),
     {"brown": (118, 92, 58), "leaf": (44, 104, 52), "leaf_light": (112, 168, 72),
      "leaf_dark": (24, 62, 34)}, 4.0),
    ("willow", "salgueiro", sp_willow, (13, 15),
     {"brown": (92, 78, 56), "leaf": (74, 112, 58), "leaf_light": (130, 164, 84),
      "leaf_dark": (40, 72, 36)}, 4.8),
    ("autumn", "carvalho de outono", sp_oak, (12, 14),
     {"brown": (94, 64, 40), "leaf": (150, 92, 34), "leaf_light": (206, 148, 52),
      "leaf_dark": (104, 46, 22)}, 4.6),
]

SIZES = [("small", "pequena", 0.68), ("medium", "média", 1.0), ("large", "grande", 1.34)]


# --- piece building ----------------------------------------------------------
def draw_piece(routine, pal, rng, w, h):
    PXW = int(round(w * UX))
    PXH = int(round(h * UY))
    img = Image.new("RGB", (PXW, PXH), (0, 0, 0))
    d = ImageDraw.Draw(img)
    # The trunk centre sits at the CENTRE OF A CELL, never on a cell boundary:
    # split across two cells it would sample as two half-lit cells and the
    # contact row would land one cell off the anchor.
    anchor_x = w // 2
    cx = (anchor_x + 0.5) * UX
    gy = PXH - UY * 0.12                      # the ground line, near the bottom edge
    routine(d, rng, w, h, PXW, PXH, cx, gy, pal)
    # The contact cell is inked by construction, whatever the species drew: a
    # prop whose anchor row is empty floats in the game, and no amount of
    # geometry luck should be what prevents that.
    d.rectangle([cx - 0.5 * UX, PXH - UY * 0.85, cx + 0.5 * UX, PXH], fill=boost(pal["brown"]))
    return img, anchor_x


def percentile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def to_cells(img, w, h, anchor_x):
    """Area-average down to cells, crop tight to the inked bbox, then choose
    glyphs from the piece's own luminance spread."""
    resample = getattr(Image, "Resampling", Image).BOX
    small = img.resize((w, h), resample)
    raw = [[small.getpixel((x, y)) for x in range(w)] for y in range(h)]
    lums = [[lum(c) for c in row] for row in raw]

    cols = [x for x in range(w) if any(lums[y][x] >= EMPTY_LUM for y in range(h))]
    rws = [y for y in range(h) if any(lums[y][x] >= EMPTY_LUM for x in range(w))]
    if not cols or not rws:                      # cannot happen with the contact rule
        raise RuntimeError("piece is entirely empty")
    x0, x1, y0, y1 = min(cols), max(cols), min(rws), max(rws)
    cw, ch = x1 - x0 + 1, y1 - y0 + 1

    kept = [lums[y][x] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if lums[y][x] >= EMPTY_LUM]
    lo = max(EMPTY_LUM, percentile(kept, 0.02))
    hi = percentile(kept, LEVEL_HI)
    span = max(1.0, hi - lo)

    rows = []
    for y in range(y0, y1 + 1):
        glyphs = []
        colors = []
        for x in range(x0, x1 + 1):
            c = raw[y][x]
            v = lums[y][x]
            if v < EMPTY_LUM:
                glyphs.append(" ")
                colors.append("")
                continue
            # A cell that survived the empty test MUST produce a glyph: letting
            # the level floor erase it is exactly what leaves a floating piece.
            t = min(1.0, max(0.0, (v - lo) / span)) ** GLYPH_GAMMA
            k = max(1, min(len(RAMP) - 1, int(t * len(RAMP))))
            glyphs.append(RAMP[k])
            colors.append(hexcol(quant(c)))
        rows.append({"g": "".join(glyphs), "c": colors})
    return {"rows": rows, "levels": [round(lo, 1), round(hi, 1)],
            "w": cw, "h": ch,
            "anchor": {"x": anchor_x - x0, "y": ch - 1}}


# --- the contact shadow -------------------------------------------------------
# The shadow is a DECAL, not part of the prop: it is flat, it is drawn together
# with the floor, and it never occludes anything. That is also the only way an
# isometric prop reads as standing IN the scene rather than floating over it.
FLOOR_TONE = (58, 53, 44)       # the stone tone the page paints under the pieces
SHADOW_INK = (26, 24, 20)       # that tone at ~45%: what the decal paints
SHADOW_LADDER = (" ", "░", "▒", "▓", "█")


def build_shadow(rx_cells):
    """An ellipse lying in the ground plane. On SCREEN it has to come out 2:1, so
    in CELLS the half-height is rx * CELL_W / (2 * CELL_H) -- a cell is 1.66x
    taller than it is wide, and ignoring that is how a flat shadow turns into a
    ball.

    A cell of text can only hold a shape that is a whole cell tall, and a flat disc
    is often LESS than one cell tall. That is what the half blocks are for: `▄` and
    `▀` carry two sub-pixels of vertical resolution inside one cell, so the disc
    stays flat instead of being inflated to the nearest whole row.

    The ANCHOR is the CENTRE of the ellipse, not the bottom row: the anchor is the
    cell that goes to the tile centre, and a disc on the ground straddles that
    point -- half of it toward the viewer, half of it away."""
    ry_cells = rx_cells * CELL_W / (2.0 * CELL_H)
    sub = 2                                  # sub-rows per cell: the half blocks
    rows = max(1, int(math.ceil(ry_cells * 2)) * sub // sub)
    if rows % 2 == 0:
        rows += 1                            # odd, so there is a true centre row
    sub_rows = rows * sub
    w_cells = max(3, int(math.ceil(rx_cells * 2)) + 1)
    sub_h = UY / float(sub)
    mask = Image.new("L", (int(round(w_cells * UX)), int(round(sub_rows * sub_h))), 0)
    d = ImageDraw.Draw(mask)
    cx = mask.width / 2.0
    cy = (rows // 2 * sub + sub / 2.0) * sub_h
    d.ellipse([cx - rx_cells * UX, cy - ry_cells * UY,
               cx + rx_cells * UX, cy + ry_cells * UY], fill=255)
    small = mask.resize((w_cells, sub_rows), getattr(Image, "Resampling", Image).BOX)
    px = small.load()
    out = []
    for y in range(rows):
        glyphs, colors = [], []
        for x in range(w_cells):
            top = px[x, 2 * y] / 255.0
            bot = px[x, 2 * y + 1] / 255.0
            if top > 0.62 and bot > 0.62:
                g = "█"
            elif bot > 0.62:
                g = "▄"
            elif top > 0.62:
                g = "▀"
            else:
                avg = (top + bot) / 2.0
                g = "▓" if avg > 0.55 else "▒" if avg > 0.30 else "░" if avg > 0.10 else " "
            glyphs.append(g)
            colors.append(hexcol(SHADOW_INK) if g != " " else "")
        out.append({"g": "".join(glyphs), "c": colors})
    return {"w": w_cells, "h": rows, "anchor": {"x": w_cells // 2, "y": rows // 2},
            "disc": {"rx": round(rx_cells, 3), "ry": round(ry_cells, 3)}, "cells": out}


def build_set(seed):
    pieces = []
    discs = {}                                   # radius -> decal, shared by every prop
    for (sid, label, routine, base_cells, raw_pal, shadow_rx) in SPECIES:
        pal = {
            "brown": boost(raw_pal["brown"]),
            "leaf": boost(raw_pal["leaf"]),
            "leaf_light": boost(raw_pal["leaf_light"]),
            "leaf_dark": boost(raw_pal["leaf_dark"]),
        }
        for (size_id, size_label, scale) in SIZES:
            w = max(5, int(round(base_cells[0] * scale)))
            h = max(5, int(round(base_cells[1] * scale)))
            piece_seed = (seed * 7919 + sum(ord(ch) for ch in sid) * 131 + int(scale * 1000)) & 0xFFFFFFFF
            rng = random.Random(piece_seed)
            img, anchor_x = draw_piece(routine, pal, rng, w, h)
            built = to_cells(img, w, h, anchor_x)
            rows = built["rows"]
            inked = sum(1 for r in rows for g in r["g"] if g != " ")
            colors = sorted({c for r in rows for c in r["c"] if c})
            prop_id = "tree.%s.%s" % (sid, size_id)
            # The shadow is a function of the DISC, not of the species: one decal per
            # distinct radius, shared by every prop that needs it. Emitting one per
            # tree filled the bank with identical art under different ids -- six
            # pairs of them on the first run.
            radius = round(shadow_rx * scale, 2)
            shadow_id = "shadow.disc.r%g" % radius
            if shadow_id not in discs:
                shadow = build_shadow(radius)
                discs[shadow_id] = {
                    "id": shadow_id,
                    "kind": "decal",
                    "layer": "ground",
                    "w": shadow["w"],
                    "h": shadow["h"],
                    "anchor": shadow["anchor"],
                    "disc": shadow["disc"],
                    "frames": 1,
                    "directions": 1,
                    "cells": shadow["cells"],
                    "stats": {"inkedCells": sum(1 for r in shadow["cells"] for g in r["g"]
                                                if g != " "),
                              "cellCount": shadow["w"] * shadow["h"], "colors": 1},
                }
            pieces.append({
                "id": prop_id,
                "kind": "prop",
                "species": sid,
                "label": label,
                "size": size_id,
                "size_label": size_label,
                "w": built["w"],
                "h": built["h"],
                "drawBox": [w, h],
                "anchor": built["anchor"],
                "shadow": shadow_id,
                "frames": 1,
                "directions": 1,
                "levels": built["levels"],
                "cells": rows,
                "stats": {"inkedCells": inked, "cellCount": built["w"] * built["h"],
                          "colors": len(colors), "seed": piece_seed},
            })
    pieces.extend(discs[key] for key in sorted(discs))
    return pieces


# --- output ------------------------------------------------------------------
def text_of(piece):
    return "\n".join(r["g"] for r in piece["cells"])


def write_json(pieces, seed):
    payload = {
        "version": 1,
        "generator": "artforge %s" % VERSION,
        "set": "trees",
        "label": "Árvores estáticas",
        "kinds": ["prop", "decal"],
        "seed": seed,
        "cell": {"w": CELL_W, "h": CELL_H, "aspect": round(CELL_ASPECT, 4)},
        "isoFlat": ISO_FLAT,
        "floorTone": hexcol(FLOOR_TONE),
        "shadowInk": hexcol(SHADOW_INK),
        "ramp": RAMP,
        "glyphGamma": GLYPH_GAMMA,
        "quant": QUANT,
        "pieces": pieces,
    }
    os.makedirs(ASSETS, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    return payload


HTML_HEAD = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>artforge — catálogo de árvores</title>
<style>
  :root {
    --panelw: min(1240px, calc(100vw - 48px));
    --fs: __FS__px;
    --bg: #05070a; --panel: #0b0f14; --line: #1c2430; --floor: __FLOOR__;
    --ink: #e9e5d8; --dim: #8b8f92; --accent: #cfa855;
    --mono: "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 34px 24px 56px; color: var(--ink); font-family: var(--mono);
         line-height: 1.5; background: radial-gradient(120% 70% at 50% 0%, #111a26 0%, var(--bg) 58%, #030405 100%); }
  .wrap { width: var(--panelw); margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 6px; }
  .lede { color: var(--dim); font-size: 12.5px; margin: 0 0 18px; max-width: 98ch; }
  .lede b { color: var(--accent); font-weight: 600; }
  .card { border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
          margin-bottom: 18px; overflow: hidden; }
  .cap { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline; padding: 9px 14px;
         border-bottom: 1px solid var(--line); font-size: 11.5px; color: var(--dim); }
  .cap b { color: var(--accent); font-weight: 600; }
  /* The pieces are shown ON the floor they will be composited over: a shadow can
     only be judged against the surface it darkens. */
  .art { padding: 12px 14px 10px; overflow-x: auto; background: var(--floor); }
  .nofloor .art { background: #05070a; }
  pre { margin: 0; font-family: var(--mono); font-size: var(--fs); line-height: 1;
        white-space: pre; font-variant-ligatures: none; -webkit-font-smoothing: antialiased;
        text-shadow: 0 0 1px rgba(0,0,0,.6); }
  pre i { font-style: normal; }
  .ground { border-top: 1px dashed #2b3644; margin: 0 14px 12px; }
  .mono .art { background: #05070a; }
  .mono pre i { color: #d2cdbe !important; }
  footer { color: var(--dim); font-size: 11.5px; border-top: 1px solid var(--line); padding-top: 12px; }
  code { color: var(--accent); }
  .bar { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 16px; }
  button { font: inherit; font-size: 11.5px; color: var(--ink); background: #101721;
           border: 1px solid var(--line); border-radius: 6px; padding: 5px 11px; cursor: pointer; }
  button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
</style></head><body><div class="wrap">
<h1>artforge — catálogo de árvores</h1>
<p class="lede">__LEDE__</p>
<div class="bar">
  <button id="bColor" aria-pressed="true">cores</button>
  <button id="bFloor" aria-pressed="true">piso</button>
  <button id="bGround" aria-pressed="true">linha de base</button>
</div>
"""


def run_length_html(rows):
    """One span per run of equal colour; empty cells go through as spaces so the
    page background shows. Runs break on colour, never on glyph."""
    out = []
    inked = 0
    for row in rows:
        glyphs, colors = row["g"], row["c"]
        parts = []
        start = 0
        key = None
        for x in range(len(glyphs) + 1):
            col = colors[x] if x < len(glyphs) else "\x00"
            if col != key:
                if key is not None and x > start:
                    text = glyphs[start:x]
                    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    if key == "" or not text.strip():
                        parts.append(esc)
                    else:
                        inked += len(text)
                        parts.append('<i style="color:%s">%s</i>' % (key, esc))
                start = x
                key = col
        out.append("".join(parts))
    return "\n".join(out), inked


def write_html(payload, pieces):
    props = [p for p in pieces if p["kind"] == "prop"]
    decals = {p["id"]: p for p in pieces if p["kind"] == "decal"}
    groups = []
    for (sid, label, _routine, _base, _pal, _shadow) in SPECIES:
        group = [p for p in props if p["species"] == sid]
        if group:
            groups.append((sid, label, group))

    widest = max(sum(p["w"] for p in g) + 4 * (len(g) - 1) for _s, _l, g in groups)
    fs = max(5.0, min(19.0, (1240 * 0.94) / (widest * 0.6)))

    total_inked = sum(p["stats"]["inkedCells"] for p in props)
    lede = ("%d peças: %d espécies × 3 tamanhos, semente <b>%d</b>. Cada quadro é uma espécie e as "
            "três árvores apoiam na <b>mesma linha de base</b>. A copa é um <b>disco achatado</b> "
            "(mais largo que alto) com a face de cima iluminada, o tronco tem <b>pé elíptico</b> e "
            "cada árvore traz a <b>mancha</b> de contato — plana, desenhada com o piso, nunca oclui. "
            "Peça = grade de glifos + cor por célula + âncora (<code>anchor</code> e "
            "<code>shadow</code> no <code>assets/trees.json</code>)."
            % (len(props), len(groups), payload["seed"]))

    html = [HTML_HEAD.replace("__FS__", ("%.2f" % fs).rstrip("0").rstrip("."))
            .replace("__FLOOR__", payload["floorTone"]).replace("__LEDE__", lede)]
    for (sid, label, group) in groups:
        height = max(p["h"] for p in group)
        gap = 4
        width = sum(p["w"] for p in group) + gap * (len(group) - 1)
        # The ground row is FIXED: every prop anchors on its own last row, so the
        # tallest tree in the panel puts the ground at height - 1. Only the frame
        # grows -- the near half of a shadow lands BELOW that row, and the panel
        # needs those rows or the shadow is cut in half.
        ground = height - 1
        below = max(decals[p["shadow"]]["h"] - 1 - decals[p["shadow"]]["anchor"]["y"] for p in group)
        total_rows = height + below
        canvas = [[" "] * width for _ in range(total_rows)]
        colors = [[""] * width for _ in range(total_rows)]
        cursor = 0
        placed = []
        for p in group:
            base = ground - p["anchor"]["y"]     # top row of the prop on the canvas
            # The decal is painted FIRST: it lies in the ground plane with the
            # floor, and the prop then stands on top of it. Both are placed by
            # their ANCHOR, not by their box: that is the cell that goes to the
            # tile centre, and it is the only alignment that survives a piece
            # whose crown is off-centre (a palm bends) or whose shadow straddles
            # the ground.
            shadow = decals.get(p.get("shadow"))
            if shadow:
                sh_x = cursor + p["anchor"]["x"] - shadow["anchor"]["x"]
                sh_y = ground - shadow["anchor"]["y"]
                for y, row in enumerate(shadow["cells"]):
                    wy = sh_y + y
                    for x in range(shadow["w"]):
                        wx = sh_x + x
                        if row["g"][x] == " " or not (0 <= wx < width and 0 <= wy < total_rows):
                            continue
                        canvas[wy][wx] = row["g"][x]
                        colors[wy][wx] = row["c"][x]
            for y, row in enumerate(p["cells"]):
                wy = base + y
                for x in range(p["w"]):
                    if row["g"][x] == " ":
                        continue
                    canvas[wy][cursor + x] = row["g"][x]
                    colors[wy][cursor + x] = row["c"][x]
            placed.append("<span>%s %d×%d</span>" % (p["size_label"], p["w"], p["h"]))
            cursor += p["w"] + gap
        rows = [{"g": "".join(r), "c": colors[y]} for y, r in enumerate(canvas)]
        body, inked = run_length_html(rows)
        cap = ("<span><b>%s</b> · %s</span>" % (label, sid)
               + "".join(placed)
               + "<span>tinta: %d células</span>" % inked
               + "<span>altura: %d células ≈ %d px</span>" % (height, int(height * CELL_H)))
        html.append('<section class="card" id="s-%s">\n  <div class="cap">%s</div>\n'
                    '  <div class="art"><pre>%s</pre></div>\n'
                    '  <div class="ground"></div>\n</section>' % (sid, cap, body))

    html.append("<footer>Gerado por <code>artforge.py</code> · catálogo em <code>assets/trees.json</code> "
                "· rampa de %d caracteres · %d células de tinta · piso do painel <code>%s</code>, "
                "mancha <code>%s</code> · <b>cores</b> deixa só o glifo e <b>piso</b> apaga o chão, "
                "para julgar a silhueta e a sombra separadamente."
                % (len(RAMP), total_inked, payload["floorTone"], payload["shadowInk"]))
    html.append("""
<script>
  var colorOn = true, groundOn = true, floorOn = true;
  document.getElementById("bColor").addEventListener("click", function () {
    colorOn = !colorOn;
    this.setAttribute("aria-pressed", colorOn ? "true" : "false");
    document.body.classList.toggle("mono", !colorOn);
  });
  document.getElementById("bFloor").addEventListener("click", function () {
    floorOn = !floorOn;
    this.setAttribute("aria-pressed", floorOn ? "true" : "false");
    document.body.classList.toggle("nofloor", !floorOn);
  });
  document.getElementById("bGround").addEventListener("click", function () {
    groundOn = !groundOn;
    this.setAttribute("aria-pressed", groundOn ? "true" : "false");
    document.querySelectorAll(".ground").forEach(function (el) {
      el.style.display = groundOn ? "block" : "none";
    });
  });
</script>
""")
    html.append("</div></body></html>")
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write("\n".join(html))
    return fs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    pieces = build_set(args.seed)
    payload = write_json(pieces, args.seed)
    fs = write_html(payload, pieces)

    print("artforge %s -- %d pieces, seed %d" % (VERSION, len(pieces), args.seed))
    print("  json : %s (%.0f KB)" % (os.path.relpath(OUT_JSON, HERE), os.path.getsize(OUT_JSON) / 1024.0))
    print("  html : %s (%.0f KB, font %.2f px)" % (os.path.relpath(OUT_HTML, HERE),
                                                   os.path.getsize(OUT_HTML) / 1024.0, fs))
    print()
    print("  %-24s %7s %6s %6s %6s %s" % ("id", "cells", "inked", "ink%", "cols", "levels"))
    for p in pieces:
        if p["kind"] != "prop":
            continue
        s = p["stats"]
        print("  %-24s %2dx%-4d %6d %5.0f%% %6d %s" % (p["id"], p["w"], p["h"], s["inkedCells"],
                                                       100.0 * s["inkedCells"] / s["cellCount"],
                                                       s["colors"], p["levels"]))
    decals = [p for p in pieces if p["kind"] == "decal"]
    print()
    print("  %d manchas (decals): %s" % (
        len(decals), ", ".join("%dx%d" % (d["w"], d["h"]) for d in decals[:6]) + " …"))
    print("  mancha: um disco no plano do chão (%s sobre o piso %s), 2:1 na tela, 1 cor, sem auto-níveis"
          % (hexcol(SHADOW_INK), hexcol(FLOOR_TONE)))
    if args.preview:
        for p in pieces:
            print()
            print("--- %s  (%dx%d, anchor %d,%d) ---"
                  % (p["id"], p["w"], p["h"], p["anchor"]["x"], p["anchor"]["y"]))
            print(text_of(p))


if __name__ == "__main__":
    main()
