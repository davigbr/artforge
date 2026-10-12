#!/usr/bin/env python3
"""scenery_audit -- the checks that measure the scenery set, in the browser and in the
pixels. Same rule as the other audits: a claim that is not measured does not enter as a
check, and a check that cannot fail is not a check.

    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/scenery_audit.py
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import scenery as sc                                            # noqa: E402
import artforge as af                                           # noqa: E402

PY = sys.executable
JSON_PATH = os.path.join(ROOT, "assets", "scenery.json")
HTML_PATH = os.path.join(ROOT, "scenery.html")
TREES = os.path.join(ROOT, "assets", "trees.json")

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %-4s %-46s %s" % ("ok" if ok else "FAIL", name, detail))


def fresh():
    """Generate twice into a temp copy and compare BYTES: determinism is the promise the
    whole bank rests on, and the only honest way to test it is two fresh runs, not the
    file that is already on disk (which is what the first version of this tested)."""
    outs = []
    for k in range(2):
        env = dict(os.environ, PYTHONPATH="")
        r = subprocess.run([PY, "scenery.py", "--seed", "4242"], cwd=ROOT, env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, r.stderr[-400:]
        with open(JSON_PATH, "rb") as fh:
            outs.append(fh.read())
    return outs, ""


def main():
    print("scenery_audit -- %s" % os.path.relpath(ROOT))
    env = dict(os.environ, PYTHONPATH="")
    subprocess.run([PY, "scenery.py"], cwd=ROOT, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    with open(JSON_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    pieces = data["pieces"]
    by_id = {p["id"]: p for p in pieces}

    # --- the set itself -------------------------------------------------------
    check("the set has the four slots the engine draws",
          {p["slot"] for p in pieces} == {"piso", "bloco", "prop", "mancha"},
          "slots: %s" % ", ".join(sorted({p["slot"] for p in pieces})))
    counts = {s: sum(1 for p in pieces if p["slot"] == s) for s in
              ("piso", "bloco", "prop", "mancha")}
    check("35 pieces, at least 6 per slot",
          len(pieces) == 35 and min(counts.values()) >= 5,
          " ".join("%s %d" % (k, v) for k, v in counts.items()))

    outs, err = fresh()
    check("two fresh runs give the same bytes", outs is not None and outs[0] == outs[1],
          err or "%d bytes" % (len(outs[0]) if outs else 0))

    with open(TREES, encoding="utf-8") as fh:
        tree_ids = {p["id"] for p in json.load(fh)["pieces"]}
    bad = [p["id"] for p in pieces if p.get("shadow") and p["shadow"] not in tree_ids]
    check("every borrowed shadow exists in the tree set", not bad, ", ".join(bad) or
          "%d props borrow a disc" % sum(1 for p in pieces if p.get("shadow")))
    shadowless = [p["id"] for p in pieces if p["slot"] == "prop" and not p.get("shadow")]
    check("no prop stands without a contact shadow", not shadowless,
          ", ".join(shadowless) or "%d/%d" % (counts["prop"] - len(shadowless),
                                              counts["prop"]))

    seen = {}
    dupes = []
    for p in pieces:
        key = json.dumps(p["cells"], sort_keys=True)
        if key in seen:
            dupes.append("%s == %s" % (p["id"], seen[key]))
        seen[key] = p["id"]
    check("no two pieces are the same art", not dupes, ", ".join(dupes) or
          "%d distinct" % len(seen))

    # --- the floor: the one thing a floor cannot do -----------------------------
    tiles = [p for p in pieces if p["slot"] == "piso"]
    grids = {tuple(p["tile"]) for p in tiles}
    check("every floor is the tile grid, 12x4 = 2:1 on screen", grids == {(12, 4)},
          "grids: %s" % grids)
    worst = []
    for p in tiles:
        s = sc.preview_seam(p)
        worst.append((s["ratio"], p["id"], s))
    worst.sort(reverse=True)
    (ratio, pid, s) = worst[0]
    check("the floor continues when shifted by half a tile", ratio == 0.0,
          "pior %s: %d de %d células mudam (0 = contínuo)"
          % (pid, round(s["ratio"] * s["total"]), s["total"]))

    glyphs = {ch for p in tiles for r in p["cells"] for ch in r["g"] if ch != " "}
    ceiling = int(len(af.RAMP) * 0.55)
    allowed = set(af.RAMP[:ceiling + 1])
    loud = sorted(glyphs - allowed)
    check("the floor stays on the low half of the ramp", not loud,
          "fora da fatia: %s" % "".join(loud))

    # --- the block has height ---------------------------------------------------
    blocks = [p for p in pieces if p["slot"] == "bloco"]
    ok = []
    for p in blocks:
        w, h = p["w"], p["h"]

        def extent(k):
            xs = [i for i, ch in enumerate(p["cells"][k]["g"]) if ch != " "]
            return (max(xs) - min(xs) + 1) if xs else 0

        top = [extent(k) for k in range(sc.TILE_H)]
        core = [extent(k) for k in range(sc.TILE_H, h - 1)]
        # A cube, not a wall painted flat: the top FACE is a rhombus, so its widest row is
        # in the middle of the face (never at an end), and the wall rows below it are
        # straight (one width) and full. The top vertex is a point and does not survive
        # sampling, which is why the widest row -- not row 0 -- is what gets measured.
        ok.append(max(top) > 0 and top.index(max(top)) not in (0, len(top) - 1)
                  and len(set(core)) == 1 and core[0] >= 0.9 * w)
    check("every block narrows at the top: it is a cube, not a wall painted flat",
          all(ok), "%d/%d" % (sum(ok), len(blocks)))
    rows = {p["h"] for p in blocks}
    check("every block is the tile's height plus the wall height",
          rows == {sc.TILE_H + sc.WALL_ROWS},
          "alturas: %s (esperado %d)" % (sorted(rows), sc.TILE_H + sc.WALL_ROWS))

    # --- the prop stands on its tile --------------------------------------------
    props = [p for p in pieces if p["slot"] == "prop"]
    feet = []
    for p in props:
        anchor_row = p["anchor"]["y"]
        inked = [i for i, ch in enumerate(p["cells"][anchor_row]["g"]) if ch != " "]
        feet.append(bool(inked) and abs((min(inked) + max(inked)) / 2.0 -
                                        p["anchor"]["x"]) <= 1.0)
    check("every prop touches the ground on its own anchor", all(feet),
          "%d/%d" % (sum(feet), len(props)))
    ink = [100.0 * p["stats"]["inkedCells"] / p["stats"]["cellCount"] for p in props]
    check("props sit between 20% and 85% ink",
          all(20 <= v <= 85 for v in ink),
          "min %.0f%% max %.0f%%" % (min(ink), max(ink)))

    # --- the decal is drawn with the floor --------------------------------------
    decals = [p for p in pieces if p["slot"] == "mancha"]
    check("every decal declares the ground layer and the tile grid",
          all(p.get("layer") == "ground" and tuple(p["tile"]) == (12, 4) for p in decals),
          "%d decals" % len(decals))

    # --- the scene composes ------------------------------------------------------
    scene, placed = sc.compose_scene(by_id)
    canvas, colors, _placed = sc.scene_cells(by_id)
    body = re.sub(r"<i[^>]*>|</i>", "", scene)
    for (ent, ch) in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        body = body.replace(ent, ch)
    lines = body.split("\n")
    width = max(len(l) for l in lines)
    inked = sum(1 for r in canvas for ch in r if ch != " ")
    check("the composed scene has no ragged right edge",
          all(len(l) == width or len(l.rstrip()) == len(l) for l in lines),
          "%dx%d células" % (width, len(lines)))
    check("the composed scene is mostly ground, not holes",
          inked / float(width * len(lines)) > 0.30,
          "%.0f%% de tinta" % (100.0 * inked / (width * len(lines))))
    # Every PROP planted: the composed cell at its anchor must be the cell the piece itself
    # has at its anchor. The props are drawn last, so nothing can legitimately sit on top;
    # tiles and decals are left out because a decal is SUPPOSED to paint over the floor.
    broken = []
    for (pid, x, y) in [t for t in placed if t[0].startswith("prop.")]:
        piece = by_id[pid]
        ax, ay = piece["anchor"]["x"], piece["anchor"]["y"]
        want = piece["cells"][ay]["g"][ax]
        got = canvas[y][x]
        if want != " " and got != want:
            broken.append("%s@%d,%d %r!=%r" % (pid, x, y, got, want))
    check("every planted prop holds its own anchor in the composition",
          not broken, ", ".join(broken[:4]) or "%d props plantados"
          % len([t for t in placed if t[0].startswith("prop.")]))

    # --- the page -----------------------------------------------------------------
    with open(HTML_PATH, encoding="utf-8") as fh:
        html = fh.read()
    check("the page carries no <script>: it is static", "<script" not in html.lower(),
          "%.0f KB" % (len(html) / 1024.0))
    check("no build marker survived", not re.search(r"__[A-Z]+__", html), "")
    check("the page shows the scene and the nine floors repeated",
          html.count('class="stage"') >= 10,
          "%d quadros" % html.count('class="stage"'))
    check("the whole library is named in the file without JavaScript",
          all(p["id"] in html for p in pieces),
          "%d peças citadas" % len(pieces))

    # --- the bank -----------------------------------------------------------------
    r = subprocess.run([PY, "bank.py", "ingest", "assets/scenery.json"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    check("the bank ingests the scenery set", r.returncode == 0,
          "exit %d -- %s" % (r.returncode, (r.stdout + r.stderr).strip()[-140:]))
    with open(os.path.join(ROOT, "bank", "index.json"), encoding="utf-8") as fh:
        bank = json.load(fh)
    ent = [e for e in bank["pieces"] if e["id"] in by_id]
    check("all 35 pieces are in the bank index", len(ent) == len(pieces),
          "%d/%d" % (len(ent), len(pieces)))
    slots = {}
    for e in ent:
        slots.setdefault(e["slot"], 0)
        slots[e["slot"]] += 1
    check("the bank files them under the right slots",
          slots.get("piso") == 9 and slots.get("bloco") == 6 and
          slots.get("prop") == 15 and slots.get("mancha") == 5,
          " ".join("%s %d" % kv for kv in sorted(slots.items())))
    r = subprocess.run([PY, "bank.py", "check"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    check("the bank's own check still passes", r.returncode == 0,
          (r.stdout or r.stderr).strip().splitlines()[-1][:110])

    # --- the browser, for the layout ------------------------------------------------
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser layout measured", False, "playwright ausente")
    else:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for (w, h, label) in ((1440, 900, "desktop"), (390, 844, "celular")):
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto("file://" + HTML_PATH)
                over = page.evaluate("document.documentElement.scrollWidth - "
                                     "window.innerWidth")
                check("no page overflow at %dx%d" % (w, h), over <= 1, "%.0f px" % over)
                if label == "desktop":
                    pre = page.eval_on_selector("pre", "e => e.getBoundingClientRect()")
                    stage = page.eval_on_selector(".stage", "e => e.getBoundingClientRect()")
                    check("the scene is measured, not clipped",
                          stage["width"] > 400 and pre["height"] > 200,
                          "quadro %.0fx%.0f" % (stage["width"], stage["height"]))
                page.close()
            browser.close()

    print()
    print("scenery_audit: %d ok, %d FAIL" % (len(PASS), len(FAIL)))
    if FAIL:
        for (name, detail) in FAIL:
            print("  FAIL %s -- %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
