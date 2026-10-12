#!/usr/bin/env python3
"""scenery_audit -- the checks that measure the scenery set, in the browser and in the
pixels. Same rule as the other audits: a claim that is not measured does not enter as a
check, and a check that cannot fail is not a check.

    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/scenery_audit.py
"""

import inspect
import json
import math
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
    SLOTS = {"piso", "bloco", "prop", "ator", "mancha"}
    check("the set has the slots the engine draws, actor included",
          {p["slot"] for p in pieces} == SLOTS,
          "slots: %s" % ", ".join(sorted({p["slot"] for p in pieces})))
    counts = {s: sum(1 for p in pieces if p["slot"] == s) for s in sorted(SLOTS)}
    check("at least %d pieces, at least 3 per slot" % 40,
          len(pieces) >= 40 and min(counts.values()) >= 3,
          " ".join("%s %d" % (k, v) for k, v in counts.items()))
    check("the tile is the test project's resolution: 20x6 with a wall of 8",
          (sc.TILE_W, sc.TILE_H, sc.WALL_ROWS) == (20, 6, 8),
          "%dx%d, parede %d (cripta: tileCellsW 20, tileCellsH 6, wallHeightCells 8)"
          % (sc.TILE_W, sc.TILE_H, sc.WALL_ROWS))

    # --- what the file DECLARES for whoever consumes it --------------------------
    # Two numbers the consumer would otherwise have to guess, and both are wrong by default
    # in the engine: the ink transform (the engine's art boosts, this set is already
    # boosted) and the culling margin (the engine's fallback is 3 tiles, this set needs 6).
    ink = data.get("ink") or {}
    defaults = inspect.signature(af.boost).parameters
    check("the file declares the ink transform, so a consumer cannot boost twice",
          ink.get("boosted") is True and
          all(ink.get(k) == defaults[k].default for k in ("sat", "gain", "lift")) and
          ink.get("quant") == af.QUANT,
          "boosted sim, sat %s gain %s lift %s quant %s (os do artforge.boost)"
          % (ink.get("sat"), ink.get("gain"), ink.get("lift"), ink.get("quant")))
    tallest = max(p["anchor"]["y"] for p in pieces if p["slot"] in ("prop", "ator"))
    want_margin = int(math.ceil(tallest / float(sc.TILE_H))) + 1
    check("the file declares the culling margin the engine needs",
          data.get("requiredMarginTiles") == want_margin and want_margin > 3,
          "%s tiles: a peça mais alta sobe %d células = %.1f tiles, e o fallback do motor "
          "com os padrões dele é 3" % (data.get("requiredMarginTiles"), tallest,
                                       tallest / float(sc.TILE_H)))
    check("the file declares the kinds it actually ships",
          set(data.get("kinds") or []) == {p["kind"] for p in pieces},
          "declara %s, traz %s" % (data.get("kinds"), sorted({p["kind"] for p in pieces})))

    outs, err = fresh()
    check("two fresh runs give the same bytes", outs is not None and outs[0] == outs[1],
          err or "%d bytes" % (len(outs[0]) if outs else 0))

    with open(TREES, encoding="utf-8") as fh:
        tree_ids = {p["id"] for p in json.load(fh)["pieces"]}
    own = {p["id"] for p in pieces}
    bad = [p["id"] for p in pieces
           if p.get("shadow") and p["shadow"] not in tree_ids and p["shadow"] not in own]
    borrowed = sum(1 for p in pieces if p.get("shadow") in tree_ids)
    check("every contact shadow resolves, borrowed from the tree set or made here",
          not bad, ", ".join(bad) or "%d emprestadas, %d feitas aqui"
          % (borrowed, sum(1 for p in pieces if p.get("shadow") in own)))
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
    check("every floor is the tile grid, %dx%d = 2:1 on screen" % (sc.TILE_W, sc.TILE_H),
          grids == {(sc.TILE_W, sc.TILE_H)}, "grids: %s" % grids)
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
        core = [extent(k) for k in range(sc.TILE_H, h - 2)]
        # A cube, not a wall painted flat: the top FACE is a rhombus, so its widest row is
        # in the middle of the face (never at an end), and the wall rows below it are
        # straight (one width) and full. The last two rows are the bottom V -- the cube's
        # front corner coming to a point -- and are left out for that reason.
        ok.append(max(top) > 0 and top.index(max(top)) not in (0, len(top) - 1)
                  and len(set(core)) == 1 and core[0] >= 0.9 * w)
    check("every block narrows at the top: it is a cube, not a wall painted flat",
          all(ok), "%d/%d" % (sum(ok), len(blocks)))
    rows = {p["h"] for p in blocks}
    check("every block is the tile's height plus the wall height",
          rows == {sc.TILE_H + sc.WALL_ROWS},
          "alturas: %s (esperado %d)" % (sorted(rows), sc.TILE_H + sc.WALL_ROWS))

    # --- the prop stands on its tile --------------------------------------------
    # props AND actors: the same rule, because the engine places both by the anchor
    standing = [p for p in pieces if p["slot"] in ("prop", "ator")]
    feet = []
    for p in standing:
        anchor_row = p["anchor"]["y"]
        inked = [i for i, ch in enumerate(p["cells"][anchor_row]["g"]) if ch != " "]
        feet.append(bool(inked) and abs((min(inked) + max(inked)) / 2.0 -
                                        p["anchor"]["x"]) <= 1.5)
    check("every prop and actor touches the ground on its own anchor", all(feet),
          "%d/%d" % (sum(feet), len(standing)))
    ink = [100.0 * p["stats"]["inkedCells"] / p["stats"]["cellCount"] for p in standing]
    check("props and actors sit between 19.5% and 85% ink",
          all(19.5 <= v <= 85 for v in ink),
          "min %.1f%% max %.1f%%" % (min(ink), max(ink)))

    # --- the actor is the size the game draws it --------------------------------
    actors = [p for p in pieces if p["slot"] == "ator"]
    check("the set has the player and something to fight", len(actors) >= 3,
          ", ".join(p["id"] for p in actors))
    hero = next((p for p in actors if p["id"].endswith("heroi")), None)
    rows_with_ink = 0
    if hero:
        rows_with_ink = sum(1 for r in hero["cells"] if r["g"].strip())
    check("the hero is the cripta's size, ~12 cells tall",
          hero is not None and 11 <= rows_with_ink <= 15,
          "herói com %d linhas de tinta (a cripta desenha A(6) com A()=2)" % rows_with_ink)
    check("every actor declares the two facings the engine flips between",
          all(p.get("facing") == [1, -1] for p in actors),
          "%d atores" % len(actors))

    # --- the decal is drawn with the floor --------------------------------------
    decals = [p for p in pieces if p["slot"] == "mancha" and p.get("tile")]
    discs = [p for p in pieces if p["slot"] == "mancha" and p.get("disc")]
    check("every floor decal declares the ground layer and the tile grid",
          all(p.get("layer") == "ground" and tuple(p["tile"]) == (sc.TILE_W, sc.TILE_H)
              for p in decals),
          "%d manchas de piso" % len(decals))
    check("every contact shadow is a 2:1 disc with its centre as the anchor",
          all(p["anchor"]["x"] == p["w"] // 2 and
              abs(p["disc"]["ry"] - p["disc"]["rx"] * af.CELL_W / (2.0 * af.CELL_H)) < 0.02
              for p in discs),
          "%d discos próprios (o conjunto das árvores não tinha deste raio)"
          % len(discs))

    # --- the scene composes ------------------------------------------------------
    for name in ("externo", "cripta"):
        scene, placed = sc.compose_scene(by_id, name)
        canvas, colors, _placed = sc.scene_cells(by_id, name)
        body = re.sub(r"<i[^>]*>|</i>", "", scene)
        for (ent, ch) in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&quot;", '"')):
            body = body.replace(ent, ch)
        lines = body.split("\n")
        width = max(len(l) for l in lines)
        inked = sum(1 for r in canvas for ch in r if ch != " ")
        check("the %s scene has no ragged right edge" % name,
              all(len(l) == width or len(l.rstrip()) == len(l) for l in lines),
              "%dx%d células" % (width, len(lines)))
        check("the %s scene is mostly ground, not holes" % name,
              inked / float(width * len(lines)) > 0.30,
              "%.0f%% de tinta" % (100.0 * inked / (width * len(lines))))
        # Every prop and actor planted: the composed cell at its anchor must be the cell
        # the piece itself has at its anchor -- OR the cell of a piece drawn LATER whose
        # box covers that point. The engine draws by depth, so props overlap; treating a
        # legitimate overlap as a defect is how a check stops meaning anything.
        boxes = []
        for (pid, x, y) in placed:
            piece = by_id[pid]
            xs = [i for row in piece["cells"] for i, ch in enumerate(row["g"]) if ch != " "]
            ys = [k for k, row in enumerate(piece["cells"]) if row["g"].strip()]
            if not xs or not ys:
                boxes.append(None)
                continue
            boxes.append((x - piece["anchor"]["x"] + min(xs),
                          x - piece["anchor"]["x"] + max(xs),
                          y - piece["anchor"]["y"] + min(ys),
                          y - piece["anchor"]["y"] + max(ys)))

        def covered_later(idx, cx, cy):
            for k in range(idx + 1, len(placed)):
                b = boxes[k]
                if b and b[0] <= cx <= b[1] and b[2] <= cy <= b[3]:
                    return placed[k][0]
            return None

        broken, hidden = [], 0
        for idx, (pid, x, y) in enumerate(placed):
            if not pid.startswith(("prop.", "ator.")):
                continue
            piece = by_id[pid]
            ax, ay = piece["anchor"]["x"], piece["anchor"]["y"]
            want = piece["cells"][ay]["g"][ax]
            got = canvas[y][x]
            if want == " " or got == want:
                continue
            if covered_later(idx, x, y):
                hidden += 1
            else:
                broken.append("%s@%d,%d %r!=%r" % (pid, x, y, got, want))
        n = len([t for t in placed if t[0].startswith(("prop.", "ator."))])
        check("every prop and actor holds its own anchor in the %s scene" % name,
              not broken, ", ".join(broken[:4]) or
              "%d peças plantadas, %d com a âncora coberta por peça posterior" % (n, hidden))

    # --- the page -----------------------------------------------------------------
    with open(HTML_PATH, encoding="utf-8") as fh:
        html = fh.read()
    check("the page carries no <script>: it is static", "<script" not in html.lower(),
          "%.0f KB" % (len(html) / 1024.0))
    check("no build marker survived", not re.search(r"__[A-Z]+__", html), "")
    check("the page shows the two scenes and the nine floors repeated",
          html.count('class="stage"') >= 11,
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
    check("all the pieces are in the bank index", len(ent) == len(pieces),
          "%d/%d" % (len(ent), len(pieces)))
    slots = {}
    for e in ent:
        slots.setdefault(e["slot"], 0)
        slots[e["slot"]] += 1
    check("the bank files them under the right slots, actor included",
          all(slots.get(s) == counts[s] for s in ("piso", "bloco", "prop", "ator")),
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
