#!/usr/bin/env python3
"""bank audit: the library page measured in a real browser.

A browser with filters is only worth something if the filters actually select the right
pieces, so this clicks them and counts what is on screen -- against the index, not
against the page's own idea of itself.

Two things this page has that are easy to get wrong and are therefore checked here: the
bank is split into two SECTIONS (the scene and the inventory items) and one card carries
a whole thing at its three resolutions with the biggest one showing. A filter counts
PIECES, not cards: reporting a filter as having lost pieces it is still showing is the
failure mode of counting the wrong thing.

Run: PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/bank_audit.py
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(HERE, "bank", "index.json")
PAGE = os.path.join(HERE, "bank", "bank.html")
SHOT = os.path.join(HERE, "reports", "bank.png")

# in the browser: the pieces a filter is actually showing, read from each card's own
# declaration of what it holds
PIECES_SHOWN = """() => Array.from(document.querySelectorAll('.card'))
  .filter(c => !c.classList.contains('hidden'))
  .reduce((n, c) => n + JSON.parse(c.dataset.meta).ids.length, 0)"""

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("  [%s] %-46s %s" % ("ok" if ok else "FAIL", name, detail))


def main():
    print("bank audit")
    with open(INDEX, encoding="utf-8") as fh:
        index = json.load(fh)
    total = len(index["pieces"])
    sizes = {e["id"]: e["w"] * e["h"] for e in index["pieces"]}
    by_slot = {}
    for e in index["pieces"]:
        by_slot[e["slot"]] = by_slot.get(e["slot"], 0) + 1
    conifers = sum(1 for e in index["pieces"] if "conifer" in e["tags"])
    palms = sum(1 for e in index["pieces"] if "palm" in e["id"] or e["species"] == "palm")
    icons = sum(1 for e in index["pieces"] if e["slot"] == "icone")

    check("index resolves its own set files", all(
        os.path.exists(os.path.join(HERE, "bank", e["file"])) for e in index["pieces"]),
        "%d pieces in %d sets" % (total, len(index["sets"])))

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
            page.wait_for_timeout(300)

            if vw == 1440:
                check("no console/page error", not errors, "; ".join(errors[:2]))
                external = [u for u in requests if not u.startswith("file://")]
                check("offline (no external request)", not external, ", ".join(external[:2]))
                page.screenshot(path=SHOT, full_page=True)

                cards = page.evaluate("""() => Array.from(document.querySelectorAll('.card'))
                  .map(c => ({ids: JSON.parse(c.dataset.meta).ids,
                              slot: JSON.parse(c.dataset.meta).slot,
                              section: c.closest('.sec').dataset.section}))""")
                held = [i for c in cards for i in c["ids"]]
                check("every piece sits in exactly one card",
                      sorted(held) == sorted(e["id"] for e in index["pieces"]),
                      "%d cards holding %d pieces (index has %d)"
                      % (len(cards), len(held), total))

                sections = {}
                for c in cards:
                    sections.setdefault(c["section"], set()).update({c["slot"]})
                check("the scene and the inventory are separate sections",
                      set(sections) == {"cena", "itens"}
                      and sections["cena"] == {"prop", "mancha"}
                      and sections["itens"] == {"icone"},
                      "; ".join("%s: %s" % (k, ",".join(sorted(v)))
                                for k, v in sorted(sections.items())))

                # A grid nested inside a grid gives the section ONE track (268px) and
                # the gallery inside it collapses to a single column -- measured, because
                # counting cards and checking the DOM never caught it.
                layout = page.evaluate("""() => Array.from(document.querySelectorAll('.sec'))
                  .map(sec => { const cards = Array.from(sec.querySelectorAll('.card'));
                                const xs = new Set(cards.map(c => Math.round(c.getBoundingClientRect().x)));
                                const ys = new Set(cards.map(c => Math.round(c.getBoundingClientRect().y)));
                                const rows = {};
                                cards.forEach(c => { const r = c.getBoundingClientRect();
                                  rows[Math.round(r.y)] = (rows[Math.round(r.y)] || 0) + 1; });
                                return {section: sec.dataset.section, cards: cards.length,
                                        columns: xs.size, rows: ys.size,
                                        widestRow: Math.max.apply(null, Object.values(rows)),
                                        secWidth: Math.round(sec.getBoundingClientRect().width)}; })""")
                stacked = [l for l in layout
                           if l["cards"] >= 4 and (l["columns"] < 3 or l["widestRow"] < 2)]
                check("each section is a gallery, not a column",
                      not stacked,
                      "; ".join("%s: %d cartões em %d colunas, seção %dpx"
                                % (l["section"], l["cards"], l["columns"], l["secWidth"])
                                for l in layout))

                # A FIXED cell with the piece centred in it: every card in a section the
                # same width AND the same height, and the art's centre within a few px of
                # its box's centre. Measuring the box is the only way to tell "centred"
                # from "happens to look centred on a piece that fills the card".
                centred = page.evaluate("""() => Array.from(document.querySelectorAll('.sec'))
                  .map(sec => {
                    const rs = Array.from(sec.querySelectorAll('.card'))
                      .map(c => c.getBoundingClientRect());
                    const ws = new Set(rs.map(r => Math.round(r.width)));
                    const hs = new Set(rs.map(r => Math.round(r.height)));
                    let worst = 0;
                    sec.querySelectorAll('.res.on .art').forEach(a => {
                      const ar = a.getBoundingClientRect();
                      const pre = a.querySelector('pre').getBoundingClientRect();
                      worst = Math.max(worst,
                        Math.abs((pre.x + pre.width / 2) - (ar.x + ar.width / 2)),
                        Math.abs((pre.y + pre.height / 2) - (ar.y + ar.height / 2)));
                    });
                    return {section: sec.dataset.section, cards: rs.length,
                            widths: ws.size, heights: hs.size, worst: Math.round(worst)};
                  })""")
                check("the cell is fixed: same width and height across a section",
                      all(c["widths"] == 1 and c["heights"] == 1 for c in centred),
                      "; ".join("%s: %d larguras, %d alturas em %d cartões"
                                % (c["section"], c["widths"], c["heights"], c["cards"])
                                for c in centred))
                check("the piece is centred in its art box",
                      all(c["worst"] <= 12 for c in centred),
                      "; ".join("%s: pior desvio %d px" % (c["section"], c["worst"])
                                for c in centred))

                # Each card opens on its biggest piece, and the switch works.
                opens = page.evaluate("""() => Array.from(document.querySelectorAll('.card'))
                  .map(c => { const on = c.querySelector('.res.on');
                              return {ids: JSON.parse(c.dataset.meta).ids,
                                      on: on ? on.dataset.id : null}; })""")
                wrong = [o for o in opens if not o["on"]
                         or sizes[o["on"]] != max(sizes[i] for i in o["ids"])]
                check("every card opens on its LARGEST resolution", not wrong,
                      "%d cards, %d not opening on the biggest" % (len(opens), len(wrong)))

                target = "weapon.sword.great.small"
                card_id = "weapon.sword.great"
                page.evaluate("""(id) => {
                    const b = Array.from(document.querySelectorAll('button.r'))
                      .find(x => x.dataset.target === id);
                    b.click();
                }""", target)
                page.wait_for_timeout(120)
                now = page.evaluate("""(id) => {
                    const card = Array.from(document.querySelectorAll('.card'))
                      .find(c => JSON.parse(c.dataset.meta).ids.includes(id));
                    const on = card.querySelector('.res.on');
                    const copy = on.querySelector('.copy');
                    return {on: on.dataset.id,
                            copied: JSON.parse(copy.dataset.json).id};
                }""", target)
                check("the resolution button switches what the card shows",
                      now["on"] == target, "%s now shows %s" % (card_id, now["on"]))
                check("and the copy button follows the visible resolution",
                      now["copied"] == target, "copies %s" % now["copied"])

                def shown():
                    return page.evaluate(PIECES_SHOWN)

                check("without a filter the whole bank shows", shown() == total,
                      "%d of %d pieces" % (shown(), total))

                def click_and_count(text):
                    page.click("button.f >> text=%s" % text)
                    page.wait_for_timeout(120)
                    return shown()

                got = click_and_count("conifer")
                check("tag filter selects the right pieces", got == conifers,
                      "conifer -> %d pieces, index has %d" % (got, conifers))
                click_and_count("conifer")                       # toggle off

                page.click("button.f >> text=mancha")
                page.wait_for_timeout(150)
                got = shown()
                hidden = page.evaluate(
                    "Array.from(document.querySelectorAll('.sec'))"
                    ".filter(s => s.classList.contains('hidden'))"
                    ".map(s => s.dataset.section)")
                check("slot filter reaches the discs", got == by_slot.get("mancha", 0),
                      "mancha -> %d pieces, index has %d" % (got, by_slot.get("mancha", 0)))
                check("and a section emptied by the filter takes its heading with it",
                      hidden == ["itens"], "hidden sections: %s" % (hidden or "none"))
                click_and_count("mancha")

                page.fill("#q", "palm")
                page.wait_for_timeout(120)
                got = shown()
                check("search box filters by id/species/tag", got == palms,
                      "'palm' -> %d pieces, index has %d" % (got, palms))
                page.fill("#q", "icone")
                page.wait_for_timeout(120)
                check("the search reaches the item section too", shown() == icons,
                      "'icone' -> %d pieces, index has %d" % (shown(), icons))
                page.fill("#q", "")

                buttons = page.evaluate("document.querySelectorAll('.copy').length")
                check("every resolution can hand its piece over", buttons == total,
                      "%d copy buttons for %d pieces" % (buttons, total))
                stamped = page.evaluate(
                    "Array.from(document.querySelectorAll('.copy'))"
                    ".filter(b => !b.dataset.json).length")
                check("each carries the anchor and hash to pick it up", stamped == 0,
                      "%d without a payload" % stamped)

            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check("no horizontal overflow at %dx%d" % (vw, vh), overflow <= 0, "%d px" % overflow)
            page.close()

        # Without JavaScript the page still has to be the whole bank: the resolution
        # switch is gated on a class the script sets, so all three should be visible.
        page = browser.new_page(viewport={"width": 1440, "height": 900},
                                java_script_enabled=False)
        page.goto("file://" + PAGE)
        page.wait_for_timeout(200)
        blocks = page.evaluate("document.querySelectorAll('.res').length")
        hidden = page.evaluate("""() => Array.from(document.querySelectorAll('.res'))
          .filter(r => !(r.offsetWidth || r.offsetHeight || r.getClientRects().length)).length""")
        check("with JavaScript off, every resolution is still on the page",
              blocks == total and hidden == 0,
              "%d resolution blocks, %d hidden" % (blocks, hidden))
        page.close()
        browser.close()

    failed = [r for r in results if not r[1]]
    print()
    print("%d/%d checks passed" % (len(results) - len(failed), len(results)))
    if failed:
        for (name, _ok, detail) in failed:
            print("  FAILED: %s %s" % (name, detail))
        sys.exit(1)
    print("screenshot: %s" % os.path.relpath(SHOT, HERE))


if __name__ == "__main__":
    main()
