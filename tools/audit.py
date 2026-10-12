#!/usr/bin/env python3
"""artforge audit: catalogue invariants (pure JSON) + the page measured in a real
browser (DOM geometry, never a screenshot).

Section A reads assets/trees.json and checks what must hold for every piece:
  - every row has exactly w cells;
  - the ANCHOR cell is inked, so the piece actually touches the ground
    (a tree whose last row is empty would float in the game);
  - the anchor is the base centre and inside the grid;
  - the catalogue is deterministic: the same seed gives the same bytes.

Section B opens trees.html over file:// in Chromium and measures:
  - no console error, no page error;
  - the page has no horizontal overflow at 1440 and at 390 px;
  - the number of panels and the font metrics are what the generator intended;
  - inside each panel's <pre>, the three trees really stand on ONE baseline:
    read the rendered textContent (what the browser is showing, not the formula
    that produced it) and require ink in the last line under each tree's columns.

Run: PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/audit.py
"""

import json
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(HERE, "assets", "trees.json")
PAGE = os.path.join(HERE, "trees.html")
SHOT = os.path.join(HERE, "reports", "catalogue.png")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("  [%s] %-46s %s" % ("ok" if ok else "FAIL", name, detail))


def section_a():
    print("A. catalogue invariants")
    with open(JSON_PATH, encoding="utf-8") as fh:
        payload = json.load(fh)
    pieces = payload["pieces"]
    props = [p for p in pieces if p["kind"] == "prop"]
    decals = {p["id"]: p for p in pieces if p["kind"] == "decal"}
    check("catalogue shape", len(props) == 24 and 0 < len(decals) <= 24,
          "%d props + %d shared discs" % (len(props), len(decals)))
    referenced = {p.get("shadow") for p in props}
    check("every shadow id is a shared disc (no per-prop duplicate art)",
          all(i.startswith("shadow.disc.") for i in referenced) and referenced == set(decals),
          "%d distinct discs referenced by %d props" % (len(referenced), len(props)))

    bad_rows = []
    floating = []
    two_feet = []
    anchor_edges = []
    for p in props:
        for r in p["cells"]:
            if len(r["g"]) != p["w"] or len(r["c"]) != p["w"]:
                bad_rows.append(p["id"])
        last = p["cells"][-1]["g"]
        ax = p["anchor"]["x"]
        if last[ax] == " ":
            floating.append("%s (row %r)" % (p["id"], last))
        # the contact must be ONE block of cells containing the anchor: a prop
        # touching the ground in two disconnected places stands on nothing.
        runs = []
        for i, g in enumerate(last):
            if g != " ":
                if runs and runs[-1][1] == i - 1:
                    runs[-1][1] = i
                else:
                    runs.append([i, i])
        if len(runs) != 1 or not (runs[0][0] <= ax <= runs[0][1]):
            two_feet.append("%s %r runs=%s anchor=%d" % (p["id"], last, runs, ax))
        if not (0 <= ax < p["w"] and p["anchor"]["y"] == p["h"] - 1):
            anchor_edges.append(p["id"])

    check("every row has w cells", not bad_rows, ", ".join(sorted(set(bad_rows))[:4]))
    check("anchor cell inked (no floating piece)", not floating, "; ".join(floating[:4]))
    check("ground contact is one run through the anchor", not two_feet, "; ".join(two_feet[:3]))
    check("anchor is base centre, inside the grid", not anchor_edges, ", ".join(anchor_edges[:4]))

    # determinism: same seed twice, byte for byte
    first = open(JSON_PATH, "rb").read()
    subprocess.run([sys.executable, os.path.join(HERE, "artforge.py"), "--seed",
                    str(payload["seed"])], cwd=HERE, check=True,
                   stdout=subprocess.DEVNULL, env=dict(os.environ, PYTHONPATH=""))
    second = open(JSON_PATH, "rb").read()
    check("determinism (same seed -> same bytes)", first == second,
          "%d bytes, %s" % (len(first), "identical" if first == second else "DIVERGED"))

    inks = [100.0 * p["stats"]["inkedCells"] / p["stats"]["cellCount"] for p in props]
    check("no piece is mostly empty", min(inks) > 12.0,
          "min ink %.0f%% (%s), max %.0f%%" % (min(inks),
                                               props[inks.index(min(inks))]["id"], max(inks)))

    # Each species must actually carry its own palette: a wiring bug that hands
    # every species the same colours would still pass every geometry check.
    def mean_of(pid_pieces):
        tot, n = [0.0, 0.0, 0.0], 0
        for p in pid_pieces:
            for r in p["cells"]:
                for c in r["c"]:
                    if not c:
                        continue
                    tot[0] += int(c[1:3], 16)
                    tot[1] += int(c[3:5], 16)
                    tot[2] += int(c[5:7], 16)
                    n += 1
        return tuple(v / max(1, n) for v in tot)

    expect = {"oak": "g", "autumn": "r", "pine": "g", "birch": "g", "willow": "g", "bush": "g"}
    means = {}
    wrong = []
    for sid in expect:
        m = mean_of([p for p in props if p["species"] == sid])
        means[sid] = m
        dominant = "rgb"[m.index(max(m))]
        if dominant != expect[sid]:
            wrong.append("%s: dominant %s not %s" % (sid, dominant, expect[sid]))
    for sid in ("palm", "dead"):
        means[sid] = mean_of([p for p in props if p["species"] == sid])
    # palm and dead are trunk by area, so their mean is bark-brown by design;
    # what has to hold is that the foliage species differ and that the dead tree
    # stays bleached (no saturated hue anywhere in it).
    check("each foliage species carries its palette", not wrong, "; ".join(wrong[:3]))
    spread = max(means["dead"]) - min(means["dead"])
    check("dead tree is bleached wood, not green", spread <= 45,
          "mean (%d,%d,%d), channel spread %d" % (*[int(v) for v in means["dead"]], spread))
    green_cells = sum(1 for p in props if p["species"] == "palm" for r in p["cells"]
                      for i, c in enumerate(r["c"]) if c and int(c[3:5], 16) > int(c[1:3], 16) + 8)
    check("palm keeps green foliage over a bark trunk", green_cells > 5,
          "%d green-dominant cells" % green_cells)
    keys = {tuple(round(v / 8.0) for v in m) for m in means.values()}
    check("species palettes are distinct from each other", len(keys) >= 7,
          "%d distinct of %d · " % (len(keys), len(means))
          + " ".join("%s(%d,%d,%d)" % (s, *[int(v) for v in means[s]]) for s in ("oak", "autumn", "pine")))
    palettes = sorted({c for p in props for r in p["cells"] for c in r["c"] if c})
    lums = [0.2126 * int(c[1:3], 16) + 0.7152 * int(c[3:5], 16) + 0.0722 * int(c[5:7], 16)
            for c in palettes]
    lums.sort()
    p90 = lums[int(0.9 * (len(lums) - 1))]
    check("palette p90 luminance > 90 (text art loses brightness)", p90 > 90,
          "%d colours, p90 %.0f, max %.0f" % (len(palettes), p90, lums[-1]))

    # --- isometric read -------------------------------------------------------
    # The projection is the point of the set, so it has to be asserted, not just
    # intended. Three cues, each measurable in the piece itself:
    #   profile   a wide crown over a narrow trunk (round species) or a cone that
    #             widens downward (conifer) -- the WIDTH profile top to bottom;
    #   foot      the contact row is an ellipse, not a point;
    #   shadow    a disc in the ground plane, 2:1 on screen, darker than the floor.
    profile = {"oak": "wide-top", "autumn": "wide-top", "birch": "wide-top",
               "willow": "wide-top", "palm": "wide-top", "pine": "wide-base",
               "bush": "wide-base"}
    wrong_profile = []
    measured = []
    for p in props:
        want = profile.get(p["species"])
        if not want:
            continue
        widths = [sum(1 for g in r["g"] if g != " ") for r in p["cells"]]
        widest = max(range(len(widths)), key=lambda i: widths[i]) / float(len(widths))
        measured.append((p["id"], widest))
        if want == "wide-top" and widest > 0.30:
            wrong_profile.append("%s widest at %.0f%% down" % (p["id"], widest * 100))
        if want == "wide-base" and widest < 0.45:
            wrong_profile.append("%s widest at %.0f%% down" % (p["id"], widest * 100))
    worst_top = max((t for t in measured if t[0].split(".")[1] in ("oak", "birch", "willow", "palm", "autumn")),
                    key=lambda t: t[1])
    worst_base = min((t for t in measured if t[0].split(".")[1] in ("pine", "bush")), key=lambda t: t[1])
    check("iso silhouette: crown wide on top, base wide on a cone", not wrong_profile,
          "widest row: crown species at %.0f%% down, cone/shrub at %.0f%% (%d pieces)"
          % (worst_top[1] * 100, worst_base[1] * 100, len(measured)))

    narrow_foot = []
    for p in props:
        ax = p["anchor"]["x"]
        last = p["cells"][-1]["g"]
        a = ax
        while a > 0 and last[a - 1] != " ":
            a -= 1
        b = ax
        while b < p["w"] - 1 and last[b + 1] != " ":
            b += 1
        if b - a + 1 < 2:
            narrow_foot.append("%s foot %d cell" % (p["id"], b - a + 1))
    check("trunk foot is an ellipse (contact wider than 1 cell)", not narrow_foot,
          ", ".join(narrow_foot[:3]) or "24/24 with a wide contact")

    missing = [p["id"] for p in props if p.get("shadow") not in decals]
    check("every prop carries its contact shadow", not missing, ", ".join(missing[:3]))

    bad_ratio, bad_shape, bad_ink, bad_anchor, bad_glyph, box_flat = [], [], [], [], [], []
    shadow_glyphs = set("█▀▄▓▒░ ")
    # how much of a cell each glyph actually covers, so "widest row" can be
    # measured as INK MASS: with half blocks the taper happens inside the cells,
    # not across rows, and a glyph count would report a flat bar.
    weight = {"█": 1.0, "▓": 0.75, "▒": 0.5, "░": 0.25, "▄": 0.5, "▀": 0.5}
    for p in props:
        s = decals.get(p["shadow"])
        if not s:
            continue
        # The 2:1 has to be asserted on the GEOMETRY (the disc the generator drew),
        # not on the cell box: a flat disc is often less than one cell tall, and the
        # grid rounds that up to the nearest row. That rounding is exactly why the
        # shadow is drawn with half blocks instead of the mass ladder.
        screen = (s["disc"]["rx"] * payload["cell"]["w"]) / (s["disc"]["ry"] * payload["cell"]["h"])
        if not (1.9 <= screen <= 2.1):
            bad_ratio.append("%s %.2f:1" % (s["id"], screen))
        mass = [sum(weight.get(g, 0.0) for g in r["g"]) for r in s["cells"]]
        if mass.index(max(mass)) != s["anchor"]["y"]:
            bad_shape.append("%s mass %s anchor %d" % (s["id"], [round(m, 1) for m in mass],
                                                       s["anchor"]["y"]))
        if s["anchor"]["x"] != s["w"] // 2 or s["anchor"]["y"] != s["h"] // 2:
            bad_anchor.append("%s anchor %s of %dx%d" % (s["id"], s["anchor"], s["w"], s["h"]))
        used = {g for r in s["cells"] for g in r["g"]} - {" "}
        if not used <= shadow_glyphs:
            bad_glyph.append("%s %s" % (s["id"], sorted(used - shadow_glyphs)))
        # The edge of the disc must not be a hard cut: either a half block or the
        # soft ladder has to appear, or the shadow is a rectangle of solid cells.
        if not (used & {"▄", "▀", "░", "▒", "▓"}):
            bad_glyph.append("%s is a hard-edged block" % s["id"])
        # Flatter than a circle on SCREEN. Not "much flatter than its prop": a
        # shrub is a low mound, so its own box is nearly as flat as its shadow --
        # the comparison only means something for a tall prop.
        box = (s["w"] * payload["cell"]["w"]) / (s["h"] * payload["cell"]["h"])
        if box < 1.2:
            box_flat.append("%s %.2f:1" % (s["id"], box))
        cols = sorted({c for r in s["cells"] for c in r["c"] if c})
        if len(cols) != 1:
            bad_ink.append("%s %d colours" % (s["id"], len(cols)))
    check("shadow disc is 2:1 in geometry (the grid cannot show 2:1 below one cell)",
          not bad_ratio,
          ", ".join(bad_ratio[:3])
          or "24/24 at %.2f:1 (measured on the drawn ellipse, not on the cell box)"
          % ((decals[props[0]["shadow"]]["disc"]["rx"] * payload["cell"]["w"])
             / (decals[props[0]["shadow"]]["disc"]["ry"] * payload["cell"]["h"])))
    check("shadow shape: a disc, not a bar, drawn with half blocks", not bad_shape and not bad_glyph,
          ", ".join((bad_shape + bad_glyph)[:3])
          or "24/24 heaviest at the anchor row, soft or half-block edge")
    check("shadow anchor is the centre of the disc", not bad_anchor, ", ".join(bad_anchor[:3]))
    check("shadow box is flatter than a circle on screen", not box_flat,
          ", ".join(box_flat[:3]) or "24/24 at least 1.2:1 wide to tall")
    # --- lit from above -------------------------------------------------------
    # The strongest cue that the camera is looking DOWN at a mass: its top face is
    # the brightest. Measured on the crown rows: the top of the window against its
    # bottom. Only asserted for the round-crowned species -- on a conifer the top
    # of the piece is a narrow tip and on a palm it is trunk, so the window there
    # measures cell COVERAGE, not lighting, and the number would be meaningless.
    gradients = []
    for p in props:
        if p["species"] not in ("oak", "birch", "willow", "autumn"):
            continue
        cut = max(3, int(p["h"] * 0.55))
        prof = []
        for i in range(cut):
            cs = [0.2126 * int(c[1:3], 16) + 0.7152 * int(c[3:5], 16) + 0.0722 * int(c[5:7], 16)
                  for c in p["cells"][i]["c"] if c]
            if cs:
                prof.append(sum(cs) / len(cs))
        if len(prof) < 3:
            continue
        gradients.append((p["id"], 100 * ((prof[0] + prof[1]) - (prof[-1] + prof[-2]))
                          / max(1.0, prof[-1] + prof[-2])))
    mean_gradient = sum(g for _i, g in gradients) / max(1, len(gradients))
    worst_gradient = min(gradients, key=lambda t: t[1])
    check("crown is lit from above (top brighter than the crown's base)",
          mean_gradient >= 15.0,
          "mean +%.0f%%, worst %s %+.0f%% (crown species only)" % (mean_gradient, *worst_gradient))

    floor_lum = 0.2126 * int(payload["floorTone"][1:3], 16) + 0.7152 * int(payload["floorTone"][3:5], 16) \
        + 0.0722 * int(payload["floorTone"][5:7], 16)
    shadow_lum = 0.2126 * int(payload["shadowInk"][1:3], 16) + 0.7152 * int(payload["shadowInk"][3:5], 16) \
        + 0.0722 * int(payload["shadowInk"][5:7], 16)
    check("shadow is one colour and darker than the floor it darkens",
          not bad_ink and shadow_lum < floor_lum * 0.7,
          "shadow %s (lum %.0f) under floor %s (lum %.0f), single colour"
          % (payload["shadowInk"], shadow_lum, payload["floorTone"], floor_lum))

    # Perceived brightness of the CELLS, which is what a reader sees. The metric
    # is the BRIGHT quartile, not the median: the median of an airy species (a
    # palm, a bare tree) is dominated by its faint silhouette edge, so it measures
    # how thin the subject is, not whether the ink reads.
    cell_lums = sorted(0.2126 * int(c[1:3], 16) + 0.7152 * int(c[3:5], 16)
                       + 0.0722 * int(c[5:7], 16)
                       for p in props for r in p["cells"] for c in r["c"] if c)
    quarters = []
    for p in props:
        own = sorted(0.2126 * int(c[1:3], 16) + 0.7152 * int(c[3:5], 16) + 0.0722 * int(c[5:7], 16)
                     for r in p["cells"] for c in r["c"] if c)
        quarters.append((p["id"], own[int(0.75 * (len(own) - 1))]))
    worst = min(quarters, key=lambda t: t[1])
    check("every piece has visible ink (bright quartile >= 60)", worst[1] >= 60,
          "worst %s p75 %.0f" % worst)
    p10 = cell_lums[int(0.10 * (len(cell_lums) - 1))]
    check("catalogue ink floor (p10 >= 22)", p10 >= 22,
          "p10 %.0f · p25 %.0f · p50 %.0f (weak boost measured 17 / 35 / 73)"
          % (p10, cell_lums[int(0.25 * len(cell_lums))], cell_lums[len(cell_lums) // 2]))
    return payload


def section_b(payload):
    print("B. the page in a real browser")
    decals = {d["id"]: d for d in payload["pieces"] if d["kind"] == "decal"}
    heights = {}
    groups = {}
    for p in payload["pieces"]:
        if p["kind"] != "prop":
            continue
        groups.setdefault(p["species"], []).append(p)
        heights[p["species"]] = max(heights.get(p["species"], 0), p["h"])

    def panel_rows(sid):
        """Rows the panel must have: the ground row is fixed, and only the frame
        grows to hold the near half of the shadows."""
        return heights[sid] + max(decals[p["shadow"]]["h"] - 1 - decals[p["shadow"]]["anchor"]["y"]
                                  for p in groups[sid])

    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for (vw, vh) in ((1440, 900), (390, 844)):
            page = browser.new_page(viewport={"width": vw, "height": vh})
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            requests = []
            page.on("request", lambda r: requests.append(r.url))
            page.goto("file://" + PAGE)
            page.wait_for_timeout(400)

            if vw == 1440:
                check("no console/page error", not errors, "; ".join(errors[:2]))
                external = [u for u in requests if not u.startswith("file://")]
                check("offline (no external request)", not external, ", ".join(external[:2]))
                page.screenshot(path=SHOT, full_page=True)

            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check("no horizontal overflow at %dx%d" % (vw, vh), overflow <= 0, "%d px" % overflow)

            sections = page.evaluate("document.querySelectorAll('section.card').length")
            pres = page.evaluate("document.querySelectorAll('pre').length")
            metrics = page.evaluate("""() => {
                const pre = document.querySelector('pre');
                const probe = document.createElement('span');
                probe.textContent = '0'.repeat(20);
                probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre';
                pre.appendChild(probe);
                const w = probe.getBoundingClientRect().width / 20;
                probe.remove();
                const cs = getComputedStyle(pre);
                const lh = cs.lineHeight;
                // line-height already resolves to px here: multiplying it by the
                // font size again would hand the audit a bogus row height and a
                // meaningless tolerance.
                const cellH = lh.endsWith('px') ? parseFloat(lh) : parseFloat(cs.fontSize) * (parseFloat(lh) || 1);
                return {cellW: w, cellH: cellH, fs: parseFloat(cs.fontSize)};
            }""")
            if vw == 1440:
                check("panel per species", sections == 8, "%d sections, %d pre" % (sections, pres))
                check("font readable", 6.0 <= metrics["fs"] <= 20.0, "%.2f px" % metrics["fs"])

            # the baseline: read the rendered text of each panel and require ink in
            # the last line under every tree (gap 4 cells, matching the generator)
            report = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('section.card').forEach(sec => {
                    const pre = sec.querySelector('pre');
                    const r = pre.getBoundingClientRect();
                    const lines = pre.textContent.split('\\n');
                    out.push({id: sec.id, rows: lines.length, lines: lines,
                              rect: {x: r.x, y: r.y, w: r.width, h: r.height}});
                });
                return out;
            }""")
            # The baseline is the GROUND ROW, which the page fixes at height - 1;
            # the panel grows BELOW it to hold the near half of the shadows, so
            # the last line is not the ground any more.
            failing = []
            for entry in report:
                sid = entry["id"][2:]
                ground = heights[sid] - 1
                line = entry["lines"][ground] if ground < len(entry["lines"]) else ""
                cursor = 0
                for p in groups.get(sid, []):
                    col = cursor + p["anchor"]["x"]
                    if col >= len(line) or line[col] == " ":
                        failing.append("%s/%s" % (sid, p["size"]))
                    cursor += p["w"] + 4
            if vw == 1440:
                check("one baseline: every tree inked on the ground row", not failing,
                      ", ".join(failing[:6]) or "24/24 trees touch the ground")
                rows_ok = all(e["rows"] == panel_rows(e["id"][2:]) for e in report)
                check("panel rows = tallest tree + room for the shadows", rows_ok,
                      ", ".join("%s:%d" % (e["id"][2:], e["rows"]) for e in report[:4]) + " …")
                # geometry for the pixel section: where each tree landed on screen
                geometry = []
                for entry in report:
                    sid = entry["id"][2:]
                    trees = []
                    cursor = 0
                    for p in groups.get(sid, []):
                        trees.append({"size": p["size"],
                                      "x0": entry["rect"]["x"] + cursor * metrics["cellW"],
                                      "x1": entry["rect"]["x"] + (cursor + p["w"]) * metrics["cellW"],
                                      "ax": p["anchor"]["x"]})
                        cursor += p["w"] + 4
                    geometry.append({"id": sid, "pre": entry["rect"], "cellW": metrics["cellW"],
                                     "cellH": metrics["cellH"], "trees": trees})
            page.close()
        browser.close()
    return geometry


def section_c(geometry):
    """The rendered pixels: where the ink really stops, and what colour the page
    actually shows. The DOM says where the text is; only the raster says where a
    reader's eye sees the tree stand."""
    from PIL import Image
    import colorsys

    print("C. the rendered pixels (ground line + colour on screen)")
    img = Image.open(SHOT).convert("RGB")
    panels_dir = os.path.join(os.path.dirname(SHOT), "panels")
    os.makedirs(panels_dir, exist_ok=True)

    offsets = []
    hues = {}
    cell_h = geometry[0].get("cellH", 19.0) if geometry else 19.0
    for panel in geometry:
        px = panel["pre"]
        x0 = max(0, int(px["x"]) - 4)
        x1 = min(img.width, int(px["x"] + px["w"]) + 4)
        y0 = max(0, int(px["y"]) - 4)
        y1 = min(img.height, int(px["y"] + px["h"]) + 4)
        crop = img.crop((x0, y0, x1, y1))
        crop.save(os.path.join(panels_dir, "panel-%s.png" % panel["id"]))
        cpx = crop.load()

        lows = []
        for tree in panel["trees"]:
            tx0 = max(0, int(tree["x0"] - x0))
            tx1 = min(crop.width, int(tree["x1"] - x0))
            low = -1
            # BRIGHT ink only: the shadow is dark on purpose (lum ~24) and the
            # floor is mid (lum ~53), so a plain threshold would find the shadow
            # and measure the wrong thing. The trunk's contact cell is the bright
            # thing that has to stop on the ground row.
            for y in range(crop.height - 1, -1, -1):
                if any(sum(cpx[x, y]) / 3.0 > 85 for x in range(tx0, tx1)):
                    low = y
                    break
            lows.append(low)
        offsets.append(max(lows) - min(lows))

        # dominant hue of the ink actually painted in this panel
        hues_list = []
        for y in range(0, crop.height, 2):
            for x in range(0, crop.width, 2):
                c = cpx[x, y]
                if sum(c) / 3.0 > 55 and not (abs(c[0] - c[1]) < 12 and abs(c[1] - c[2]) < 12):
                    h, s, v = colorsys.rgb_to_hsv(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
                    hues_list.append(h * 360)
        if hues_list:
            hues_list.sort()
            hues[panel["id"]] = hues_list[len(hues_list) // 2]

    check("ground line: all three sizes stop on the same row",
          max(offsets) <= cell_h * 0.75,
          "worst spread %d px (one row is %.0f px) across %d panels"
          % (max(offsets), cell_h, len(offsets)))
    oak_h, autumn_h = hues.get("oak"), hues.get("autumn")
    gap = abs(((oak_h or 0) - (autumn_h or 0) + 180) % 360 - 180)
    check("colour reaches the screen and separates species", oak_h is not None and gap > 25,
          "oak %.0f° vs autumn %.0f° (gap %.0f°)" % (oak_h or -1, autumn_h or -1, gap))
    check("panels cropped for looking", len(os.listdir(panels_dir)) == 8,
          "%s" % os.path.relpath(panels_dir, HERE))


def main():
    print("artforge audit")
    payload = section_a()
    geometry = section_b(payload)
    section_c(geometry)
    print()
    failed = [r for r in results if not r[1]]
    print("%d/%d checks passed" % (len(results) - len(failed), len(results)))
    if failed:
        for (name, _ok, detail) in failed:
            print("  FAILED: %s %s" % (name, detail))
        sys.exit(1)
    print("screenshot: %s" % os.path.relpath(SHOT, HERE))


if __name__ == "__main__":
    main()
