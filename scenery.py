#!/usr/bin/env python3
"""scenery -- the set the world is made of: floor, blocks, props and decals, so an
environment can be composed (interior or exterior).

Different problem from a tree and from an item, and the hard part is in the floor:

  * a FLOOR TILE must tile WITH ITSELF. In a text grid that means the pattern has to be
    periodic with the tile: the last column and the first column of the next tile have to
    continue one another. Done here by drawing the texture with every feature also at the
    +/- w and +/- h offsets ("wrapped"), so the field is toroidal before it is sampled.
  * a BLOCK has HEIGHT: a top face and two side faces, which is what the engine's
    WALL_HEIGHT_CELLS asks for.
  * a PROP stands on a tile, so it has a FOOT and a contact shadow, like a tree.
  * a DECAL is drawn with the floor and never occludes: a path, a patch of moss, a puddle.

The cell-space drawing kit (cpoly, crect, cline, cellipse, circle, pal, to_cells) lives in
weapons.py, written for the item set first. Scenery BORROWS it rather than forking a
second copy: one place to fix an aspect correction is one place to be wrong once.

Usage:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 scenery.py
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/scenery_audit.py
    open scenery.html
"""

import argparse
import json
import math
import os
import random

from PIL import Image, ImageDraw

import artforge as af
import weapons as wk

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_JSON = os.path.join(ASSETS, "scenery.json")
OUT_HTML = os.path.join(HERE, "scenery.html")
TREES_JSON = os.path.join(ASSETS, "trees.json")

VERSION = "0.1.0"
DEFAULT_SEED = 20261014

SS = af.SS
UX, UY = af.UX, af.UY
RAMP = af.RAMP

cpoly, crect, cline, cellipse, circle = wk.cpoly, wk.crect, wk.cline, wk.cellipse, wk.circle
pal = wk.pal
# Sampling is to_ground() below, NOT wk.to_cells: that one centres the ink in the box.

# The tile: 12 calls across is 79.4 px and 4 calls down is 44.0 px -- 2:1 on screen, the
# isometry's own proportion, so a floor of these interlocks with nothing but itself.
TILE_W, TILE_H = 12, 4
WALL_ROWS = 4                       # the engine's WALL_HEIGHT_CELLS


# --- ground materials ----------------------------------------------------------
GROUND = {
    "grass": pal(metal=(74, 108, 52), metal_light=(118, 158, 74), metal_dark=(44, 68, 34)),
    "dry_grass": pal(metal=(108, 112, 56), metal_light=(156, 152, 82), metal_dark=(66, 68, 36)),
    "dirt": pal(metal=(96, 70, 46), metal_light=(136, 104, 68), metal_dark=(58, 42, 28)),
    "sand": pal(metal=(176, 152, 104), metal_light=(214, 194, 146), metal_dark=(122, 102, 66)),
    "snow": pal(metal=(196, 204, 214), metal_light=(236, 242, 250), metal_dark=(140, 150, 166)),
    "stone": pal(metal=(112, 112, 118), metal_light=(158, 158, 164), metal_dark=(68, 68, 74)),
    "cobble": pal(metal=(124, 122, 116), metal_light=(170, 168, 160), metal_dark=(74, 72, 68)),
    "plank": pal(metal=(122, 88, 52), metal_light=(164, 122, 74), metal_dark=(74, 52, 30)),
    "moss": pal(metal=(62, 96, 50), metal_light=(104, 146, 68), metal_dark=(36, 58, 32)),
    "brick": pal(metal=(126, 84, 66), metal_light=(168, 116, 92), metal_dark=(78, 50, 40)),
    "plaster": pal(metal=(168, 162, 148), metal_light=(204, 198, 184), metal_dark=(112, 106, 94)),
    "rock": pal(metal=(96, 94, 98), metal_light=(140, 138, 144), metal_dark=(58, 56, 60)),
    "water": pal(metal=(58, 96, 140), metal_light=(96, 148, 190), metal_dark=(34, 58, 92)),
    "wood": pal(metal=(112, 78, 46), metal_light=(154, 114, 66), metal_dark=(60, 40, 24)),
    "iron": pal(metal=(138, 142, 150), metal_light=(196, 200, 208), metal_dark=(70, 74, 82)),
    "flame": pal(metal=(232, 132, 48), metal_light=(252, 214, 120), metal_dark=(186, 74, 28)),
    "cloth": pal(metal=(74, 84, 132), metal_light=(118, 130, 186), metal_dark=(38, 44, 76)),
}


def g(name):
    return GROUND[name]


# --- the tile field, wrapped ---------------------------------------------------
def wrapped(d, w_cells, h_cells, draw_one, count, rng, period=None):
    """Draw `count` features so the field is TOROIDAL with the period given.

    The period is HALF a tile by default, and that is not a detail: with an iso stagger
    the neighbouring tile sits at (+w/2, +h/2), so what has to continue across the shared
    edge is the field shifted by half a tile. A field with only a whole-tile period
    interlocks with a mismatch along the edges -- invisible in ONE tile, visible in a
    floor of them.
    """
    pw, ph = period or (w_cells / 2.0, h_cells / 2.0)
    for _ in range(count):
        cx = rng.uniform(0, w_cells)
        cy = rng.uniform(0, h_cells)
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                draw_one(d, cx + dx * pw, cy + dy * ph, rng)


def diamond_mask(w_cells, h_cells):
    """The iso rhombus: 12 wide and 4 tall in calls is exactly 2:1 on screen, and the
    empty corners are where the neighbouring tiles' rhombi come in."""
    mask = Image.new("L", (int(round(w_cells * UX)), int(round(h_cells * UY))), 0)
    md = ImageDraw.Draw(mask)
    cx, cy = w_cells / 2.0, h_cells / 2.0
    md.polygon([((cx) * UX, 0), (w_cells * UX, cy * UY),
                (cx * UX, h_cells * UY), (0, cy * UY)], fill=255)
    return mask


def tile(w_cells, h_cells, base, speck, features):
    """A floor tile: a base colour, wrapped speckle, then the material's own features."""
    img = Image.new("RGB", (int(round(w_cells * UX)), int(round(h_cells * UY))), base["metal"])
    d = ImageDraw.Draw(img)
    rng = random.Random(7)
    wrapped(d, w_cells, h_cells,
            lambda dd, x, y, r: crect(dd, x - 0.18, y - 0.14, x + 0.18, y + 0.14,
                                      speck["metal"] if (int(x * 3) + int(y * 3)) % 3 else
                                      speck["metal_light"]),
            int(w_cells * h_cells * 1.6), rng)
    features(d, w_cells, h_cells, rng)
    img = Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)),
                          diamond_mask(w_cells, h_cells))
    return img


