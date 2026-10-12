#!/usr/bin/env python3
"""weapons -- inventory icons: weapons and armour, at three character resolutions.

Different problem from a tree. A tree is a PROP: it stands on a tile, its anchor is
the foot, and its shadow goes with the floor. An ITEM is an ICON: it is centred in
an inventory slot, it has no contact with any ground, and what has to survive is the
SILHOUETTE -- at 5 cells wide a sword reads by its outline or it does not read.

## The resolution question

"Make it smaller" in text art is not one problem, it is two:

  * SAMPLING the same drawing onto a smaller grid. Free, and it is what a runtime
    shrink does. It loses the signature first: a 1-cell crossguard averaged into the
    blade stops being a crossguard.
  * AUTHORING the smaller size. Here the box is a parameter and so is what gets
    drawn: at the small size the guard is a plain bar and there is no fuller, no gem
    and no grip wrapping; at the large size those exist because there are cells for
    them.

This set does the second, and ships the first as the bridge (`shrink`, mirrored in
the page in JavaScript), so a slot that matches no authored size still gets served.
Which of the two is better at the same grid size is not an opinion: the audit
measures both against each other.

Sizes are a 2x chain at the ends -- large = 2 x small in both axes -- so the shrink of
the large lands EXACTLY on the small grid and the comparison is like for like.

The small box is not arbitrary either: it is the item's INVENTORY FOOTPRINT. A slot
is a square block of 5x3 cells (33 x 33 px), the footprint says how many slots the
item takes (a sword 1x3, a breastplate 2x3), and the small icon is drawn to fill it.
That is how the resolution ends up answering to the game instead of to taste.

Usage:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 weapons.py [--seed N]
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/items_audit.py
    open weapons.html
"""

import argparse
import json
import math
import os
import random

from PIL import Image, ImageDraw

import artforge as af

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_JSON = os.path.join(ASSETS, "weapons.json")
OUT_HTML = os.path.join(HERE, "weapons.html")

VERSION = "0.1.0"
DEFAULT_SEED = 20261013

SS = af.SS
UX, UY = af.UX, af.UY
RAMP = af.RAMP

# No slot grid: this set is not an inventory of square slots any more, so there is no
# footprint for the small size to answer to -- the box is chosen for LEGIBILITY. It
# has to hold the feature that makes the item that item (a sword its crossguard, a
# helm its vision slit), and that is what fixed the two pieces the slot used to
# squeeze: the small sword, which read as "some bladed weapon", and the small helm,
# which arrived as a solid block.

# 1x / 1.5x / 2x: the ends are exactly a factor of two apart, so shrink(large, 2)
# lands on the small grid and the two can be compared cell by cell.
SIZES = [("small", "pequena", 1.0), ("medium", "média", 1.5), ("large", "grande", 2.0)]


# --- cell-space drawing --------------------------------------------------------
# Everything is specified in CELLS, never in supersampled pixels. A part thinner
# than ~0.6 cell is averaged away by the area average, so every part in this file
# has a 1 cell floor -- and the "small" size is exactly where that floor bites.
def cpoly(d, pts, color):
    d.polygon([(x * UX, y * UY) for (x, y) in pts], fill=color)


def crect(d, x0, y0, x1, y1, color):
    if x1 <= x0 or y1 <= y0:
        return
    d.rectangle([x0 * UX, y0 * UY, x1 * UX, y1 * UY], fill=color)


def cline(d, x0, y0, x1, y1, color, width=1.0):
    d.line([(x0 * UX, y0 * UY), (x1 * UX, y1 * UY)], fill=color,
           width=max(1, int(width * UX)), joint="curve")


def cellipse(d, cx, cy, rx, ry, color):
    d.ellipse([(cx - rx) * UX, (cy - ry) * UY, (cx + rx) * UX, (cy + ry) * UY], fill=color)


CIRCLES = []          # the round geometry drawn for the piece being built, for the audit


def circle(d, cx, cy, r, color):
    """A circle ON SCREEN, where `r` is the radius in CELLS across.

    A text cell is 1.66x taller than it is wide, so an ellipse with equal radii in cell
    units comes out as a tall oval on screen: this is that correction, in one place.
    The opposite case is a horizontal DISC seen from above (a tree crown, a contact
    shadow), which is squashed on purpose -- that is the isometry, and it lives in
    `artforge.ISO_FLAT`. A stone, a mace head, a round shield and a ring are round, not
    squashed, and this is the helper that says so.
    """
    ry = r * af.CELL_W / af.CELL_H
    cellipse(d, cx, cy, r, ry, color)
    CIRCLES.append([round(r, 3), round(ry, 3)])
    return ry


def pal(**kw):
    """Every art colour goes through the ink boost exactly once (the engine's
    numbers: a glyph only covers part of its cell, so the declared colour is not the
    colour you perceive)."""
    return {k: af.boost(v) for k, v in kw.items()}


def shade(c, k):
    return af.shade(c, k)


# --- materials -----------------------------------------------------------------
def steel(palette_light=1.0):
    return pal(steel=(176, 182, 194), steel_light=(236, 240, 248), steel_dark=(88, 94, 108))


MAT = {
    "steel": pal(metal=(176, 182, 194), metal_light=(236, 240, 248), metal_dark=(88, 94, 108)),
    "iron": pal(metal=(138, 142, 150), metal_light=(196, 200, 208), metal_dark=(70, 74, 82)),
    "bronze": pal(metal=(186, 138, 74), metal_light=(230, 190, 120), metal_dark=(104, 74, 38)),
    "gold": pal(metal=(214, 176, 92), metal_light=(248, 224, 150), metal_dark=(126, 98, 40)),
    "wood": pal(metal=(112, 78, 46), metal_light=(154, 114, 66), metal_dark=(60, 40, 24)),
    "leather": pal(metal=(104, 72, 48), metal_light=(146, 106, 66), metal_dark=(56, 38, 26)),
    "cloth": pal(metal=(74, 84, 132), metal_light=(118, 130, 186), metal_dark=(38, 44, 76)),
}


def mat(name):
    return MAT[name]


# --- weapons -------------------------------------------------------------------
def w_blade(d, w, h, detail, metal, fitting, grip, gem=None, kind="sword"):
    """Dagger, sword, great sword: an upright blade with a crossguard. The blade is
    always at least 1 cell wide, which is the whole reason the small size is drawn
    instead of shrunk."""
    cx = w / 2.0
    blade_half = max(0.5, w * 0.075)
    guard_half = max(1.6, w * 0.42)
    grip_half = max(0.6, w * 0.085)
    # The guard sits LOW. Putting it at 30% of the height leaves the grip with eight
    # of twelve rows and the blade with three -- a sword drawn backwards.
    guard_y = h * (0.74 if kind != "dagger" else 0.70)
    guard_th = 1.0 if not detail else 1.4
    pommel_y = h - 0.8
    tip = 0.4
    # Edges and core stay proportional so the blade reads at 1 cell wide: the dark
    # border must not eat the light core, or the small sword arrives as a smudge.
    edge = min(0.32, blade_half * 0.35)
    core = max(0.22, blade_half - edge * 1.15)

    if kind == "great":
        blade_half = max(0.8, w * 0.09)
        guard_half = max(2.2, w * 0.40)

    # blade: tapered to a point, dark edges, light core
    cpoly(d, [(cx, tip), (cx + blade_half, tip + h * 0.05), (cx + blade_half, guard_y),
              (cx - blade_half, guard_y), (cx - blade_half, tip + h * 0.05)], metal["metal"])
    crect(d, cx - blade_half, tip + h * 0.05, cx - blade_half + edge, guard_y, metal["metal_dark"])
    crect(d, cx + blade_half - edge, tip + h * 0.05, cx + blade_half, guard_y, metal["metal_dark"])
    crect(d, cx - core, tip + h * 0.06, cx + core, guard_y, metal["metal_light"])
    if detail:                                    # the fuller: a groove down the blade
        crect(d, cx - core * 0.35, tip + h * 0.12, cx + core * 0.35,
              guard_y - 1.0, metal["metal_dark"])
    # crossguard
    crect(d, cx - guard_half, guard_y, cx + guard_half, guard_y + guard_th, fitting["metal"])
    crect(d, cx - guard_half, guard_y, cx + guard_half, guard_y + guard_th * 0.45,
          fitting["metal_light"])
    if detail:                                    # quillon tips
        circle(d, cx - guard_half, guard_y + guard_th * 0.5, 0.5, fitting["metal_light"])
        circle(d, cx + guard_half, guard_y + guard_th * 0.5, 0.5, fitting["metal_light"])
        if gem:
            circle(d, cx, guard_y + guard_th * 0.5, 0.45, gem["metal"])
    # grip and pommel
    crect(d, cx - grip_half, guard_y + guard_th, cx + grip_half, pommel_y, grip["metal"])
    crect(d, cx - grip_half, guard_y + guard_th, cx - grip_half * 0.2, pommel_y,
          grip["metal_light"])
    if detail:
        for i in range(3):
            y = guard_y + guard_th + (pommel_y - guard_y - guard_th) * (0.22 + 0.26 * i)
            cline(d, cx - grip_half, y, cx + grip_half, y, grip["metal_dark"], 1.0)
    circle(d, cx, pommel_y, max(0.7, grip_half * 1.35), fitting["metal"])
    circle(d, cx - grip_half * 0.35, pommel_y - grip_half * 0.30, max(0.3, grip_half * 0.55),
           fitting["metal_light"])


