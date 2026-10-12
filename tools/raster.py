#!/usr/bin/env python3
"""raster -- the same cell grid, drawn as pixels, so a human (or a vision model) can look
at the pieces at FULL resolution. The browser page is what the project ships; this is for
looking, because a screenshot of a 160-cell-wide scene comes back as mush.

    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/raster.py
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import scenery as sc                                            # noqa: E402

FONT = "/System/Library/Fonts/Menlo.ttc"
CELL_W, CELL_H = 7.2, 12.0
BG = (12, 12, 14)
FLOOR = (26, 24, 20)


def raster(rows, colors, path, scale=2.0, background=BG):
    w = len(rows[0])
    h = len(rows)
    img = Image.new("RGB", (int(w * CELL_W * scale), int(h * CELL_H * scale)), background)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(CELL_H * scale))
    for y in range(h):
        for x in range(w):
            ch = rows[y][x]
            if ch == " ":
                continue
            d.text((x * CELL_W * scale, y * CELL_H * scale - 2 * scale), ch,
                   font=font, fill=colors[y][x] or "#888888")
    img.save(path)
    print("wrote %s (%dx%d)" % (path, img.size[0], img.size[1]))


def sheet(pieces, path, scale=2.0):
    """The pieces side by side, each on the floor tone, labels under them."""
    gap = 3
    colw = max(p["w"] for p in pieces) + gap
    rowh = max(p["h"] for p in pieces)
    rows = [[" "] * (colw * len(pieces)) for _ in range(rowh + 3)]
    colors = [[""] * (colw * len(pieces)) for _ in range(rowh + 3)]
    for k, p in enumerate(pieces):
        ox = k * colw + (colw - p["w"]) // 2
        oy = rowh - p["h"]
        for ry, row in enumerate(p["cells"]):
            for rx in range(p["w"]):
                if row["g"][rx] == " ":
                    continue
                rows[oy + ry][ox + rx] = row["g"][rx]
                colors[oy + ry][ox + rx] = row["c"][rx]
        label = p["label"]
        start = k * colw + max(0, (colw - len(label)) // 2)
        for m, ch in enumerate(label):
            rows[rowh + 1][start + m] = ch
            colors[rowh + 1][start + m] = "#cfa855"
    raster(["".join(r) for r in rows], colors, path, scale, FLOOR)


def crop(by_id, name, x0, x1, y0, y1, path, scale=2.0):
    """A window of the composed scene, at 1:1 cells: what a piece actually looks like in
    the scene it will live in."""
    canvas, colors, _placed = sc.scene_cells(by_id, name)
    rows = ["".join(r[x0:x1]) for r in canvas[y0:y1]]
    cols = [c[x0:x1] for c in colors[y0:y1]]
    raster(rows, cols, path, scale, FLOOR)


def main():
    with open(os.path.join(ROOT, "assets", "scenery.json"), encoding="utf-8") as fh:
        pieces = json.load(fh)["pieces"]
    by_id = {p["id"]: p for p in pieces}
    out = os.path.join(ROOT, "reports")
    os.makedirs(out, exist_ok=True)
    sheet([by_id[i] for i in ("ator.heroi", "ator.esqueleto", "ator.ghoul")],
          os.path.join(out, "actors.png"), 2.5)
    crop(by_id, "cripta", 20, 90, 26, 60, os.path.join(out, "crypt-left.png"), 1.6)
    crop(by_id, "cripta", 80, 150, 26, 60, os.path.join(out, "crypt-right.png"), 1.6)


if __name__ == "__main__":
    main()