def to_ground(img, w, h):
    """Sample to cells WITHOUT the item icon's centring shift.

    weapons.to_cells centres the ink in the box -- right for an icon, because an item has
    no ground to stand on, and wrong for everything here: a tile's pattern stops being
    periodic, a block's top stops meeting its walls, and a prop's FOOT moves up a row and
    the anchor row comes out blank. Measured: five props floating above their own shadow
    for exactly this reason. A piece of the world keeps the box exactly as drawn.
    """
    resample = getattr(Image, "Resampling", Image).BOX
    small = img.resize((w, h), resample)
    raw = [[small.getpixel((x, y)) for x in range(w)] for y in range(h)]
    lums = [[af.lum(c) for c in row] for row in raw]
    kept = [lums[y][x] for y in range(h) for x in range(w) if lums[y][x] >= af.EMPTY_LUM]
    lo = max(af.EMPTY_LUM, af.percentile(kept, 0.02)) if kept else af.EMPTY_LUM
    hi = af.percentile(kept, 0.99) if kept else 255.0
    span = max(1.0, hi - lo)
    rows = []
    for y in range(h):
        glyphs, colors = [], []
        for x in range(w):
            c = raw[y][x]
            v = lums[y][x]
            if v < af.EMPTY_LUM:
                glyphs.append(" ")
                colors.append("")
                continue
            t = min(1.0, max(0.0, (v - lo) / span)) ** af.GLYPH_GAMMA
            k = max(1, min(len(RAMP) - 1, int(t * len(RAMP))))
            glyphs.append(RAMP[k])
            colors.append(af.hexcol(af.quant(c)))
        rows.append({"g": "".join(glyphs), "c": colors})
    return {"rows": rows, "levels": [round(lo, 1), round(hi, 1)]}


def quiet(rows, ceiling=0.55):
    """Restrain a background piece to the lower part of the ramp.

    A floor that uses the full range competes with everything standing on it: measured on
    the first pass, the tile's own interior steps (p75 42-84 of luminance) were of the
    same order as a torch's against the ground it stands on. The props are the subject and
    the floor is the surface, and the ramp is where that gets decided.
    """
    top = int(len(RAMP) * ceiling)
    out = []
    for row in rows:
        glyphs = "".join(RAMP[min(RAMP.index(ch), top)] if ch != " " else " "
                         for ch in row["g"])
        out.append({"g": glyphs, "c": row["c"]})
    return out


def f_grass(d, w, h, rng):
    def blade(dd, x, y, r):
        lean = r.choice((-0.22, -0.1, 0.1, 0.22))
        cline(dd, x, y + 0.45, x + lean, y - 0.45,
              g("grass")["metal_light"] if r.random() < 0.45 else g("grass")["metal_dark"],
              0.5)
    wrapped(d, w, h, blade, int(w * h * 2.4), rng)


def f_dry(d, w, h, rng):
    def straw(dd, x, y, r):
        cline(dd, x, y + 0.4, x + r.choice((-0.2, 0.2)), y - 0.4,
              g("dry_grass")["metal_light"], 0.5)
    wrapped(d, w, h, straw, int(w * h * 2.2), rng)


def f_dirt(d, w, h, rng):
    def pebble(dd, x, y, r):
        circle(dd, x, y, r.uniform(0.12, 0.26), g("dirt")["metal_dark"])
    wrapped(d, w, h, pebble, int(w * h * 1.2), rng)


def f_sand(d, w, h, rng):
    # ripples land on the stagger's rows: y=1 and y=3 are the same row of the texture's
    # own period, which is what lets one tile continue into the next
    for y in (1, 3):
        cline(d, 0, y, w, y, g("sand")["metal_dark"], 0.6)


def f_snow(d, w, h, rng):
    def drift(dd, x, y, r):
        cellipse(dd, x, y, r.uniform(0.5, 1.0), r.uniform(0.16, 0.30),
                 g("snow")["metal_light"])
    wrapped(d, w, h, drift, 6, rng)


def f_stone(d, w, h, rng):
    # slab lines every half tile and every period row: 6 divides the 12 and 2 divides the
    # 4, so the slabs continue across tiles without a hiccup
    for x in (6,):
        cline(d, x, 0, x, h, g("stone")["metal_dark"], 0.8)
    for y in (1, 3):
        cline(d, 0, y, w, y, g("stone")["metal_dark"], 0.7)


def f_cobble(d, w, h, rng):
    def stone(dd, x, y, r):
        cellipse(dd, x, y, 0.62, 0.44, g("cobble")["metal_dark"])
        cellipse(dd, x - 0.06, y - 0.08, 0.48, 0.30, g("cobble")["metal_light"])
    for y in (1, 3):
        for x in range(0, w, 2):
            stone(d, x, y, rng)


def f_plank(d, w, h, rng):
    for y in (1, 3):
        cline(d, 0, y, w, y, g("plank")["metal_dark"], 1.0)
        cline(d, 0, y + 0.22, w, y + 0.22, g("plank")["metal_light"], 0.5)

    def knot(dd, x, y, r):
        cellipse(dd, x, y, 0.3, 0.22, g("plank")["metal_dark"])
    wrapped(d, w, h, knot, 6, rng)


def f_water(d, w, h, rng):
    for y in (1, 3):
        cline(d, 0, y, w, y, g("water")["metal_light"], 0.6)


TILES = [
    ("piso.grass", "Grama", "grass", g("grass"), g("grass"), f_grass),
    ("piso.dry_grass", "Capim seco", "dry_grass", g("dry_grass"), g("dry_grass"), f_dry),
    ("piso.dirt", "Terra", "dirt", g("dirt"), g("dirt"), f_dirt),
    ("piso.sand", "Areia", "sand", g("sand"), g("sand"), f_sand),
    ("piso.snow", "Neve", "snow", g("snow"), g("snow"), f_snow),
    ("piso.stone", "Laje de pedra", "stone", g("stone"), g("stone"), f_stone),
    ("piso.cobble", "Calçamento", "cobble", g("cobble"), g("cobble"), f_cobble),
    ("piso.plank", "Assoalho", "plank", g("plank"), g("plank"), f_plank),
    ("piso.water", "Água", "water", g("water"), g("water"), f_water),
]