def w_mace(d, w, h, detail, metal, haft, fitting, gem=None):
    """A head at the top of a haft: flanged, spiked when there is room."""
    cx = w / 2.0
    haft_half = max(0.6, w * 0.07)
    head_r = min(w * 0.34, h * 0.20)
    head_y = head_r + 0.8
    crect(d, cx - haft_half, head_y, cx + haft_half, h - 0.6, haft["metal"])
    crect(d, cx - haft_half, head_y, cx - haft_half * 0.2, h - 0.6, haft["metal_light"])
    circle(d, cx, head_y, head_r, metal["metal"])
    circle(d, cx - head_r * 0.30, head_y - head_r * 0.34, head_r * 0.45, metal["metal_light"])
    circle(d, cx + head_r * 0.35, head_y + head_r * 0.40, head_r * 0.52, metal["metal_dark"])
    for angle in (-90, -30, 30, 90, 150, 210):    # flanges
        a = math.radians(angle)
        cline(d, cx + math.cos(a) * head_r * 0.6, head_y + math.sin(a) * head_r * 0.6,
              cx + math.cos(a) * head_r * 1.15, head_y + math.sin(a) * head_r * 1.15,
              metal["metal_dark"], 1.0)
    if detail:
        for angle in (-60, 0, 60):                # spikes
            a = math.radians(angle)
            cline(d, cx + math.cos(a) * head_r * 0.9, head_y + math.sin(a) * head_r * 0.9,
                  cx + math.cos(a) * head_r * 1.5, head_y + math.sin(a) * head_r * 1.5,
                  metal["metal_light"], 1.0)
    cline(d, cx - haft_half, head_y + 1.6, cx + haft_half, head_y + 1.6, fitting["metal"], 1.0)
    cellipse(d, cx, h - 0.6, haft_half * 1.4, 0.8, fitting["metal"])
    if gem:
        cellipse(d, cx, head_y - head_r * 0.75, 0.6, 0.6, gem["metal"])


def w_hammer(d, w, h, detail, metal, haft, fitting):
    """A rectangular head: the silhouette that says 'hit hard'."""
    cx = w / 2.0
    haft_half = max(0.6, w * 0.07)
    head_w = w * 0.42
    head_h = max(1.4, h * 0.11)
    head_y = 0.8
    crect(d, cx - haft_half, head_y + head_h * 0.5, cx + haft_half, h - 0.6, haft["metal"])
    crect(d, cx - haft_half, head_y + head_h * 0.5, cx - haft_half * 0.2, h - 0.6,
          haft["metal_light"])
    crect(d, cx - head_w, head_y, cx + head_w, head_y + head_h, metal["metal"])
    crect(d, cx - head_w, head_y, cx + head_w, head_y + head_h * 0.30, metal["metal_light"])
    crect(d, cx - head_w, head_y + head_h * 0.72, cx + head_w, head_y + head_h,
          metal["metal_dark"])
    crect(d, cx - head_w * 0.35, head_y, cx + head_w * 0.35, head_y + head_h,
          metal["metal_dark"])
    if detail:
        for i in (-1, 1):                          # the banded ends of the head
            crect(d, cx + i * head_w * 0.82, head_y - 0.4, cx + i * head_w, head_y + head_h + 0.4,
                  metal["metal_dark"])
            crect(d, cx + i * head_w * 0.66, head_y - 0.2, cx + i * head_w * 0.82,
                  head_y + head_h + 0.2, metal["metal_light"])
    cline(d, cx - haft_half, head_y + head_h + 1.4, cx + haft_half, head_y + head_h + 1.4,
          fitting["metal"], 1.0)
    cellipse(d, cx, h - 0.6, haft_half * 1.4, 0.8, fitting["metal"])


def w_axe(d, w, h, detail, metal, haft, fitting, double=False):
    """A crescent blade on a haft. Two crescents when the handle is long enough."""
    cx = w / 2.0
    haft_half = max(0.6, w * 0.055)
    top = 0.6
    bot = h - 0.6
    crect(d, cx - haft_half, top, cx + haft_half, bot, haft["metal"])
    crect(d, cx - haft_half, top, cx - haft_half * 0.2, bot, haft["metal_light"])
    blade_top = h * 0.10
    blade_bot = h * 0.46
    span = cx - haft_half
    sides = (-1, 1) if double else (1,)
    for side in sides:
        outer = haft_half + span * 0.94
        cpoly(d, [(cx + side * haft_half, blade_top + 0.6),
                  (cx + side * outer * 0.72, blade_top),
                  (cx + side * outer, (blade_top + blade_bot) * 0.5),
                  (cx + side * outer * 0.66, blade_bot),
                  (cx + side * haft_half, blade_bot - 0.8)], metal["metal"])
        cpoly(d, [(cx + side * haft_half, blade_top + 0.6),
                  (cx + side * outer * 0.62, blade_top + 0.5),
                  (cx + side * outer * 0.78, (blade_top + blade_bot) * 0.5),
                  (cx + side * haft_half, blade_bot - 0.9)], metal["metal_light"])
        cpoly(d, [(cx + side * outer * 0.70, blade_top + 0.4),
                  (cx + side * outer, (blade_top + blade_bot) * 0.5),
                  (cx + side * outer * 0.66, blade_bot),
                  (cx + side * outer * 0.74, (blade_top + blade_bot) * 0.5)], metal["metal_dark"])
    if detail:
        cline(d, cx - haft_half, blade_bot + 0.6, cx + haft_half, blade_bot + 0.6,
              fitting["metal"], 1.0)
        cline(d, cx - haft_half, top + 1.2, cx + haft_half, top + 1.2, fitting["metal"], 1.0)
    cellipse(d, cx, bot, haft_half * 1.5, 0.8, fitting["metal"])


def w_polearm(d, w, h, detail, metal, haft, fitting, halberd=False):
    """Spear and halberd: a long haft, a point, and on the halberd a blade crosswise."""
    cx = w / 2.0
    haft_half = max(0.5, w * 0.075)
    head_h = h * (0.20 if halberd else 0.24)
    crect(d, cx - haft_half, head_h * 0.9, cx + haft_half, h - 0.5, haft["metal"])
    crect(d, cx - haft_half, head_h * 0.9, cx - haft_half * 0.2, h - 0.5, haft["metal_light"])
    head_half = max(1.0, w * 0.42)
    cpoly(d, [(cx, 0.5), (cx + head_half, head_h * 0.42), (cx + haft_half, head_h),
              (cx - haft_half, head_h), (cx - head_half, head_h * 0.42)], metal["metal"])
    cpoly(d, [(cx, 0.5), (cx + head_half * 0.35, head_h * 0.44), (cx + haft_half * 0.6, head_h),
              (cx - haft_half * 0.6, head_h), (cx - head_half * 0.35, head_h * 0.44)],
          metal["metal_light"])
    if halberd:
        span = cx - haft_half
        outer = haft_half + span * 0.92
        top = head_h * 1.05
        bot = head_h * 1.18 + h * 0.14
        cpoly(d, [(cx + haft_half, top), (cx + outer * 0.7, top + 0.5),
                  (cx + outer, (top + bot) * 0.5), (cx + outer * 0.6, bot),
                  (cx + haft_half, bot - 0.6)], metal["metal"])
        cpoly(d, [(cx + haft_half, top + 0.4), (cx + outer * 0.6, top + 0.6),
                  (cx + outer * 0.75, (top + bot) * 0.5), (cx + haft_half, bot - 0.7)],
              metal["metal_light"])
        cline(d, cx - haft_half, bot + 0.5, cx + haft_half, bot + 0.5, fitting["metal"], 1.0)
    else:
        cline(d, cx - haft_half * 1.3, head_h * 1.1, cx + haft_half * 1.3, head_h * 1.1,
              fitting["metal"], 1.0)
    if detail:
        cline(d, cx - haft_half, h * 0.72, cx + haft_half, h * 0.72, fitting["metal"], 1.0)
        cline(d, cx - haft_half, h * 0.78, cx + haft_half, h * 0.78, fitting["metal_dark"], 1.0)


