#!/usr/bin/env python3
"""bank audit: the library page measured in a real browser.

A browser with filters is only worth something if the filters actually select the
right pieces, so this clicks them and counts what is on screen -- against the
index, not against the page's own idea of itself.

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

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("  [%s] %-46s %s" % ("ok" if ok else "FAIL", name, detail))


def main():
    print("bank audit")
    with open(INDEX, encoding="utf-8") as fh:
        index = json.load(fh)
    total = len(index["pieces"])
    by_slot = {}
    for e in index["pieces"]:
        by_slot[e["slot"]] = by_slot.get(e["slot"], 0) + 1
    conifers = sum(1 for e in index["pieces"] if "conifer" in e["tags"])

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

                cards = page.evaluate("document.querySelectorAll('.card').length")
                check("one card per piece in the index", cards == total,
                      "%d cards for %d pieces" % (cards, total))
                visible = page.evaluate(
                    "Array.from(document.querySelectorAll('.card')).filter(c => !c.classList.contains('hidden')).length")
                check("without a filter the whole bank shows", visible == total, "%d visible" % visible)

                def click_and_count(selector, text):
                    page.click("%s >> text=%s" % (selector, text))
                    page.wait_for_timeout(120)
                    return page.evaluate(
                        "Array.from(document.querySelectorAll('.card'))"
                        ".filter(c => !c.classList.contains('hidden')).length")

                got = click_and_count("button.f", "conifer")
                check("tag filter selects the right pieces", got == conifers,
                      "conifer -> %d card(s), index has %d" % (got, conifers))
                click_and_count("button.f", "conifer")          # toggle off

                got = click_and_count("button.f", "mancha")
                check("slot filter reaches the discs", got == by_slot.get("mancha", 0),
                      "mancha -> %d card(s), index has %d" % (got, by_slot.get("mancha", 0)))
                click_and_count("button.f", "mancha")

                page.fill("#q", "palm")
                page.wait_for_timeout(120)
                got = page.evaluate(
                    "Array.from(document.querySelectorAll('.card'))"
                    ".filter(c => !c.classList.contains('hidden')).length")
                palm = sum(1 for e in index["pieces"] if "palm" in e["id"] or e["species"] == "palm")
                check("search box filters by id/species/tag", got == palm,
                      "'palm' -> %d card(s), index has %d" % (got, palm))
                page.fill("#q", "")

                buttons = page.evaluate("document.querySelectorAll('.copy').length")
                check("every card can hand its piece over", buttons == total,
                      "%d copy buttons" % buttons)
                stamped = page.evaluate(
                    "Array.from(document.querySelectorAll('.copy')).filter(b => !b.dataset.json).length")
                check("each card carries the anchor and hash to pick it up", stamped == 0,
                      "%d cards without a payload" % stamped)

            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check("no horizontal overflow at %dx%d" % (vw, vh), overflow <= 0, "%d px" % overflow)
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