# --- blocks: a cube, so a wall has a top and two faces --------------------------
def iso_block(w_cells, top, left, right, face_feature=None, rng=None):
    """The engine's block: the top rhombus and the two faces below it. Drawn with the
    tile's own width and the tile's own height for the top face, so a wall sits on the
    floor grid: the first version drew the rhombus 12 wide and 6 tall, which is not a
    rhombus at 2:1 but a block standing on a taller block."""
    half_h = TILE_H / 2.0
    h_cells = int(TILE_H + WALL_ROWS)
    img = Image.new("RGB", (int(round(w_cells * UX)), int(round(h_cells * UY))), (0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w_cells / 2.0
    cpoly(d, [(cx, 0), (w_cells, half_h), (cx, half_h * 2), (0, half_h)], top["metal"])
    cpoly(d, [(0, half_h), (cx, half_h * 2), (cx, half_h * 2 + WALL_ROWS),
              (0, half_h + WALL_ROWS)], left["metal"])
    cpoly(d, [(cx, half_h * 2), (w_cells, half_h), (w_cells, half_h + WALL_ROWS),
              (cx, half_h * 2 + WALL_ROWS)], right["metal"])
    cpoly(d, [(cx, 0), (w_cells * 0.42, half_h * 0.42), (cx, half_h * 0.9),
              (w_cells * 0.58, half_h * 0.42)], top["metal_light"])
    if face_feature:
        face_feature(d, w_cells, h_cells, rng or random.Random(3))
    return img, h_cells


def face_brick(d, w, h, rng):
    for row in range(WALL_ROWS):
        y = TILE_H / 2.0 + 0.5 + row
        cline(d, 0, y, w, y, g("brick")["metal_dark"], 1.0)
    for k in range(WALL_ROWS * 2):
        x = w * (0.08 + 0.42 * (k % 3))
        y0 = TILE_H / 2.0 + 0.5 + (k // 3)
        cline(d, x, y0, x, y0 + 1.0, g("brick")["metal_dark"], 0.8)


def face_plank(d, w, h, rng):
    for k in range(1, WALL_ROWS):
        cline(d, 0, TILE_H / 2.0 + k, w, TILE_H / 2.0 + k, g("wood")["metal_dark"], 0.9)


def face_rock(d, w, h, rng):
    for k in range(5):
        x = w * (0.1 + 0.18 * k)
        cline(d, x, TILE_H / 2.0, x + 0.6, TILE_H / 2.0 + WALL_ROWS * 0.8,
              g("rock")["metal_dark"], 0.9)


BLOCKS = [
    ("bloco.rock", "Rocha", "rock", g("rock"), g("rock"), g("rock"), None),
    ("bloco.cliff", "Barranco", "dirt", g("grass"), g("dirt"), g("dirt"), None),
    ("bloco.cave", "Parede de caverna", "rock", g("rock"), g("rock"), g("rock"), face_rock),
    ("bloco.brick", "Parede de tijolo", "brick", g("brick"), g("brick"), g("brick"), face_brick),
    ("bloco.wall_wood", "Parede de madeira", "wood", g("wood"), g("wood"), g("wood"), face_plank),
    ("bloco.plaster", "Parede de reboco", "plaster", g("plaster"), g("plaster"),
     g("plaster"), None),
]


# --- props: a foot on a tile, like a tree ---------------------------------------
def p_boulder(d, w, h):
    cx, base = w / 2.0, h - 0.8
    cellipse(d, cx, base - h * 0.34, w * 0.44, h * 0.30, g("rock")["metal"])
    cellipse(d, cx - w * 0.12, base - h * 0.40, w * 0.26, h * 0.18, g("rock")["metal_light"])
    cellipse(d, cx + w * 0.16, base - h * 0.26, w * 0.22, h * 0.14, g("rock")["metal_dark"])
    crect(d, cx - w * 0.20, base - 0.5, cx + w * 0.20, base + 0.4, g("rock")["metal_dark"])


def p_rocks(d, w, h):
    base = h - 0.8
    for (dx, r) in ((-w * 0.24, w * 0.20), (w * 0.16, w * 0.15), (w * 0.02, w * 0.10)):
        circle(d, w / 2.0 + dx, base - r * 0.75, r, g("rock")["metal"])
        circle(d, w / 2.0 + dx - r * 0.2, base - r * 0.9, r * 0.5, g("rock")["metal_light"])
    crect(d, w / 2.0 - w * 0.36, base - 0.4, w / 2.0 + w * 0.32, base + 0.4,
          g("rock")["metal_dark"])


def p_stump(d, w, h):
    cx, base = w / 2.0, h - 0.8
    crect(d, cx - w * 0.24, h * 0.34, cx + w * 0.24, base, g("wood")["metal"])
    crect(d, cx - w * 0.24, h * 0.34, cx - w * 0.06, base, g("wood")["metal_light"])
    crect(d, cx + w * 0.12, h * 0.34, cx + w * 0.24, base, g("wood")["metal_dark"])
    circle(d, cx, h * 0.34, w * 0.24, g("wood")["metal_light"])
    circle(d, cx, h * 0.34, w * 0.14, g("wood")["metal"])
    circle(d, cx, h * 0.34, w * 0.06, g("wood")["metal_dark"])


def p_log(d, w, h):
    cy = h * 0.62
    crect(d, w * 0.08, cy - h * 0.13, w * 0.92, cy + h * 0.13, g("wood")["metal"])
    crect(d, w * 0.08, cy - h * 0.13, w * 0.92, cy - h * 0.05, g("wood")["metal_light"])
    crect(d, w * 0.08, cy + h * 0.05, w * 0.92, cy + h * 0.13, g("wood")["metal_dark"])
    circle(d, w * 0.90, cy, h * 0.13, g("wood")["metal_light"])
    circle(d, w * 0.90, cy, h * 0.06, g("wood")["metal_dark"])


def p_mushroom(d, w, h):
    base = h - 0.7
    for (dx, dh, c) in ((-w * 0.18, 0.0, g("cloth")), (w * 0.16, h * 0.16, g("flame"))):
        stem_x = w / 2.0 + dx
        crect(d, stem_x - w * 0.12, base - h * 0.30 - dh, stem_x + w * 0.12, base,
              g("plaster")["metal"])
        cellipse(d, stem_x, base - h * 0.30 - dh, w * 0.26, h * 0.10, c["metal"])
        cellipse(d, stem_x - w * 0.07, base - h * 0.32 - dh, w * 0.11, h * 0.05,
                 c["metal_light"])


def p_flowers(d, w, h):
    base = h - 0.7
    rng = random.Random(11)
    for k in range(5):
        x = w * (0.14 + 0.18 * k)
        cline(d, x, base, x + rng.choice((-0.2, 0.2)), base - h * 0.34,
              g("grass")["metal_dark"], 0.5)
        c = (g("cloth") if k % 2 else g("flame"))
        circle(d, x + rng.choice((-0.2, 0.2)), base - h * 0.36, w * 0.07, c["metal_light"])
    crect(d, w * 0.06, base - 0.3, w * 0.94, base + 0.4, g("grass")["metal_dark"])


def p_reeds(d, w, h):
    base = h - 0.7
    for k in range(4):
        x = w * (0.20 + 0.2 * k)
        top = base - h * (0.50 + 0.10 * (k % 2))
        cline(d, x, base, x + (0.3 if k % 2 else -0.3), top, g("grass")["metal"], 0.6)
        circle(d, x + (0.3 if k % 2 else -0.3), top - h * 0.05, w * 0.055,
               g("dirt")["metal_dark"])
    crect(d, w * 0.08, base - 0.3, w * 0.92, base + 0.4, g("grass")["metal_dark"])


def p_lily(d, w, h):
    cy = h * 0.66
    circle(d, w / 2.0, cy, w * 0.40, g("grass")["metal"])
    circle(d, w / 2.0, cy, w * 0.34, g("grass")["metal_light"])
    cellipse(d, w * 0.5, cy - w * 0.05, w * 0.06, w * 0.16, (0, 0, 0))
    circle(d, w * 0.34, cy - w * 0.10, w * 0.08, g("flame")["metal_light"])
    circle(d, w * 0.34, cy - w * 0.10, w * 0.04, g("plaster")["metal"])


def p_deadbush(d, w, h):
    base = h - 0.7
    cline(d, w / 2.0, base, w / 2.0, h * 0.16, g("wood")["metal_dark"], 0.7)
    for k in range(4):
        y = h * (0.30 + 0.12 * k)
        side = -1 if k % 2 else 1
        cline(d, w / 2.0, y, w / 2.0 + side * w * 0.30, y - h * 0.10,
              g("wood")["metal_dark"], 0.5)
    crect(d, w * 0.26, base - 0.3, w * 0.74, base + 0.4, g("dirt")["metal_dark"])


def p_torch(d, w, h):
    cx = w / 2.0
    crect(d, cx - w * 0.06, h * 0.30, cx + w * 0.06, h - 0.8, g("wood")["metal"])
    crect(d, cx - w * 0.06, h * 0.30, cx - w * 0.02, h - 0.8, g("wood")["metal_light"])
    cellipse(d, cx, h * 0.30, w * 0.16, h * 0.06, g("iron")["metal_dark"])
    cpoly(d, [(cx, h * 0.02), (cx + w * 0.11, h * 0.17), (cx + w * 0.07, h * 0.27),
              (cx - w * 0.07, h * 0.27), (cx - w * 0.11, h * 0.17)], g("flame")["metal"])
    cpoly(d, [(cx, h * 0.08), (cx + w * 0.05, h * 0.19), (cx, h * 0.24),
              (cx - w * 0.05, h * 0.19)], g("flame")["metal_light"])
    crect(d, cx - w * 0.20, h - 0.8, cx + w * 0.20, h - 0.1, g("sand")["metal_dark"])


def p_brazier(d, w, h):
    cx, base = w / 2.0, h - 0.8
    for side in (-1, 1):
        cline(d, cx + side * w * 0.22, base, cx + side * w * 0.10, h * 0.42,
              g("iron")["metal_dark"], 0.7)
    cpoly(d, [(cx - w * 0.30, h * 0.34), (cx + w * 0.30, h * 0.34),
              (cx + w * 0.20, h * 0.50), (cx - w * 0.20, h * 0.50)], g("iron")["metal"])
    cellipse(d, cx, h * 0.34, w * 0.30, h * 0.06, g("iron")["metal_light"])
    cpoly(d, [(cx, h * 0.04), (cx + w * 0.16, h * 0.20), (cx + w * 0.10, h * 0.32),
              (cx - w * 0.10, h * 0.32), (cx - w * 0.16, h * 0.20)], g("flame")["metal"])
    cpoly(d, [(cx, h * 0.12), (cx + w * 0.07, h * 0.23), (cx, h * 0.29),
              (cx - w * 0.07, h * 0.23)], g("flame")["metal_light"])
    crect(d, cx - w * 0.34, base - 0.3, cx + w * 0.34, base + 0.4, g("rock")["metal_dark"])


def p_barrel(d, w, h):
    cx, base = w / 2.0, h - 0.6
    crect(d, cx - w * 0.28, h * 0.16, cx + w * 0.28, base, g("wood")["metal"])
    crect(d, cx - w * 0.28, h * 0.16, cx - w * 0.10, base, g("wood")["metal_light"])
    crect(d, cx + w * 0.16, h * 0.16, cx + w * 0.28, base, g("wood")["metal_dark"])
    for y in (h * 0.26, h * 0.62):
        crect(d, cx - w * 0.30, y, cx + w * 0.30, y + 0.7, g("iron")["metal_dark"])
    cellipse(d, cx, h * 0.16, w * 0.28, h * 0.05, g("wood")["metal_light"])


def p_crate(d, w, h):
    cx, base = w / 2.0, h - 0.6
    top = h * 0.22
    crect(d, cx - w * 0.30, top, cx + w * 0.30, base, g("wood")["metal"])
    crect(d, cx - w * 0.30, top, cx - w * 0.18, base, g("wood")["metal_light"])
    crect(d, cx + w * 0.20, top, cx + w * 0.30, base, g("wood")["metal_dark"])
    crect(d, cx - w * 0.30, top, cx + w * 0.30, top + 0.8, g("wood")["metal_dark"])
    cline(d, cx - w * 0.30, top + 0.8, cx + w * 0.30, base - 0.8, g("wood")["metal_dark"], 0.8)
    cline(d, cx + w * 0.30, top + 0.8, cx - w * 0.30, base - 0.8, g("wood")["metal_dark"], 0.8)


def p_column(d, w, h):
    cx, base = w / 2.0, h - 0.6
    crect(d, cx - w * 0.34, base - 1.0, cx + w * 0.34, base, g("stone")["metal_dark"])
    crect(d, cx - w * 0.26, h * 0.20, cx + w * 0.26, base - 1.0, g("stone")["metal"])
    for k in range(3):
        x = cx - w * 0.20 + k * w * 0.20
        cline(d, x, h * 0.20, x, base - 1.0, g("stone")["metal_dark"], 0.7)
    crect(d, cx - w * 0.30, h * 0.12, cx + w * 0.30, h * 0.20, g("stone")["metal_light"])
    crect(d, cx - w * 0.26, h * 0.12, cx + w * 0.26, h * 0.16, g("stone")["metal_dark"])


def p_ladder(d, w, h):
    base = h - 0.5
    for side in (-1, 1):
        crect(d, w / 2.0 + side * w * 0.22, h * 0.06, w / 2.0 + side * w * 0.30, base,
              g("wood")["metal"])
    for k in range(4):
        y = h * (0.20 + 0.19 * k)
        crect(d, w * 0.22, y, w * 0.78, y + 0.8, g("wood")["metal_light"])


PROPS = [
    ("prop.boulder", "Pedregulho", "boulder", (10, 8), p_boulder, 4.0, "rock", "rock"),
    ("prop.rocks", "Pedras", "rocks", (10, 6), p_rocks, 3.4, "rock", "rock"),
    ("prop.stump", "Toco", "stump", (9, 8), p_stump, 3.2, "wood", "wood"),
    ("prop.log", "Tronco caído", "log", (12, 6), p_log, 1.6, "wood", "wood"),
    ("prop.mushroom", "Cogumelos", "mushroom", (9, 7), p_mushroom, 3.0, "cloth", "dirt"),
    ("prop.flowers", "Flores", "flowers", (9, 5), p_flowers, 3.2, "flame", "grass"),
    ("prop.reeds", "Juncos", "reeds", (9, 9), p_reeds, 3.0, "grass", "grass"),
    ("prop.lily", "Vitória-régia", "lily", (10, 6), p_lily, 3.6, "grass", "water"),
    ("prop.deadbush", "Toco seco", "deadbush", (9, 8), p_deadbush, 3.2, "wood", "dirt"),
    ("prop.torch", "Tocha", "torch", (7, 12), p_torch, 2.4, "flame", "sand"),
    ("prop.brazier", "Braseiro", "brazier", (9, 10), p_brazier, 3.2, "flame", "rock"),
    ("prop.barrel", "Barril", "barrel", (8, 9), p_barrel, 3.4, "wood", "wood"),
    ("prop.crate", "Caixote", "crate", (8, 8), p_crate, 3.4, "wood", "wood"),
    ("prop.column", "Coluna", "column", (9, 14), p_column, 3.6, "stone", "stone"),
    ("prop.ladder", "Escada de mão", "ladder", (8, 13), p_ladder, 3.0, "wood", "wood"),
]


# --- decals: drawn with the floor, never occluding --------------------------------
def d_patch(w_cells, h_cells, base, speck, colour, density, size=(0.5, 0.30)):
    """A patch on the floor: wrapped so it continues across the tile's edge too, or a
    path of these would show its own repeat."""
    img = Image.new("RGB", (int(round(w_cells * UX)), int(round(h_cells * UY))), (0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = random.Random(23)

    def blob(dd, x, y, r):
        cellipse(dd, x, y, size[0] * r.uniform(0.7, 1.3), size[1] * r.uniform(0.7, 1.3),
                 colour["metal"])
    wrapped(d, w_cells, h_cells, blob, int(density), rng)

    def fleck(dd, x, y, r):
        circle(dd, x, y, r.uniform(0.1, 0.2), colour["metal_light"])
    wrapped(d, w_cells, h_cells, fleck, int(density * 0.8), rng)
    return Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)),
                           diamond_mask(w_cells, h_cells))


DECALS = [
    ("mancha.grass", "Moita de capim", "grass", (10, 4), "grass"),
    ("mancha.moss", "Musgo", "moss", (10, 4), "moss"),
    ("mancha.dirt_path", "Trilha de terra", "dirt", (10, 4), "dirt"),
    ("mancha.snow", "Mancha de neve", "snow", (10, 4), "snow"),
    ("mancha.puddle", "Poça", "water", (10, 4), "water"),
]


# --- building the set -------------------------------------------------------------
def disc_index():
    """The bank refuses two pieces with the same art, and a contact shadow IS a disc of a
    given radius -- so the scenery props REFERENCE the tree set's shared discs instead of
    emitting their own identical copies."""
    if not os.path.exists(TREES_JSON):
        return []
    with open(TREES_JSON, encoding="utf-8") as fh:
        payload = json.load(fh)
    out = []
    for p in payload["pieces"]:
        if p.get("kind") == "decal" and p.get("disc"):
            out.append((p["disc"]["rx"], p["id"]))
    return sorted(out)


def pick_disc(discs, want):
    best = None
    for (rx, pid) in discs:
        d = abs(rx - want)
        if best is None or d < best[0]:
            best = (d, pid)
    if best and best[0] <= 1.0:
        return best[1]
    return None


def build_set(seed):
    pieces = []
    discs = disc_index()
    missing_shadows = []

    def add(piece_id, label, kind, slot, rows, w, h, anchor, levels, extra=None):
        inked = sum(1 for r in rows for ch in r["g"] if ch != " ")
        piece = {
            "id": piece_id, "kind": kind, "slot": slot, "label": label,
            "species": piece_id.split(".")[1], "family": ".".join(piece_id.split(".")[:2]),
            "w": w, "h": h, "anchor": anchor, "frames": 1, "directions": 1,
            "levels": levels, "cells": rows,
            "stats": {"inkedCells": inked, "cellCount": w * h,
                      "colors": len({c for r in rows for c in r["c"] if c})},
        }
        if extra:
            piece.update(extra)
        pieces.append(piece)

    for entry in TILES:
        (pid, label, species, base, speck, feat) = entry
        img = tile(TILE_W, TILE_H, base, speck, feat)
        built = to_ground(img, TILE_W, TILE_H)
        add(pid, label, "tile", "piso", quiet(built["rows"]), TILE_W, TILE_H,
            {"x": TILE_W // 2, "y": TILE_H // 2}, built["levels"],
            {"tile": [TILE_W, TILE_H], "aspect": 2.0, "iso": {"flat": af.ISO_FLAT}})

    for entry in BLOCKS:
        (pid, label, species, top, left, right, feat) = entry
        img, h_cells = iso_block(TILE_W, top, left, right, feat)
        built = to_ground(img, TILE_W, h_cells)
        add(pid, label, "block", "bloco", built["rows"], TILE_W, h_cells,
            {"x": TILE_W // 2, "y": h_cells - 1}, built["levels"],
            {"tile": [TILE_W, TILE_H], "wall": WALL_ROWS, "aspect": 2.0})
    for entry in PROPS:
        (pid, label, species, (w_cells, h_cells), routine, shadow_r, material, foot) = entry
        img = Image.new("RGB", (int(round(w_cells * UX)), int(round(h_cells * UY))), (0, 0, 0))
        d = ImageDraw.Draw(img)
        routine(d, w_cells, h_cells)
        # The contact patch is drawn HERE, not left to each routine: a prop has to touch
        # the tile it stands on, and a stroke thinner than a cell does not survive the
        # sampling -- the first pass had five props floating above their own shadow.
        # Its tone is the material's MID tone, not its dark one: measured on the first
        # pass, a dark patch on a bright piece (mushrooms, flowers, reeds) fell below the
        # ink level of the piece's own tones and the bottom row came out blank.
        crect(d, w_cells * 0.34, h_cells - 0.75, w_cells * 0.66, h_cells - 0.05,
              GROUND[foot]["metal"])
        built = to_ground(img, w_cells, h_cells)
        shadow = pick_disc(discs, shadow_r)
        if shadow is None:
            missing_shadows.append(pid)
        add(pid, label, "prop", "prop", built["rows"], w_cells, h_cells,
            {"x": w_cells // 2, "y": h_cells - 1}, built["levels"],
            {"shadow": shadow, "material": material})

    for entry in DECALS:
        (pid, label, species, (w_cells, h_cells), material) = entry
        colour = g(material)
        img = d_patch(w_cells, h_cells, colour, colour, colour, w_cells * h_cells * 0.8)
        built = to_ground(img, w_cells, h_cells)
        add(pid, label, "decal", "mancha", quiet(built["rows"], 0.62), w_cells, h_cells,
            {"x": w_cells // 2, "y": h_cells // 2}, built["levels"],
            {"layer": "ground", "material": material, "tile": [TILE_W, TILE_H]})

    return pieces, missing_shadows


def write_json(pieces, seed, missing_shadows):
    payload = {
        "version": 1,
        "generator": "scenery %s (artforge %s)" % (VERSION, af.VERSION),
        "set": "scenery",
        "label": "Cenário: piso, bloco, prop e mancha",
        "kinds": ["tile", "block", "prop", "decal"],
        "seed": seed,
        "cell": {"w": af.CELL_W, "h": af.CELL_H, "aspect": round(af.CELL_ASPECT, 4)},
        "tile": {"w": TILE_W, "h": TILE_H, "px": [round(TILE_W * af.CELL_W, 1),
                                                  round(TILE_H * af.CELL_H, 1)]},
        "wallRows": WALL_ROWS,
        "floorTone": "#3a352c",
        "shadowInk": "#1a1814",
        "ramp": RAMP,
        "glyphGamma": af.GLYPH_GAMMA,
        "quant": af.QUANT,
        "missingShadows": missing_shadows,
        "pieces": pieces,
    }
    os.makedirs(ASSETS, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    return payload


# --- measuring the repeat ---------------------------------------------------------
def tile_grid(piece, n=3):
    """The tile repeated n x n at its own iso offsets, as raw rows plus a per-cell
    (glyph, colour) grid -- what the measuring needs, and what the page draws."""
    tw, th = piece["tile"]
    span = n - 1
    width = 2 * span * (tw // 2) + tw
    height = span * th + th
    canvas = [[" "] * width for _ in range(height)]
    colors = [[""] * width for _ in range(height)]
    off = span * (tw // 2)
    for j in range(n):
        for i in range(n):
            (x, y) = iso_xy(i, j, tw, th)
            blit(canvas, colors, piece, off + x + tw // 2, y + th // 2)
    meta = [[(canvas[y][x], colors[y][x]) if canvas[y][x] != " " else None
             for x in range(width)] for y in range(height)]
    return canvas, colors, meta


def preview_seam(piece, n=4):
    """Does the floor continue?

    With an iso stagger the neighbour of a tile sits HALF a tile over, so a tile is
    seamless only if its field repeats with half a tile. If it does, shifting the composed
    floor by one tile step leaves the same picture; a feature drawn without wrapping shows
    up as cells that change.

    Measured on the composition, because one tile cannot show this at all. The first
    version measured the tile's own two edges -- which an iso tile never touches, which is
    why it read 0.0 for every floor, including ones that did not emend.
    """
    (rows, colors, meta) = tile_grid(piece, n)
    tw, th = piece["tile"]
    sx, sy = tw // 2, th // 2
    height, width = len(rows), len(rows[0])
    mx, my = tw, th                      # one tile of margin: the composed picture's own
    same = diff = 0                      # edge cells are covered by clipped tiles, which
    for y in range(my, height - sy - my):  # is an artefact of the CANVAS, not of the tile
        for x in range(mx, width - sx - mx):
            a, b = meta[y][x], meta[y + sy][x + sx]
            if a is None or b is None:
                continue
            if a == b:
                same += 1
            else:
                diff += 1
    total = same + diff
    return {"same": same, "total": total,
            "ratio": (diff / float(total)) if total else 1.0}


# --- composing a scene ------------------------------------------------------------
def blit(canvas, colors, piece, x, y):
    """Place a piece so its ANCHOR lands on (x, y) -- the same rule the engine uses, and
    the only reason a prop sits on a tile instead of near it."""
    for ry, row in enumerate(piece["cells"]):
        for rx in range(piece["w"]):
            if row["g"][rx] == " ":
                continue
            wx = x - piece["anchor"]["x"] + rx
            wy = y - piece["anchor"]["y"] + ry
            if 0 <= wx < len(canvas[0]) and 0 <= wy < len(canvas):
                canvas[wy][wx] = row["g"][rx]
                colors[wy][wx] = row["c"][rx]


def iso_xy(i, j, tw, th):
    """The tile (i, j)'s top-left cell: half a tile across and half a tile down per step,
    which is what makes the rhombi interlock instead of stacking."""
    return (i - j) * (tw // 2), (i + j) * (th // 2)


def scene_cells(by_id, size=(11, 7), floor="piso.grass", path="piso.dirt"):
    """An environment, composed, as raw cells: a floor of tiles, a path over it, decals,
    props standing on their tiles with their contact shadows, and walls on the two back
    edges.

    Returns (canvas, colors, placed), where `placed` is what was planted and where -- so a
    check can verify the COMPOSITION (the anchor really holds its cell) instead of hunting
    for a substring that a later piece may legitimately have overdrawn.

    The canvas is sized to the DIAMOND the lattice actually fills, plus headroom: a prop
    is taller than the tile it stands on, so it rises above the floor and the top of the
    picture is where the tallest thing is.
    """
    tw, th = TILE_W, TILE_H
    cols, rows = size
    span = cols + rows - 2
    head = 13
    width = span * (tw // 2) + tw
    height = head + span * (th // 2) + th + 4
    canvas = [[" "] * width for _ in range(height)]
    colors = [[""] * width for _ in range(height)]
    ox, oy = (rows - 1) * (tw // 2), head
    placed = []

    def put(piece_id, i, j, dy=0):
        piece = by_id.get(piece_id)
        if not piece:
            return None
        (x, y) = iso_xy(i, j, tw, th)
        at = (ox + x + tw // 2, oy + y + th // 2 + dy)
        blit(canvas, colors, piece, at[0], at[1])
        placed.append((piece_id, at[0], at[1]))
        return piece

    path_tiles = {(2, 1), (2, 2), (3, 2), (3, 3), (4, 3), (4, 4), (5, 4)}
    # The floor is drawn over a lattice range WIDER than the grid: the (i, j) grid is a
    # rectangle in lattice space, and the rhombi of a rectangle do not fill the rectangle
    # of the canvas -- the corners are covered by tiles that are outside the grid's own
    # indices. (This is also why the canvas is sized to the diamond, not to a rectangle.)
    for j in range(-3, rows + 4):
        for i in range(-3, cols + 4):
            inside = 0 <= i < cols and 0 <= j < rows
            pid = path if inside and (i, j) in path_tiles else floor
            put(pid, i, j)
    # decals go with the floor, before anything stands on it (the engine's draw order)
    for (pid, i, j) in (("mancha.grass", 0, 0), ("mancha.moss", 5, 1),
                        ("mancha.puddle", 4, 5)):
        put(pid, i, j)
    # walls along the two back edges: a block anchors at the tile's FRONT corner
    for i in range(cols - 1):
        put("bloco.rock", i, rows - 1, dy=th // 2)
    for j in range(rows):
        put("bloco.cave", cols - 1, j, dy=th // 2)
    # props on their tiles, with the shadow composed underneath. Spaced so no prop's
    # ANCHOR falls inside a later prop's box: stacking them is allowed in a real scene
    # (the engine draws in order), but then the demo cannot show that the anchor holds.
    for (pid, i, j) in (("prop.torch", 1, 4), ("prop.torch", 6, 1), ("prop.barrel", 6, 2),
                        ("prop.crate", 9, 4), ("prop.boulder", 0, 2), ("prop.reeds", 3, 0),
                        ("prop.flowers", 1, 1), ("prop.column", 5, 5), ("prop.stump", 9, 0)):
        piece = by_id.get(pid)
        if not piece:
            continue
        (x, y) = iso_xy(i, j, tw, th)
        at = (ox + x + tw // 2, oy + y + th // 2)
        shadow = by_id.get(piece.get("shadow") or "")
        if shadow:
            blit(canvas, colors, shadow, at[0], at[1])
        blit(canvas, colors, piece, at[0], at[1] + 1)
        placed.append((pid, at[0], at[1] + 1))
    return canvas, colors, placed


def compose_scene(by_id, **kw):
    """The composed environment as run-length markup, plus what was planted where."""
    (canvas, colors, placed) = scene_cells(by_id, **kw)
    rows_out = [{"g": "".join(r), "c": colors[k]} for k, r in enumerate(canvas)]
    html, _inked = af.run_length_html(rows_out)
    return html, placed


def tile_preview(piece, n=3):
    """The tile repeated n x n at its own offsets: if the pattern does not continue, this
    is where it shows, and it is the only honest way to look at a floor."""
    (canvas, colors, _meta) = tile_grid(piece, n)
    rows_out = [{"g": "".join(r), "c": colors[k]} for k, r in enumerate(canvas)]
    return af.run_length_html(rows_out)


# --- the page ---------------------------------------------------------------------
PAGE_HEAD = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>artforge — cenário</title>
<style>
  :root { --panelw: min(1240px, calc(100vw - 40px)); --fs: __FS__px;
    --bg: #05070a; --panel: #0b0f14; --line: #1c2430;
    --ink: #e9e5d8; --dim: #8b8f92; --accent: #cfa855;
    --mono: "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 30px 20px 52px; color: var(--ink); font-family: var(--mono);
         line-height: 1.5; background: radial-gradient(120% 70% at 50% 0%, #111a26 0%, var(--bg) 58%, #030405 100%); }
  .wrap { width: var(--panelw); margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 6px; }
  h2 { font-size: 13px; margin: 26px 0 10px; color: var(--accent); font-weight: 600; }
  .lede { color: var(--dim); font-size: 12.5px; margin: 0 0 18px; max-width: 98ch; }
  .lede b { color: var(--accent); font-weight: 600; }
  .card { border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
          margin-bottom: 16px; overflow: hidden; }
  .cap { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline;
         padding: 9px 14px; border-bottom: 1px solid var(--line); font-size: 11.5px; color: var(--dim); }
  .cap b { color: var(--accent); font-weight: 600; }
  .arts { display: flex; flex-wrap: wrap; gap: 20px; padding: 12px 14px 14px; align-items: flex-start; }
  .pane .name { color: var(--dim); font-size: 10.5px; margin-bottom: 5px; }
  pre { margin: 0; font-family: var(--mono); font-size: var(--fs); line-height: 1;
        white-space: pre; font-variant-ligatures: none; -webkit-font-smoothing: antialiased; }
  pre i { font-style: normal; }
  .gridbox { padding: 14px; overflow-x: auto; }
  .stage { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #0b0d10; }
  table { border-collapse: collapse; font-size: 11.5px; margin-top: 8px; }
  th, td { border: 1px solid var(--line); padding: 3px 9px; text-align: right; color: var(--dim); }
  th { color: var(--ink); font-weight: 600; }
  td.id { text-align: left; color: var(--ink); }
  footer { color: var(--dim); font-size: 11.5px; border-top: 1px solid var(--line); padding-top: 12px; margin-top: 18px; }
  code { color: var(--accent); }
</style></head><body><div class="wrap">
<h1>artforge — cenário</h1>
<p class="lede">__LEDE__</p>
<h2>Um ambiente, composto</h2>
<p class="lede">__SCENENOTE__</p>
<div class="card"><div class="gridbox"><div class="stage"><pre>__SCENE__</pre></div></div></div>
<h2>O piso emenda consigo mesmo</h2>
<p class="lede">__SEAMNOTE__</p>
__TILES__
__SHEETS__
<footer>__FOOTER__</footer>
</div></body></html>
"""


def build_html(payload, pieces):
    by_id = {p["id"]: p for p in pieces}
    scene, _placed = compose_scene(by_id)
    tiles = [p for p in pieces if p["slot"] == "piso"]
    sheets = []
    for (slot, label) in (("bloco", "blocos"), ("prop", "props"), ("mancha", "manchas")):
        group = [p for p in pieces if p["slot"] == slot]
        if not group:
            continue
        colw = max(p["w"] for p in group) + 4
        rowh = max(p["h"] for p in group)
        width, height = colw * len(group), rowh + 3
        canvas = [[" "] * width for _ in range(height)]
        colors = [[""] * width for _ in range(height)]
        for k, piece in enumerate(group):
            ox = k * colw + (colw - piece["w"]) // 2
            oy = (rowh - piece["h"]) // 2
            for ry, row in enumerate(piece["cells"]):
                for rx in range(piece["w"]):
                    if row["g"][rx] == " ":
                        continue
                    canvas[oy + ry][ox + rx] = row["g"][rx]
                    colors[oy + ry][ox + rx] = row["c"][rx]
        for k, piece in enumerate(group):
            text = piece["label"][:colw - 2]
            start = k * colw + max(0, (colw - len(text)) // 2)
            for m, ch in enumerate(text):
                canvas[rowh + 1][start + m] = ch
                colors[rowh + 1][start + m] = "#8b8f92"
        rows_out = [{"g": "".join(r), "c": colors[k]} for k, r in enumerate(canvas)]
        body, _i = af.run_length_html(rows_out)
        sheets.append('<section class="card"><div class="cap"><b>%s</b>'
                      '<span>%d peças</span><span>%s</span></div>'
                      '<div class="gridbox"><pre>%s</pre></div></section>'
                      % (label, len(group), ", ".join(p["id"] for p in group), body))

    tile_cards, table = [], ['<div class="gridbox"><table>'
                             '<tr><th>piso</th><th>células que mudam ao deslocar</th>'
                             '<th>de</th><th>emenda</th></tr>']
    for piece in tiles:
        s = preview_seam(piece)
        body, _i = tile_preview(piece)
        ok = s["ratio"] == 0.0
        tile_cards.append('<section class="card"><div class="cap"><b>%s</b><span>%s</span>'
                          '<span>%dx%d células → %.0f×%.0f px</span>'
                          '<span>%s</span></div>'
                          '<div class="gridbox"><div class="stage"><pre>%s</pre></div></div>'
                          '</section>'
                          % (piece["label"], piece["id"], piece["w"], piece["h"],
                             piece["w"] * af.CELL_W, piece["h"] * af.CELL_H,
                             "contínuo" if ok else "MOSTRA A EMENDA", body))
        table.append('<tr><td class="id">%s</td><td>%d</td><td>%d</td><td>%s</td></tr>'
                     % (piece["id"], round(s["ratio"] * s["total"]), s["total"],
                        "contínuo" if ok else "quebra"))
    table.append("</table></div>")

    fs = 12.0
    lede = ("<b>%d peças</b> de cenário em <b>quatro slots</b> — %d pisos, %d blocos, "
            "%d props e %d manchas — para compor ambiente externo ou interno. O piso é "
            "<b>%d × %d células</b> (%.0f × %.0f px, 2:1 na tela), o bloco tem %d linhas de "
            "parede, o prop pisa no tile com <b>mancha de contato</b> e a mancha é desenhada "
            "junto com o piso e nunca oclui."
            % (len(pieces), len(tiles), sum(1 for p in pieces if p["slot"] == "bloco"),
               sum(1 for p in pieces if p["slot"] == "prop"),
               sum(1 for p in pieces if p["slot"] == "mancha"), TILE_W, TILE_H,
               TILE_W * af.CELL_W, TILE_H * af.CELL_H, WALL_ROWS))
    scene_note = ("Pisos emendados no losango iso, uma trilha de terra por cima, manchas, "
                  "muros nas duas bordas de trás e props plantados nas suas tiles com a "
                  "sombra composta embaixo — na MESMA ordem de desenho do motor: "
                  "<b>piso → mancha → sombra → prop</b>. Nada aqui foi posicionado à mão.")
    seam_note = ("Cada piso repetido 3×3 nos seus próprios deslocamentos (meia tile de "
                 "largura, meia de altura por passo), que é onde a repetição aparece se "
                 "não emendar. A medida: com o escalonamento iso o vizinho está <b>meia "
                 "tile</b> adiante, então a tile só é contínua se o campo repetir com "
                 "meia tile — se repetir, <b>deslocar o piso composto deixa a mesma "
                 "figura</b>, e uma textura desenhada sem dar a volta aparece como "
                 "células que mudam.")
    footer = ("Gerado por <code>scenery.py</code> · conjunto em <code>assets/scenery.json</code> · "
              "peças em <code>bank.py ingest assets/scenery.json</code>")
    html = PAGE_HEAD
    for (marker, value) in (("__FS__", ("%.2f" % fs).rstrip("0").rstrip(".")),
                            ("__LEDE__", lede), ("__SCENENOTE__", scene_note),
                            ("__SCENE__", scene), ("__SEAMNOTE__", seam_note),
                            ("__TILES__", "\n".join(tile_cards)),
                            ("__SHEETS__", "\n".join(sheets) + "\n" + "\n".join(table)),
                            ("__FOOTER__", footer)):
        html = html.replace(marker, value)
    for marker in ("__FS__", "__LEDE__", "__SCENENOTE__", "__SCENE__", "__SEAMNOTE__",
                   "__TILES__", "__SHEETS__", "__FOOTER__"):
        if marker in html:
            raise SystemExit("marker survived the build: %s" % marker)
    if "<script" in html:
        raise SystemExit("this page is static: no script needed")
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    return fs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    pieces, missing = build_set(args.seed)
    payload = write_json(pieces, args.seed, missing)
    build_html(payload, pieces)
    print("scenery %s -- %d pieces, seed %d" % (VERSION, len(pieces), args.seed))
    print("  json : %s (%.0f KB)" % (os.path.relpath(OUT_JSON, HERE),
                                     os.path.getsize(OUT_JSON) / 1024.0))
    print("  html : %s (%.0f KB)" % (os.path.relpath(OUT_HTML, HERE),
                                     os.path.getsize(OUT_HTML) / 1024.0))
    if missing:
        print("  sem mancha emprestada: %s" % ", ".join(missing))
    print()
    print("  %-22s %-7s %-6s %-8s %s" % ("id", "slot", "caixa", "tinta", "emenda"))
    for p in pieces:
        s = preview_seam(p) if p["slot"] == "piso" else None
        print("  %-22s %-7s %2dx%-3d %5.0f%%  %s"
              % (p["id"], p["slot"], p["w"], p["h"],
                 100.0 * p["stats"]["inkedCells"] / p["stats"]["cellCount"],
                 ("%d de %d células mudam ao deslocar" % (round(s["ratio"] * s["total"]),
                                                          s["total"])) if s else "-"))


if __name__ == "__main__":
    main()