def w_bow(d, w, h, detail, wood, string, fitting):
    """An arc and a straight string: the arc is the whole read."""
    cx = w / 2.0
    top, bot = 0.8, h - 0.8
    reach = w * 0.40
    steps = max(8, int(h))
    limb = max(1.6, w * 0.11)
    for i in range(steps + 1):
        f = i / float(steps)
        y = top + (bot - top) * f
        bulge = math.sin(math.pi * f)              # 0 at the tips, 1 at the belly
        x = cx - reach * 0.15 - reach * bulge
        cline(d, x, y, x + 0.1, y + (bot - top) / steps, wood["metal"], limb)
        if detail and i % 3 == 0:
            cline(d, x, y, x - 0.7, y, wood["metal_light"], 1.0)
    cline(d, cx - reach * 0.15, top, cx - reach * 0.15, bot, string["metal"], 1.0)
    mid = (top + bot) * 0.5
    crect(d, cx - reach * 0.15 - 0.7, mid - 1.6, cx - reach * 0.15 + 0.7, mid + 1.6,
          fitting["metal"])
    crect(d, cx - reach * 0.15 - 0.7, mid - 1.6, cx - reach * 0.15 - 0.1, mid + 1.6,
          fitting["metal_light"])
    if detail:
        for i in (-1, 1):
            cellipse(d, cx - reach * 0.15, mid + i * 1.6, 0.6, 0.6, fitting["metal_dark"])


def w_staff(d, w, h, detail, wood, metal, gem):
    """A shaft with an orb held by prongs."""
    cx = w / 2.0
    shaft_half = max(0.6, w * 0.09)
    head_y = h * 0.16
    crect(d, cx - shaft_half, head_y, cx + shaft_half, h - 0.5, wood["metal"])
    crect(d, cx - shaft_half, head_y, cx - shaft_half * 0.2, h - 0.5, wood["metal_light"])
    orb_r = min(w * 0.30, h * 0.16)
    circle(d, cx, head_y - 0.4, orb_r, gem["metal"])
    circle(d, cx - orb_r * 0.35, head_y - orb_r * 0.55, orb_r * 0.42,
           shade(gem["metal"], 1.35))
    circle(d, cx + orb_r * 0.40, head_y + orb_r * 0.25, orb_r * 0.46,
           shade(gem["metal"], 0.62))
    for side in (-1, 1):                           # prongs
        cline(d, cx + side * shaft_half * 0.8, head_y + 0.4, cx + side * orb_r * 1.25,
              head_y - orb_r * 0.9, metal["metal"], 1.0)
        if detail:
            cline(d, cx + side * orb_r * 1.25, head_y - orb_r * 0.9, cx + side * orb_r * 0.5,
                  head_y - orb_r * 1.7, metal["metal_light"], 1.0)


def w_shield(d, w, h, detail, style, body, metal, boss, emblem=None):
    """A shield reads by its OUTLINE, so the shape is the style: round, kite (the
    teardrop) and tower (a tall rectangle with a curved top)."""
    cx = w / 2.0
    top, bot = 1.0, h - 1.0
    half = w * 0.40

    if style == "round":
        cy = (top + bot) / 2.0
        rr = min(half, ((bot - top) / 2.0) / (af.CELL_W / af.CELL_H))
        circle(d, cx, cy, rr, body["metal"])
        circle(d, cx - rr * 0.20, cy - rr * 0.20, rr * 0.66, body["metal_light"])
        circle(d, cx + rr * 0.34, cy + rr * 0.30, rr * 0.52, body["metal_dark"])
        circle(d, cx, cy, rr * 0.30, boss["metal"])
        circle(d, cx - rr * 0.10, cy - rr * 0.14, rr * 0.13, shade(boss["metal"], 1.35))
        if detail:
            for k in range(8):
                a = math.radians(k * 45)
                circle(d, cx + math.cos(a) * rr * 0.84, cy + math.sin(a) * rr * 0.84,
                       max(0.22, rr * 0.07), metal["metal"])
        return

    if style == "tower":
        cpoly(d, [(cx - half, top + h * 0.10), (cx - half * 0.62, top), (cx + half * 0.62, top),
                  (cx + half, top + h * 0.10), (cx + half, bot - 1.4), (cx, bot),
                  (cx - half, bot - 1.4)], body["metal"])
        cpoly(d, [(cx - half * 0.84, top + h * 0.16), (cx - half * 0.52, top + 0.8),
                  (cx - half * 0.16, bot - 1.6), (cx - half * 0.74, bot - 1.4)],
              body["metal_light"])
        cpoly(d, [(cx + half * 0.30, top + 0.8), (cx + half * 0.84, top + h * 0.16),
                  (cx + half * 0.84, bot - 1.5), (cx + half * 0.34, bot - 0.9)],
              body["metal_dark"])
        boss_y = top + h * 0.42
    else:
        cpoly(d, [(cx - half, top), (cx + half, top), (cx + half, bot - h * 0.22),
                  (cx, bot), (cx - half, bot - h * 0.22)], body["metal"])
        cpoly(d, [(cx - half * 0.90, top + 0.6), (cx + half * 0.90, top + 0.6),
                  (cx + half * 0.90, bot - h * 0.26), (cx, bot - 1.2),
                  (cx - half * 0.90, bot - h * 0.26)], body["metal_light"])
        cpoly(d, [(cx + half * 0.44, top + 0.6), (cx + half * 0.90, top + 0.6),
                  (cx + half * 0.90, bot - h * 0.26), (cx, bot - 1.2),
                  (cx + half * 0.10, bot - 0.8)], body["metal_dark"])
        boss_y = top + h * 0.34

    crect(d, cx - half, top, cx + half, top + 1.0, metal["metal"])
    crect(d, cx - half, top, cx + half, top + 0.4, metal["metal_light"])
    if emblem:
        crect(d, cx - 0.5, top + 1.2, cx + 0.5, boss_y - 0.4, emblem["metal"])
        crect(d, cx - half * 0.5, boss_y + 0.9, cx + half * 0.5, boss_y + 1.9, emblem["metal"])
    cellipse(d, cx, boss_y, max(0.8, w * 0.13), max(0.7, h * 0.08), boss["metal"])
    cellipse(d, cx - w * 0.05, boss_y - h * 0.03, max(0.4, w * 0.05), max(0.35, h * 0.04),
             shade(boss["metal"], 1.35))
    if detail:
        for i in (-1, 1):
            for j in range(3):
                y = top + 2.0 + j * (h - 4.5) / 2.4
                cellipse(d, cx + i * half * 0.76, y, 0.6, 0.7, metal["metal"])
        cline(d, cx - half, bot - h * 0.20, cx, bot, metal["metal_dark"], 1.0)
        cline(d, cx + half, bot - h * 0.20, cx, bot, metal["metal_dark"], 1.0)


