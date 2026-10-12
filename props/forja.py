#!/usr/bin/env python3
"""forja -- the forge and the camp: four more scenery props, staged beside the set.

Same problem as the props already in scenery.py: a piece stands on a tile, its anchor
is the FOOT at the centre of the base, and its contact shadow is composed underneath by
the builder -- not by the routine. So everything here is authored in CELLS and the base
sits near the last row (h - 1).

The cell-space kit (cpoly, crect, cline, cellipse, circle) and the colour matrix
(scenery.GROUND) are BORROWED, never forked: one place to fix the aspect correction is
one place to be wrong once.

Three rules that cost iterations, kept here so the next piece does not pay again:

  * NO stroke thinner than 0.15 cell. A hairline is averaged away by the area sample and
    the piece arrives with a hole where the leg used to be.
  * Light on top/left (metal_light), body in the middle (metal), shade at bottom/right
    and at the joints (metal_dark). A piece in one colour reads as a stain.
  * Ink (non-empty cells / cells) between 20% and 85%. A tall narrow piece -- the
    banner -- needs the cloth to fill most of its rows or it drops under 20%.

Nothing here touches scenery.py: the four routines are staged in this file, with the
exact table the set will ingest.

Usage:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/staging/forja.py
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import artforge as af
import weapons as wk
import scenery as sc

from props.kit import cline, crect, cpoly, cellipse, circle


# --- 1. the anvil: a wide working face on a narrow waist, on a flared base ---------
def p_anvil(d, w, h):
    """Silhouette is the read: wide top, pinched waist, wide base, a horn to the right."""
    cx, base = w / 2.0, h - 0.35
    iron = sc.GROUND["iron"]
    light, body, dark = iron["metal_light"], iron["metal"], iron["metal_dark"]

    # base flange: the widest part, resting on the ground
    crect(d, cx - w * 0.40, base - 1.6, cx + w * 0.40, base, body)
    crect(d, cx - w * 0.40, base - 1.6, cx - w * 0.16, base, light)
    crect(d, cx + w * 0.20, base - 1.6, cx + w * 0.40, base, dark)
    crect(d, cx - w * 0.40, base - 0.4, cx + w * 0.40, base, dark)

    # waist: the pinched neck under the overhanging face
    top = base - 4.9
    crect(d, cx - w * 0.17, top + 1.2, cx + w * 0.17, base - 1.5, body)
    crect(d, cx - w * 0.17, top + 1.2, cx - w * 0.05, base - 1.5, light)
    crect(d, cx + w * 0.07, top + 1.2, cx + w * 0.17, base - 1.5, dark)

    # working face: overhangs the waist, lit along the top edge
    crect(d, cx - w * 0.44, top, cx + w * 0.30, top + 1.4, body)
    crect(d, cx - w * 0.44, top, cx + w * 0.30, top + 0.45, light)
    crect(d, cx - w * 0.44, top + 1.0, cx + w * 0.30, top + 1.4, dark)

    # horn: tapers off to the right, lit top / body under it
    cpoly(d, [(cx + w * 0.28, top + 0.1), (cx + w * 0.48, top + 0.6),
              (cx + w * 0.28, top + 1.2)], light)
    cpoly(d, [(cx + w * 0.28, top + 0.5), (cx + w * 0.48, top + 0.6),
              (cx + w * 0.28, top + 1.2)], body)


# --- 2. the cauldron: a wide pot, ears at the sides, three legs -------------------
def p_cauldron(d, w, h):
    """A rounded body with a lit rim ring and a dark mouth: the opening is the read."""
    cx = w / 2.0
    iron = sc.GROUND["iron"]
    light, body, dark = iron["metal_light"], iron["metal"], iron["metal_dark"]

    # three legs
    for dx in (-w * 0.22, 0.0, w * 0.22):
        crect(d, cx + dx - 0.35, h - 1.7, cx + dx + 0.35, h - 0.3, dark)
        crect(d, cx + dx - 0.35, h - 1.7, cx + dx - 0.15, h - 0.3, body)

    # the pot body, lit up-left / sunk down-right
    cellipse(d, cx, h * 0.60, w * 0.36, h * 0.29, body)
    cellipse(d, cx - w * 0.13, h * 0.50, w * 0.12, h * 0.13, light)
    cellipse(d, cx + w * 0.15, h * 0.68, w * 0.13, h * 0.11, dark)

    # ears (handles) at the sides
    for s in (-1, 1):
        cellipse(d, cx + s * w * 0.38, h * 0.45, w * 0.06, h * 0.10, dark)

    # the mouth: lit rim ring, inner wall, dark opening
    cellipse(d, cx, h * 0.31, w * 0.34, h * 0.12, light)
    cellipse(d, cx, h * 0.33, w * 0.27, h * 0.075, body)
    cellipse(d, cx, h * 0.345, w * 0.19, h * 0.05, dark)


# --- 3. the sack: a cloth bulb cinched at the neck, floppy top --------------------
def p_sack(d, w, h):
    """Bulb + tie + floppy mouth; the tie's dark band is what says 'sack'."""
    cx = w / 2.0
    cloth = sc.GROUND["cloth"]
    light, body, dark = cloth["metal_light"], cloth["metal"], cloth["metal_dark"]

    # the bulb, lit up-left / sunk down-right
    wk.circle(d, cx, h * 0.66, w * 0.35, body)
    wk.circle(d, cx - w * 0.10, h * 0.58, w * 0.15, light)
    wk.circle(d, cx + w * 0.11, h * 0.74, w * 0.12, dark)

    # two folds, so the cloth is not a flat disc
    cline(d, cx - w * 0.16, h * 0.60, cx - w * 0.06, h * 0.86, dark, 0.5)
    cline(d, cx + w * 0.07, h * 0.60, cx + w * 0.16, h * 0.84, dark, 0.5)

    # the neck, cinched
    wk.cpoly(d, [(cx - w * 0.22, h * 0.46), (cx + w * 0.22, h * 0.46),
                 (cx + w * 0.13, h * 0.28), (cx - w * 0.13, h * 0.28)], light)
    crect(d, cx - w * 0.24, h * 0.38, cx + w * 0.24, h * 0.48, dark)   # the tie

    # the floppy mouth of the cloth
    wk.cpoly(d, [(cx - w * 0.13, h * 0.30), (cx - w * 0.21, h * 0.10),
                 (cx + w * 0.19, h * 0.15), (cx + w * 0.13, h * 0.30)], body)
    wk.cpoly(d, [(cx - w * 0.13, h * 0.30), (cx - w * 0.21, h * 0.10),
                 (cx - w * 0.02, h * 0.13), (cx - w * 0.04, h * 0.30)], light)