def w_helm(d, w, h, detail, style, metal, leather, fitting, gem=None):
    """Six helms, one routine: cap (leather), iron (dome + nasal), great (a closed
    barrel with a full slit), horned, hood (cloth) and crown.

    The rule from the slot era outlives the slot: a helm needs room for the BREAK --
    the vision slit is what makes it a helm and not a rock. With the footprint gone
    the small box is chosen for legibility instead, which is what fixes the helmet
    that used to arrive as a solid block.
    """
    cx = w / 2.0
    half = w * 0.40
    top, bot = 1.0, h - 1.2

    if style == "crown":
        band = h * 0.44
        crect(d, cx - half, band, cx + half, bot, metal["metal"])
        crect(d, cx - half, band, cx + half, band + 0.8, metal["metal_light"])
        crect(d, cx - half, bot - 1.0, cx + half, bot, fitting["metal"])
        count = 3 if w < 14 else 5
        for k in range(count):
            x = cx - half * 0.74 + k * (half * 1.48 / (count - 1))
            cpoly(d, [(x - 0.7, band), (x + 0.7, band), (x, band - h * 0.26)], metal["metal"])
            cpoly(d, [(x - 0.4, band - 0.1), (x + 0.4, band - 0.1), (x, band - h * 0.18)],
                  metal["metal_light"])
            if gem:
                cellipse(d, x, band + 0.5, 0.5, 0.5, gem["metal"])
        return

    if style == "hood":
        cpoly(d, [(cx, top), (cx + half * 0.62, top + h * 0.26), (cx + half * 0.92, h * 0.60),
                  (cx + half * 1.0, bot), (cx - half * 1.0, bot), (cx - half * 0.92, h * 0.60),
                  (cx - half * 0.62, top + h * 0.26)], metal["metal"])
        cpoly(d, [(cx, top + 0.7), (cx + half * 0.46, top + h * 0.28),
                  (cx + half * 0.64, h * 0.58), (cx, h * 0.64), (cx - half * 0.64, h * 0.58),
                  (cx - half * 0.46, top + h * 0.28)], metal["metal_light"])
        cpoly(d, [(cx + half * 0.26, top + h * 0.30), (cx + half * 0.80, h * 0.56),
                  (cx + half * 0.90, bot), (cx + half * 0.30, bot)], metal["metal_dark"])
        cellipse(d, cx, h * 0.50, half * 0.42, h * 0.15, shade(metal["metal_dark"], 0.35))
        if detail:
            cline(d, cx - half * 0.84, h * 0.72, cx + half * 0.84, h * 0.72,
                  fitting["metal"], 1.0)
        return

    if style == "great":
        dome_top = top + 0.4
        cpoly(d, [(cx - half * 0.92, dome_top + h * 0.06), (cx - half * 0.60, dome_top),
                  (cx + half * 0.60, dome_top), (cx + half * 0.92, dome_top + h * 0.06),
                  (cx + half, h * 0.70), (cx + half * 0.78, bot), (cx - half * 0.78, bot),
                  (cx - half, h * 0.70)], metal["metal"])
        crect(d, cx - half * 0.86, dome_top + h * 0.06, cx + half * 0.86,
              dome_top + h * 0.06 + 0.9, metal["metal_light"])
        crect(d, cx - 0.6, dome_top, cx + 0.6, bot - 0.2, metal["metal_light"])      # the ridge
        slit = shade(metal["metal_dark"], 0.42)
        crect(d, cx - half * 0.84, h * 0.44, cx + half * 0.84, h * 0.44 + 1.4, slit)
        crect(d, cx - 0.7, h * 0.52, cx + 0.7, bot - 0.5, shade(metal["metal_dark"], 0.5))
        if detail:
            for k in range(3):
                cline(d, cx - half * 0.5, h * 0.64 + k * 0.9, cx + half * 0.5,
                      h * 0.64 + k * 0.9, metal["metal_dark"], 0.9)
            crect(d, cx - half, h * 0.22, cx + half, h * 0.22 + 0.8, fitting["metal"])
        return

    dome_bot = h * 0.56
    cpoly(d, [(cx - half, dome_bot), (cx - half, dome_bot - h * 0.16),
              (cx - half * 0.5, top + 0.3), (cx, top), (cx + half * 0.5, top + 0.3),
              (cx + half, dome_bot - h * 0.16), (cx + half, dome_bot)], metal["metal"])
    cpoly(d, [(cx - half * 0.86, dome_bot - h * 0.02), (cx - half * 0.42, top + 0.8),
              (cx, top + 0.5), (cx - half * 0.10, dome_bot - h * 0.02)], metal["metal_light"])
    cpoly(d, [(cx + half * 0.30, top + 0.9), (cx + half * 0.86, top + 1.6),
              (cx + half * 0.86, dome_bot - h * 0.02), (cx + half * 0.30, dome_bot - h * 0.02)],
          metal["metal_dark"])

    if style == "cap":
        crect(d, cx - half, dome_bot - 0.9, cx + half, dome_bot + 0.3, metal["metal_dark"])
        crect(d, cx - half, dome_bot - 0.9, cx + half, dome_bot - 0.3, metal["metal_light"])
        for i in (-1, 1):
            crect(d, cx + i * half * 0.74, dome_bot, cx + i * half * 0.94, bot,
                  leather["metal"])
        if detail:
            crect(d, cx - half, top + h * 0.16, cx + half, top + h * 0.16 + 0.9,
                  fitting["metal"])
        return

    if style == "horned":
        for i in (-1, 1):
            bx = cx + i * half * 0.76
            by = dome_bot - h * 0.16
            cpoly(d, [(bx, by + 1.2), (bx + i * half * 0.34, by - h * 0.06),
                      (bx + i * half * 0.66, by - h * 0.34), (bx + i * half * 0.44, by - h * 0.30),
                      (bx + i * half * 0.16, by - h * 0.04), (bx, by - 0.3)],
                  fitting["metal_light"])
            cpoly(d, [(bx, by + 1.2), (bx + i * half * 0.20, by - h * 0.02),
                      (bx + i * half * 0.40, by - h * 0.20), (bx, by - 0.3)],
                  fitting["metal_dark"])

    # cheeks and the vision slit -- the slit is the BREAK, the dark line the eye needs
    cpoly(d, [(cx - half, dome_bot), (cx + half, dome_bot), (cx + half * 0.86, bot),
              (cx - half * 0.86, bot)], metal["metal_dark"])
    crect(d, cx - half * 0.70, dome_bot + 0.2, cx + half * 0.70, dome_bot + 1.8,
          shade(metal["metal_dark"], 0.42))
    crect(d, cx - 0.7, dome_bot - h * 0.20, cx + 0.7, bot - 0.1, metal["metal_dark"])   # nasal
    crect(d, cx - 0.4, dome_bot - h * 0.20, cx + 0.4, bot - 0.1, metal["metal"])
    if detail:
        crect(d, cx - half, top + 1.2, cx + half, top + 2.0, fitting["metal"])
        cline(d, cx - half * 0.9, bot - 0.6, cx + half * 0.9, bot - 0.6, fitting["metal"], 1.0)


def w_armor(d, w, h, detail, style, metal, leather, fitting, gem=None):
    """Six chests, one routine. The trade is the surface: leather lacing, chain rings,
    plate (a sternum ridge and two round bosses), scale rows, a cloth robe with a
    collar and a sash, and a gilded plate with trim and a gem."""
    cx = w / 2.0
    half = w * 0.44
    top, waist = 0.8, h * 0.74

    if style == "robe":
        cpoly(d, [(cx - half * 0.52, top + h * 0.06), (cx - half * 0.16, top),
                  (cx + half * 0.16, top), (cx + half * 0.52, top + h * 0.06),
                  (cx + half * 1.00, h - 0.9), (cx + half * 0.92, h - 0.4),
                  (cx - half * 0.92, h - 0.4), (cx - half * 1.00, h - 0.9)], metal["metal"])
        cpoly(d, [(cx - half * 0.42, top + h * 0.10), (cx - half * 0.06, top + h * 0.04),
                  (cx - half * 0.30, h - 0.7), (cx - half * 0.72, h - 0.7)],
              metal["metal_light"])
        cpoly(d, [(cx + half * 0.20, top + h * 0.04), (cx + half * 0.46, top + h * 0.10),
                  (cx + half * 0.86, h - 0.7), (cx + half * 0.40, h - 0.7)],
              metal["metal_dark"])
        crect(d, cx - half * 0.34, top, cx + half * 0.34, top + 1.0, fitting["metal"])
        crect(d, cx - half * 0.70, waist, cx + half * 0.70, waist + 1.1, fitting["metal"])
        crect(d, cx - half * 0.70, waist, cx + half * 0.70, waist + 0.4,
              fitting["metal_light"])
        if detail:
            for k in range(3):
                cline(d, cx - half * 0.60, h - 1.6 - k * 1.1, cx + half * 0.60,
                      h - 1.6 - k * 1.1, metal["metal_dark"], 0.9)
        return

    cpoly(d, [(cx - half * 0.92, top + h * 0.10), (cx - half * 0.30, top),
              (cx + half * 0.30, top), (cx + half * 0.92, top + h * 0.10),
              (cx + half * 0.62, waist), (cx + half * 0.34, h - 0.6),
              (cx - half * 0.34, h - 0.6), (cx - half * 0.62, waist)], metal["metal"])
    cpoly(d, [(cx - half * 0.78, top + h * 0.14), (cx - half * 0.20, top + h * 0.05),
              (cx - half * 0.02, waist - 0.8), (cx - half * 0.42, h - 1.0),
              (cx - half * 0.52, waist)], metal["metal_light"])
    cpoly(d, [(cx + half * 0.30, top + h * 0.04), (cx + half * 0.86, top + h * 0.14),
              (cx + half * 0.56, waist), (cx + half * 0.30, h - 0.8),
              (cx + half * 0.16, waist - 0.8)], metal["metal_dark"])

    if style == "chain":
        step = max(1.0, w * 0.11)
        y, row = top + h * 0.20, 0
        while y < waist + 0.4:
            x = cx - half * 0.60 + (step * 0.5 if row % 2 else 0.0)
            while x < cx + half * 0.60:
                cellipse(d, x, y, step * 0.36, step * 0.30, metal["metal_dark"])
                cellipse(d, x, y, step * 0.20, step * 0.17, metal["metal_light"])
                x += step
            y += step * 0.82
            row += 1
    elif style == "scale":
        step = max(1.1, w * 0.14)
        y, row = top + h * 0.18, 0
        while y < waist + 0.3:
            x = cx - half * 0.66 + (step * 0.5 if row % 2 else 0.0)
            while x < cx + half * 0.66:
                cpoly(d, [(x - step * 0.50, y), (x + step * 0.50, y), (x, y + step * 0.66)],
                      metal["metal_dark"])
                cpoly(d, [(x - step * 0.38, y + 0.25), (x + step * 0.38, y + 0.25),
                          (x, y + step * 0.50)], metal["metal_light"])
                x += step
            y += step * 0.58
            row += 1
    elif style in ("plate", "gilded"):
        crect(d, cx - half * 0.30, top + h * 0.26, cx + half * 0.30, waist - 1.0,
              metal["metal_dark"])
        crect(d, cx - half * 0.24, top + h * 0.28, cx + half * 0.24, waist - 1.2,
              metal["metal"])
        for i in (-1, 1):
            cellipse(d, cx + i * half * 0.60, top + h * 0.48, half * 0.28, h * 0.15,
                     metal["metal"])
            cellipse(d, cx + i * half * 0.60, top + h * 0.44, half * 0.22, h * 0.09,
                     metal["metal_light"])
        if style == "gilded":
            # The gilded plate has to differ from the plain one at EVERY size -- if the
            # gold only appears on the large, the two are the same art small and the
            # bank's hash check calls that a duplicate (it did).
            for i in (-1, 1):
                crect(d, cx + i * half * 0.30, top + h * 0.22, cx + i * half * 0.88,
                      waist - 1.2, fitting["metal"])
                crect(d, cx + i * half * 0.30, top + h * 0.22, cx + i * half * 0.60,
                      waist - 1.2, fitting["metal_light"])
            cellipse(d, cx, top + h * 0.30, max(0.6, w * 0.08), max(0.5, h * 0.05),
                     gem["metal"] if gem else fitting["metal"])
    elif style == "leather":
        crect(d, cx - 0.6, top + h * 0.10, cx + 0.6, h - 0.9, leather["metal_dark"])
        for k in range(4 if detail else 3):
            y = top + h * (0.20 + 0.16 * k)
            cline(d, cx - 0.6, y, cx + 0.6, y + 0.7, leather["metal_light"], 1.0)
        for i in (-1, 1):
            cline(d, cx + i * half * 0.34, top + h * 0.10, cx + i * half * 0.60, waist,
                  leather["metal_dark"], 1.0)

    for side in (-1, 1):
        cellipse(d, cx + side * half * 0.86, top + h * 0.10, half * 0.22, h * 0.11,
                 metal["metal"])
        cellipse(d, cx + side * half * 0.86, top + h * 0.06, half * 0.16, h * 0.06,
                 metal["metal_light"])
    crect(d, cx - half * 0.70, waist - 0.8, cx + half * 0.70, h - 0.8, leather["metal"])
    crect(d, cx - half * 0.70, waist - 0.8, cx + half * 0.70, waist - 0.2,
          leather["metal_light"])
    if detail:
        if style in ("plate", "gilded", "leather"):
            for i in range(3):
                y = top + h * (0.40 + 0.12 * i)
                crect(d, cx - half * 0.34, y, cx + half * 0.34, y + 0.7, fitting["metal"])
        cellipse(d, cx, top + h * 0.30, 0.7, 0.7, fitting["metal"])
        if style == "gilded":
            for k in range(3):
                y = top + h * (0.30 + 0.14 * k)
                crect(d, cx + half * 0.30, y, cx + half * 0.88, y + 1.0, fitting["metal"])
                crect(d, cx - half * 0.88, y, cx - half * 0.30, y + 1.0, fitting["metal"])
            if gem:
                cellipse(d, cx, top + h * 0.44, 0.9, 0.9, gem["metal"])


# The aspect each piece is meant to have ON SCREEN (ink width / ink height in pixels).
#
# A text cell is 1.66x taller than wide, so "the box looks right" in cells says nothing
# about how the piece reads: the chests sat at 0.60 (a column, not a torso) and the
# great helm at 0.77 while a helm is about square. Declared here so it can be checked --
# a number nobody wrote down is a number nobody can regress. (Rounded down to two
# decimals from the measurement, so the check catches drift, not float noise.)
ASPECT = {
    "weapon.dagger": 0.43, "weapon.sword.short": 0.27, "weapon.sword.long": 0.24,
    "weapon.sword.great": 0.28, "weapon.mace": 0.28, "weapon.warhammer": 0.47,
    "weapon.axe": 0.34, "weapon.battleaxe": 0.42, "weapon.spear": 0.24,
    "weapon.halberd": 0.24, "weapon.bow": 0.38, "weapon.staff": 0.24,
    "armor.helm.cap": 1.08, "armor.helm.iron": 0.92, "armor.helm.great": 0.91,
    "armor.helm.horned": 1.14, "armor.helm.hood": 0.70, "armor.helm.crown": 1.08,
    "armor.chest.leather": 1.03, "armor.chest.chain": 1.03, "armor.chest.plate": 1.03,
    "armor.chest.scale": 1.03, "armor.chest.robe": 0.80, "armor.chest.gilded": 1.03,
    "armor.shield.round": 1.05, "armor.shield.kite": 0.60, "armor.shield.tower": 0.42,
    "jewelry.ring": 1.00,
}


def w_ring(d, w, h, detail, metal, gem):
    """A band and a stone, and at this size the two circles ARE the read.

    This is the one piece in the set where 'round' is the feature, so the band, the hole
    and the stone all go through circle() -- drawn in cell units they came out as a tall
    oval, which is exactly what the eye was complaining about."""
    cx = w / 2.0
    r = max(0.9, min(w * 0.42, h * 0.42))
    band = max(0.5, r * 0.32)
    gem_r = max(0.5, r * 0.40)
    ry = r * af.CELL_W / af.CELL_H
    cy = h * 0.60
    circle(d, cx, cy, r, metal["metal"])                       # the band
    circle(d, cx, cy, r - band, (0, 0, 0))                     # the hole: background
    circle(d, cx - r * 0.34, cy - ry * 0.42, r * 0.24, metal["metal_light"])
    # The stone sits IN the band's top, not above it: a ring with the stone sticking out
    # is 0.6 (a lollipop) where a ring is round, and the band is what reads as round.
    circle(d, cx, cy - ry * 0.52, gem_r, gem["metal"])
    circle(d, cx - gem_r * 0.30, cy - ry * 0.52 - gem_r * 0.30, gem_r * 0.34,
           shade(gem["metal"], 1.4))
    if detail:
        for angle in range(0, 360, 45):
            a = math.radians(angle)
            circle(d, cx + math.cos(a) * (r - band * 0.5),
                   cy + math.sin(a) * (ry - band * 0.5 * af.CELL_W / af.CELL_H),
                   max(0.22, band * 0.28), metal["metal_dark"])