# --- 4. the banner: a tall pole and a hanging flag --------------------------------
def p_banner(d, w, h):
    """A banner hanging from its rod, CENTRED.

    The first version drew the pole at the left with the flag to one side: a correct piece
    with the wrong foot -- the ink sat two cells left of the anchor, and the rule is that
    the mass stands over the foot. The mass is the cloth, so the cloth goes over the anchor
    and the rod spans it.
    """
    cloth, wood, iron = sc.GROUND["cloth"], sc.GROUND["wood"], sc.GROUND["iron"]
    lightc, bodyc, darkc = cloth["metal_light"], cloth["metal"], cloth["metal_dark"]
    mid = w / 2.0
    ry = 1.2

    # the rod, spanning the cloth, ends capped in iron
    crect(d, w * 0.14, ry - 0.5, w * 0.86, ry + 0.5, wood["metal"])
    crect(d, w * 0.14, ry - 0.5, w * 0.86, ry - 0.1, wood["metal_light"])
    circle(d, w * 0.14, ry, 0.6, iron["metal_light"])
    circle(d, w * 0.86, ry, 0.6, iron["metal_light"])

    # the cloth: a swallowtail, centred on the anchor, reaching the ground
    fx0, fx1 = w * 0.24, w * 0.76
    fy0, fy1 = ry + 0.8, h - 0.6
    cpoly(d, [(fx0, fy0), (fx1, fy0), (fx1, fy1), (mid, fy1 - 1.6), (fx0, fy1)], bodyc)
    crect(d, fx0, fy0, fx0 + w * 0.09, fy1, lightc)
    crect(d, fx1 - w * 0.09, fy0, fx1, fy1, darkc)

    # folds down the cloth
    for k in (0.34, 0.64):
        x = fx0 + (fx1 - fx0) * k
        cline(d, x, fy0 + 0.8, x - 0.3, fy1 - 1.4, darkc, 0.5)

    # emblem: a cross, so the banner is not a plain rectangle
    crect(d, mid - 0.6, fy0 + 2.0, mid + 0.6, fy0 + 6.4, iron["metal"])
    crect(d, mid - 0.6, fy0 + 2.0, mid + 0.6, fy0 + 3.0, iron["metal_light"])
    crect(d, fx0 + 0.8, fy0 + 3.7, fx1 - 0.8, fy0 + 4.7, iron["metal"])


# --- the table the set ingests ----------------------------------------------------
NEW_PROPS = [
    ("prop.anvil", "Bigorna", "anvil", (10, 7), p_anvil, 3.4, "iron", "rock"),
    ("prop.cauldron", "Caldeirão", "cauldron", (10, 8), p_cauldron, 3.4, "iron", "dirt"),
    ("prop.sack", "Saco", "sack", (8, 7), p_sack, 2.8, "cloth", "dirt"),
    ("prop.banner", "Estandarte", "banner", (8, 14), p_banner, 2.4, "cloth", "stone"),
]


def build(pid, label, sp, box, routine, shr, mat, foot):
    """One staged piece, built the same way the set will: routine, then the contact
    patch at the foot, then sample to cells."""
    w_cells, h_cells = box
    img = Image.new("RGB", (int(round(w_cells * af.UX)), int(round(h_cells * af.UY))),
                    (0, 0, 0))
    d = ImageDraw.Draw(img)
    routine(d, w_cells, h_cells)
    wk.crect(d, w_cells * 0.34, h_cells - 0.75, w_cells * 0.66, h_cells - 0.05,
             sc.GROUND[foot]["metal_dark"])
    return wk.to_cells(img, w_cells, h_cells)


def main():
    for (pid, label, sp, (w, h), routine, shr, mat, foot) in NEW_PROPS:
        built = build(pid, label, sp, (w, h), routine, shr, mat, foot)
        rows = built["rows"]
        ink = sum(1 for r in rows for ch in r["g"] if ch != " ")
        bottom = [i for i, ch in enumerate(rows[h - 1]["g"]) if ch != " "]
        print("%s  tinta %.0f%%  chao: %s" % (pid, 100.0 * ink / (w * h),
                                              "ok" if bottom else "VAZIO"))
        for r in rows:
            print("|%s|" % r["g"])
        print()


if __name__ == "__main__":
    main()