# --- the set --------------------------------------------------------------------
# id, label, category, style, small box in cells, routine, materials
ITEMS = [
    ("weapon.dagger", "Adaga", "weapon", None, (5, 7), w_blade,
     dict(metal="steel", fitting="gold", grip="leather", kind="dagger")),
    ("weapon.sword.short", "Espada curta", "weapon", None, (6, 11), w_blade,
     dict(metal="steel", fitting="steel", grip="leather", kind="sword")),
    ("weapon.sword.long", "Espada longa", "weapon", None, (6, 13), w_blade,
     dict(metal="steel", fitting="gold", grip="leather", kind="sword")),
    ("weapon.sword.great", "Montante", "weapon", None, (8, 15), w_blade,
     dict(metal="steel", fitting="gold", grip="leather", kind="great")),
    ("weapon.mace", "Maça", "weapon", None, (6, 11), w_mace,
     dict(metal="iron", haft="wood", fitting="iron")),
    ("weapon.warhammer", "Marreta", "weapon", None, (8, 10), w_hammer,
     dict(metal="steel", haft="wood", fitting="iron")),
    ("weapon.axe", "Machado", "weapon", None, (8, 10), w_axe,
     dict(metal="steel", haft="wood", fitting="iron")),
    ("weapon.battleaxe", "Machado de guerra", "weapon", None, (9, 13), w_axe,
     dict(metal="steel", haft="wood", fitting="gold", double=True)),
    ("weapon.spear", "Lança", "weapon", None, (5, 13), w_polearm,
     dict(metal="steel", haft="wood", fitting="iron")),
    ("weapon.halberd", "Alabarda", "weapon", None, (6, 14), w_polearm,
     dict(metal="steel", haft="wood", fitting="gold", halberd=True)),
    ("weapon.bow", "Arco", "weapon", None, (10, 9), w_bow,
     dict(wood="wood", string="leather", fitting="iron")),
    ("weapon.staff", "Cajado", "weapon", None, (6, 14), w_staff,
     dict(wood="wood", metal="gold", gem_color=(92, 96, 214))),
    # six helms, one routine -- the style is the silhouette, and each has to survive
    # in its own small box
    ("armor.helm.cap", "Barrete de couro", "armor", "cap", (9, 7), w_helm,
     dict(metal="leather", leather="leather", fitting="iron")),
    ("armor.helm.iron", "Elmo de ferro", "armor", "iron", (9, 8), w_helm,
     dict(metal="iron", leather="leather", fitting="iron")),
    ("armor.helm.great", "Elmo fechado", "armor", "great", (9, 8), w_helm,
     dict(metal="steel", leather="leather", fitting="gold")),
    ("armor.helm.horned", "Elmo com chifres", "armor", "horned", (11, 7), w_helm,
     dict(metal="bronze", leather="leather", fitting="gold")),
    ("armor.helm.hood", "Capuz", "armor", "hood", (9, 8), w_helm,
     dict(metal="cloth", leather="cloth", fitting="gold")),
    ("armor.helm.crown", "Coroa", "armor", "crown", (9, 7), w_helm,
     dict(metal="gold", leather="leather", fitting="gold", gem_color=(180, 40, 48))),
    # six chests. At 10x10 the ink came out 60 x 99 px -- a column, not a torso: the box
    # was square in CELLS, which is 1.66:1 on screen.
    ("armor.chest.leather", "Gibão de couro", "armor", "leather", (12, 8), w_armor,
     dict(metal="leather", leather="leather", fitting="iron")),
    ("armor.chest.chain", "Cota de malha", "armor", "chain", (12, 8), w_armor,
     dict(metal="iron", leather="leather", fitting="iron")),
    ("armor.chest.plate", "Peitoral de placas", "armor", "plate", (12, 8), w_armor,
     dict(metal="steel", leather="leather", fitting="gold")),
    ("armor.chest.scale", "Armadura de escamas", "armor", "scale", (12, 8), w_armor,
     dict(metal="bronze", leather="leather", fitting="gold")),
    ("armor.chest.robe", "Túnica", "armor", "robe", (12, 9), w_armor,
     dict(metal="cloth", leather="cloth", fitting="gold")),
    ("armor.chest.gilded", "Peitoral dourado", "armor", "gilded", (12, 8), w_armor,
     dict(metal="steel", leather="leather", fitting="gold", gem_color=(180, 40, 48))),
    # three shield shapes
    ("armor.shield.round", "Escudo redondo", "armor", "round", (9, 6), w_shield,
     dict(body="wood", metal="iron", boss="gold", emblem_color=(150, 44, 44))),
    ("armor.shield.kite", "Escudo em gota", "armor", "kite", (9, 11), w_shield,
     dict(body="wood", metal="iron", boss="gold", emblem_color=(150, 44, 44))),
    ("armor.shield.tower", "Escudo torre", "armor", "tower", (8, 12), w_shield,
     dict(body="wood", metal="iron", boss="steel", emblem_color=(60, 90, 150))),
    # 7x7 and not 5x5: the ring's HOLE is the feature, and inside a 5-cell box it comes
    # out under a cell wide -- a cell is 6.6 x 11 px, so there is nowhere to put it.
    ("jewelry.ring", "Anel", "jewelry", None, (7, 7), w_ring,
     dict(metal="gold", gem_color=(180, 40, 48))),
]

GEM_PALETTES = {}   # colours are turned into materials by tone() at build time


def tone(c):
    """A one-off material from a single colour: three shades of it, boosted once."""
    return pal(metal=c, metal_light=af.shade(c, 1.45), metal_dark=af.shade(c, 0.55))


def build_item(item, size_id, scale, seed):
    (item_id, label, category, style, box, routine, mats) = item
    w = max(4, int(round(box[0] * scale)))
    h = max(3, int(round(box[1] * scale)))
    detail = size_id == "large" or (size_id == "medium" and scale >= 1.5)
    img = Image.new("RGB", (int(round(w * UX)), int(round(h * UY))), (0, 0, 0))
    d = ImageDraw.Draw(img)
    kw = {}
    if style:
        kw["style"] = style
    for key, value in mats.items():
        if key.endswith("_color"):
            kw[key[:-6]] = tone(value)             # a raw colour becomes a 3-shade material
        elif isinstance(value, str) and value in MAT:
            kw[key] = mat(value)                   # a material name resolves to its palette
        else:
            kw[key] = value                        # a geometry knob passes through
    CIRCLES.clear()
    routine(d, w, h, detail, **kw)
    return img, w, h, detail, list(CIRCLES)


def shift_grid(rows, w, h, dx, dy):
    out = [{"g": " " * w, "c": [""] * w} for _ in range(h)]
    for y in range(h):
        ny = y + dy
        if not (0 <= ny < h):
            continue
        for x in range(w):
            nx = x + dx
            if not (0 <= nx < w) or rows[y]["g"][x] == " ":
                continue
            out[ny]["g"] = out[ny]["g"][:nx] + rows[y]["g"][x] + out[ny]["g"][nx + 1:]
            out[ny]["c"][nx] = rows[y]["c"][x]
    return out


def to_cells(img, w, h):
    """Sample to cells WITHOUT cropping. An icon declares its grid: the box is the
    resolution, and the piece has to sit centred in it, so trimming the box would
    throw away the very thing the box was chosen for."""
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

    # An item has no ground to stand on: it is centred on its anchor, so shift the
    # sampled grid until the ink's bounding box sits in the middle of the box. Done
    # AFTER sampling on purpose -- the box stays exactly the declared resolution.
    # Two passes: the shift is whole cells, and one pass can still land a cell off.
    for _ in range(2):
        cols = [x for x in range(w) if any(rows[y]["g"][x] != " " for y in range(h))]
        rws = [y for y in range(h) if any(g != " " for g in rows[y]["g"])]
        if not cols or not rws:
            break
        dx = w // 2 - (min(cols) + max(cols)) // 2
        dy = h // 2 - (min(rws) + max(rws)) // 2
        if not dx and not dy:
            break
        rows = shift_grid(rows, w, h, dx, dy)
    return {"rows": rows, "levels": [round(lo, 1), round(hi, 1)]}


def shrink(piece, factor=2):
    """The runtime bridge: halve (or quarter) the grid by averaging blocks.

    It is mirrored in the page in JavaScript so the same piece can be adapted live.
    It is NOT a substitute for an authored size: averaging a 1-cell crossguard into
    the blade is how the signature disappears, and the audit measures exactly that.
    """
    src = piece["cells"]
    w, h = piece["w"], piece["h"]
    ow, oh = max(1, w // factor), max(1, h // factor)
    lo, hi = piece["levels"]
    span = max(1.0, hi - lo)
    rows = []
    for by in range(oh):
        glyphs, colors = [], []
        for bx in range(ow):
            block = [(src[y]["g"][x], src[y]["c"][x])
                     for y in range(by * factor, min(h, (by + 1) * factor))
                     for x in range(bx * factor, min(w, (bx + 1) * factor))]
            inked = [(g, c) for (g, c) in block if g != " "]
            if not inked:
                glyphs.append(" ")
                colors.append("")
                continue
            tot = [0.0, 0.0, 0.0]
            for (_g, c) in inked:
                tot[0] += int(c[1:3], 16)
                tot[1] += int(c[3:5], 16)
                tot[2] += int(c[5:7], 16)
            n = float(len(inked))
            rgb = (int(tot[0] / n), int(tot[1] / n), int(tot[2] / n))
            lum = af.lum(rgb)
            t = min(1.0, max(0.0, (lum - lo) / span)) ** af.GLYPH_GAMMA
            k = max(1, min(len(RAMP) - 1, int(t * len(RAMP))))
            glyphs.append(RAMP[k])
            colors.append(af.hexcol(af.quant(rgb)))
        rows.append({"g": "".join(glyphs), "c": colors})
    return {"w": ow, "h": oh, "cells": rows, "levels": piece["levels"]}


def build_set(seed):
    pieces = []
    for item in ITEMS:
        (item_id, label, category, style, box, _routine, _mats) = item
        for (size_id, size_label, scale) in SIZES:
            img, w, h, detail, circles = build_item(item, size_id, scale, seed)
            built = to_cells(img, w, h)
            rows = built["rows"]
            inked = sum(1 for r in rows for g in r["g"] if g != " ")
            colors = sorted({c for r in rows for c in r["c"] if c})
            cx, cy = w // 2, h // 2
            parts = item_id.split(".")
            pieces.append({
                "id": "%s.%s" % (item_id, size_id),
                "kind": "item",
                "slot": "icone",
                "label": label,
                "category": parts[0],
                "species": parts[1],
                "family": ".".join(parts[:2]),
                "style": style,
                "aspect": ASPECT.get(item_id),
                "size": size_id,
                "size_label": size_label,
                "box": [w, h],
                "detail": detail,
                "w": w,
                "h": h,
                "anchor": {"x": cx, "y": cy},
                "frames": 1,
                "directions": 1,
                # The round geometry, declared the way the contact shadow declares its
                # ellipse: what is round on screen cannot be checked in a cell grid, so
                # it is checked here (see the audit's screen-circle check).
                "circles": circles,
                "levels": built["levels"],
                "cells": rows,
                "stats": {"inkedCells": inked, "cellCount": w * h,
                          "colors": len(colors)},
            })
    return pieces


def write_json(pieces, seed):
    payload = {
        "version": 1,
        "generator": "weapons %s (artforge %s)" % (VERSION, af.VERSION),
        "set": "weapons",
        "label": "Armas e armaduras",
        "kind": "item",
        "slot": "icone",
        "kinds": ["item"],
        "seed": seed,
        "cell": {"w": af.CELL_W, "h": af.CELL_H, "aspect": round(af.CELL_ASPECT, 4)},
        "sizes": [{"id": s, "label": l, "scale": k} for (s, l, k) in SIZES],
        "ramp": RAMP,
        "glyphGamma": af.GLYPH_GAMMA,
        "quant": af.QUANT,
        "pieces": pieces,
    }
    os.makedirs(ASSETS, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    return payload


# --- the page -------------------------------------------------------------------
PAGE_HEAD = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>artforge — armas e armaduras</title>
<style>
  :root {
    --panelw: min(1240px, calc(100vw - 40px));
    --fs: __FS__px;
    --bg: #05070a; --panel: #0b0f14; --line: #1c2430; --slot: #171c24;
    --ink: #e9e5d8; --dim: #8b8f92; --accent: #cfa855;
    --mono: "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  }
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
  .cap { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline; padding: 9px 14px;
         border-bottom: 1px solid var(--line); font-size: 11.5px; color: var(--dim); }
  .cap b { color: var(--accent); font-weight: 600; }
  .arts { display: flex; flex-wrap: wrap; gap: 18px; padding: 12px 14px 14px; align-items: flex-end; }
  .pane { }
  .pane .name { color: var(--dim); font-size: 10.5px; margin-bottom: 4px; }
  pre { margin: 0; font-family: var(--mono); font-size: var(--fs); line-height: 1;
        white-space: pre; font-variant-ligatures: none; -webkit-font-smoothing: antialiased; }
  pre i { font-style: normal; }
  .gridbox { padding: 14px; overflow-x: auto; }
  .slots { border: 1px solid var(--line); border-radius: 8px; padding: 6px; background: #0e1219; }
  footer { color: var(--dim); font-size: 11.5px; border-top: 1px solid var(--line); padding-top: 12px; margin-top: 18px; }
  code { color: var(--accent); }
  table { border-collapse: collapse; font-size: 11.5px; margin-top: 8px; }
  th, td { border: 1px solid var(--line); padding: 3px 9px; text-align: right; color: var(--dim); }
  th { color: var(--ink); font-weight: 600; }
  td.id { text-align: left; color: var(--ink); }
  .bar { display: flex; flex-wrap: wrap; gap: 7px; margin: 0 0 10px; }
  button.f { font: inherit; font-size: 11.5px; color: var(--ink); background: #101721;
             border: 1px solid var(--line); border-radius: 6px; padding: 4px 10px; cursor: pointer; }
  button.f[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
</style></head><body><div class="wrap">
<h1>artforge — armas e armaduras</h1>
<p class="lede">__LEDE__</p>
<h2>Os ícones no tamanho de jogo</h2>
<p class="lede">__SLOTNOTE__</p>
__SHOWCASE__
<h2>As três resoluções</h2>
<p class="lede">__RATENOTE__</p>
__CARDS__
<h2>Reduzir em tempo real</h2>
<p class="lede">__SHRINKNOTE__</p>
__SHRINK__
<h2>O algoritmo, ao vivo</h2>
<p class="lede">__LIVENOTE__</p>
<div class="bar" id="liveItems"></div>
<div class="bar" id="liveFactors"></div>
<div class="card"><div class="gridbox"><div class="slots"><pre id="liveOut"></pre></div></div></div>
<p class="lede" id="liveInfo"></p>
<footer>__FOOTER__</footer>
</div>
<script id="labdata" type="application/json">__LABDATA__</script>
<script>
__SHRINKJS__
mountShrinkLab(JSON.parse(document.getElementById("labdata").textContent));
</script>
</body></html>
"""


def panel_html(cells):
    body, inked = af.run_length_html(cells)
    return body, inked


def build_showcase(pieces, by_id):
    """Every item at its small size, in a flat row per category -- no slots, no grid.

    Dropping the slot inventory leaves no footprint for the small size to answer to,
    and leaves one question the page has to answer: does this read at the size the
    game will draw it? The rows share a vertical CENTRE, which is where an icon lives
    (it has no ground to stand on).
    """
    cats = [("weapon", "armas"), ("armor", "armaduras e escudos"), ("jewelry", "adornos")]
    out = []
    for (cat, cat_label) in cats:
        group = [p for p in pieces if p["category"] == cat and p["size"] == "small"]
        if not group:
            continue
        colw = max(p["w"] for p in group) + 4
        rowh = max(p["h"] for p in group)
        width, height = colw * len(group), rowh + 3
        canvas = [[" "] * width for _ in range(height)]
        colors = [[""] * width for _ in range(height)]
        for i, piece in enumerate(group):
            ox = i * colw + (colw - piece["w"]) // 2
            oy = (rowh - piece["h"]) // 2
            for y, row in enumerate(piece["cells"]):
                for x in range(piece["w"]):
                    if row["g"][x] == " ":
                        continue
                    canvas[oy + y][ox + x] = row["g"][x]
                    colors[oy + y][ox + x] = row["c"][x]
        for i, piece in enumerate(group):
            text = piece["label"][:colw - 2]
            start = i * colw + max(0, (colw - len(text)) // 2)
            for k, ch in enumerate(text):
                canvas[rowh + 1][start + k] = ch
                colors[rowh + 1][start + k] = "#8b8f92"
        rows_out = [{"g": "".join(r), "c": colors[y]} for y, r in enumerate(canvas)]
        body, _inked = panel_html(rows_out)
        out.append('<div class="card"><div class="cap"><span><b>%s</b></span>'
                   '<span>%d itens no tamanho pequeno · mesma escala de fonte</span></div>'
                   '<div class="gridbox"><pre>%s</pre></div></div>'
                   % (cat_label, len(group), body))
    return "\n".join(out)


def build_html(payload, pieces):
    by_id = {p["id"]: p for p in pieces}
    fams = []
    for item in ITEMS:
        item_id = item[0]
        group = [by_id["%s.%s" % (item_id, s)] for (s, _l, _k) in SIZES
                 if "%s.%s" % (item_id, s) in by_id]
        if group:
            fams.append((item_id, item[1], group))

    widest = max(sum(p["w"] for p in g) + 8 * (len(g) - 1) for _i, _l, g in fams)
    fs = max(5.0, min(15.0, (1240 * 0.90) / (widest * 0.62)))

    showcase = build_showcase(pieces, by_id)
    lede = ("<b>%d itens</b> — %d armas e %d peças de armadura/adorno — cada um em <b>três resoluções</b> "
            "(pequena, média, grande), semente <b>%d</b>. Um item não tem pé no chão: ele é "
            "<b>centralizado</b>, então a âncora é o centro da caixa e o que tem de sobreviver é a "
            "<b>silhueta</b>."
            % (len(fams), sum(1 for f in fams if f[0].startswith("weapon")),
               sum(1 for f in fams if not f[0].startswith("weapon")), payload["seed"]))
    slotnote = ("Não há grade de slots: o tamanho pequeno <b>não responde a footprint nenhum</b>, "
                "responde à legibilidade — a caixa tem de caber o traço que faz o item ser o que é "
                "(na espada a guarda, no elmo a fenda da viseira). Foi isso que consertou as duas "
                "peças que o slot apertava. Cada peça diz suas dimensões em células; a âncora é o "
                "centro.")
    ratenote = ("As três na <b>mesma escala de fonte</b>: a grande é literalmente o dobro da pequena. "
                "A cadeia é 1× / 1,5× / 2× de propósito — assim a grande reduzida por 2 cai "
                "<b>exatamente</b> na grade da pequena, e as duas podem ser comparadas célula a célula.")
    shrinknote = ("O mesmo item, duas vezes na grade da pequena: à esquerda a pequena <b>desenhada</b>, "
                  "à direita a grande <b>reduzida em tempo real</b> (média de blocos 2×2, o mesmo "
                  "<code>shrink</code> do Python rodando no navegador). A tabela abaixo mede as duas.")
    livenote = ("O algoritmo ao vivo, no navegador: escolha o item e o fator. É o "
                "<code>tools/shrink.js</code> embutido na página (a página é um arquivo só, sem "
                "dependência), e ele decide glifo e cor com as <b>mesmas regras do Python</b> — "
                "inclusive gama e quantização — para os dois lados darem a mesma grade.")
    footer = ("Gerado por <code>weapons.py</code> · conjunto em <code>assets/weapons.json</code> · "
              "peças em <code>bank.py ingest assets/weapons.json</code>")

    cards = []
    for (item_id, label, group) in fams:
        panes = []
        caps = []
        for p in group:
            body, inked = panel_html(p["cells"])
            panes.append('<div class="pane"><div class="name">%s · %d×%d · âncora %d,%d</div>'
                         '<pre>%s</pre></div>' % (p["size_label"], p["w"], p["h"],
                                                  p["anchor"]["x"], p["anchor"]["y"], body))
            caps.append("%s %d×%d" % (p["size_label"], p["w"], p["h"]))
        cards.append('<section class="card" id="%s">\n  <div class="cap"><span><b>%s</b> · %s</span>'
                     '<span>%s</span><span>%s</span></div>\n'
                     '  <div class="arts">%s</div>\n</section>'
                     % (item_id.replace(".", "-"), label, item_id,
                        group[0]["category"] + (" · " + group[0]["style"]
                                                if group[0].get("style") else ""),
                        " · ".join(caps), "".join(panes)))

    shrink_rows = []
    table = ['<table><tr><th>item</th><th>pequena desenhada</th><th>grande reduzida ÷2</th>'
             '<th>tinta p.</th><th>tinta red.</th><th>perda</th></tr>']
    for (item_id, label, group) in fams:
        small = next(p for p in group if p["size"] == "small")
        large = next(p for p in group if p["size"] == "large")
        shrunk = shrink(large, 2)
        body_s, inked_s = panel_html(small["cells"])
        body_z, inked_z = panel_html(shrunk["cells"])
        shrink_rows.append(
            '<section class="card" id="shrink-%s">\n  <div class="cap"><span><b>%s</b> · %s</span>'
            '<span>mesma grade: %d×%d</span></div>\n'
            '  <div class="arts">'
            '<div class="pane"><div class="name">desenhada pequena · %d células de tinta</div>'
            '<pre>%s</pre></div>'
            '<div class="pane"><div class="name">grande reduzida ÷2 · %d células de tinta</div>'
            '<pre>%s</pre></div></div>\n</section>'
            % (item_id.replace(".", "-"), label, item_id, small["w"], small["h"],
               inked_s, body_s, inked_z, body_z))
        table.append('<tr><td class="id">%s</td><td>%d</td><td>%d</td><td>%d%%</td><td>%d%%</td>'
                     '<td>%+.0f%%</td></tr>'
                     % (item_id, inked_s, inked_z,
                        100.0 * inked_s / (small["w"] * small["h"]),
                        100.0 * inked_z / (shrunk["w"] * shrunk["h"]),
                        100.0 * (inked_z - inked_s) / max(1, inked_s)))
    table.append("</table>")

    # The live lab needs the large pieces and the same constants the generator used,
    # so the browser and Python cannot drift: same ramp, same gamma, same quantiser.
    lab = {"ramp": RAMP, "gamma": af.GLYPH_GAMMA, "quant": af.QUANT,
           "pieces": [{"id": p["id"], "label": p["label"], "w": p["w"], "h": p["h"],
                       "levels": p["levels"], "cells": p["cells"]}
                      for p in pieces if p["size"] == "large"]}
    with open(os.path.join(HERE, "tools", "shrink.js"), encoding="utf-8") as fh:
        shrink_js = fh.read()

    page = PAGE_HEAD
    for marker, value in (
            ("__FS__", ("%.2f" % fs).rstrip("0").rstrip(".")),
            ("__LEDE__", lede), ("__SLOTNOTE__", slotnote), ("__SHOWCASE__", showcase),
            ("__RATENOTE__", ratenote), ("__CARDS__", "\n".join(cards)),
            ("__SHRINKNOTE__", shrinknote),
            ("__SHRINK__", "\n".join(shrink_rows) + '\n<div class="gridbox">'
             + "\n".join(table) + "</div>"),
            ("__LIVENOTE__", livenote), ("__FOOTER__", footer),
            ("__LABDATA__", json.dumps(lab, ensure_ascii=False)),
            ("__SHRINKJS__", shrink_js)):
        page = page.replace(marker, value)
    for marker in ("__FS__", "__LEDE__", "__SLOTNOTE__", "__SHOWCASE__", "__RATENOTE__",
                   "__CARDS__", "__SHRINKNOTE__", "__SHRINK__", "__LIVENOTE__", "__FOOTER__",
                   "__LABDATA__", "__SHRINKJS__"):
        if marker in page:
            raise SystemExit("marker survived the build: %s" % marker)
    if "<script src" in page:
        raise SystemExit("the page must be one file: no external script")
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(page)
    return fs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    pieces = build_set(args.seed)
    payload = write_json(pieces, args.seed)
    fs = build_html(payload, pieces)
    print("weapons %s -- %d items x %d sizes = %d pieces, seed %d"
          % (VERSION, len(ITEMS), len(SIZES), len(pieces), args.seed))
    print("  json : %s (%.0f KB)" % (os.path.relpath(OUT_JSON, HERE),
                                     os.path.getsize(OUT_JSON) / 1024.0))
    print("  html : %s (%.0f KB, font %.2f px)" % (os.path.relpath(OUT_HTML, HERE),
                                                   os.path.getsize(OUT_HTML) / 1024.0, fs))
    print()
    print("  %-30s %-8s %-11s %-7s %s" % ("id", "box", "species", "ink%", "detail"))
    for p in pieces:
        s = p["stats"]
        print("  %-30s %2dx%-5d %-11s %5.0f%%  %s"
              % (p["id"], p["w"], p["h"], p["species"],
                 100.0 * s["inkedCells"] / s["cellCount"], "sim" if p["detail"] else "-"))


if __name__ == "__main__":
    main()
