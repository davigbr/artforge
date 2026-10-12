#!/usr/bin/env python3
"""bank -- the piece library: every set that has been generated, indexed, tagged and
reusable by another game.

Why a bank and not just the generator's output: a set is what one script produced
for one game; the bank is the stock. It keeps the set files untouched, indexes
every piece with the metadata another project needs to pick it (slot, species,
size, tags, size in cells, ANCHOR, its shadow), and gives each piece a content
hash so the same piece arriving from two sets is recognisable as one thing.

The SLOT vocabulary is the one the engine draws by:
    piso    the ground, repeated on every tile (must tile with itself)
    bloco   a tile with height: wall, cliff, thick trunk
    prop    a static object standing on a tile (a tree)
    ator    something that walks and animates
    mancha  flat, drawn with the floor, never occludes (a contact shadow)
    efeito  fire, smoke, glow

Usage:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py ingest [file]
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py build
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py list [--slot S] [--tag T]
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py check
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py export --out game.json [--slot S] [--tag T] [--set X]

`ingest` copies a generated set into the bank, `build` rewrites the index and the
browser, `check` proves the bank is consistent with its own set files.

Code is English; the copy the reader sees on the page is Portuguese.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys

import artforge as af

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "bank")
SETS = os.path.join(BANK, "sets")
INDEX = os.path.join(BANK, "index.json")
PAGE = os.path.join(BANK, "bank.html")
DEFAULT_SET = os.path.join(HERE, "assets", "trees.json")

BANK_VERSION = 1

# What each species IS, so another game can ask for "a conifer" and not for "oak".
# A set that ships its own `pieceTags` overrides this; an unknown species gets the
# slot tag only, which is honest -- the bank should not invent what it does not know.
TAG_RULES = {
    "oak": ["tree", "foliage"],
    "autumn": ["tree", "foliage", "autumn"],
    "birch": ["tree", "foliage", "pale-bark"],
    "pine": ["tree", "conifer"],
    "willow": ["tree", "foliage", "hanging"],
    "palm": ["tree", "palm"],
    "bush": ["shrub", "foliage"],
    "dead": ["tree", "bare"],
    # inventory items (the icone slot): the species is the weapon/armour family
    "dagger": ["arma", "lamina", "curta"],
    "sword": ["arma", "lamina"],
    "mace": ["arma", "contundente"],
    "warhammer": ["arma", "contundente", "haste"],
    "axe": ["arma", "lamina", "haste"],
    "battleaxe": ["arma", "lamina", "haste", "duas-maos"],
    "spear": ["arma", "haste", "longa"],
    "halberd": ["arma", "haste", "longa", "lamina"],
    "bow": ["arma", "distancia"],
    "staff": ["arma", "magica", "haste"],
    "shield": ["armadura", "defesa", "offhand"],
    "helm": ["armadura", "cabeca"],
    "chest": ["armadura", "torso"],
    "breastplate": ["armadura", "torso"],
    "ring": ["adorno", "dedo"],
}

SLOT_OF_KIND = {"prop": "prop", "decal": "mancha", "tile": "piso", "block": "bloco",
                "actor": "ator", "fx": "efeito", "item": "icone"}

# The bank has two halves and they are nothing alike: a piece of the WORLD is placed on
# a tile and has to compose with its neighbours (a floor must tile with itself, a prop
# stands on the ground), while an inventory ITEM is a picture that sits in a list. The
# split lives in the index -- so it can be filtered and exported -- and on the page.
SECTIONS = [
    ("cena", "Cena: paisagem e natureza",
     ("piso", "bloco", "prop", "ator", "mancha", "efeito", "panorama")),
    ("itens", "Itens de inventário", ("icone",)),
    ("outros", "Outros slots", ()),
]

SIZE_ORDER = {"small": 0, "medium": 1, "large": 2, None: 3}
SIZE_LABEL = {"small": "P", "medium": "M", "large": "G"}


def section_of(slot):
    for (key, _label, slots) in SECTIONS:
        if slot in slots:
            return key
    return "outros"


def family_of(piece_id):
    """One THING, however many resolutions it has: an item at three resolutions is three
    rows in the index but one entry to a person browsing the bank."""
    for suffix in (".small", ".medium", ".large"):
        if piece_id.endswith(suffix):
            return piece_id[:-len(suffix)]
    return piece_id


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def piece_hash(piece):
    """Content hash: the same piece arriving from two sets has to be recognisable
    as one thing, so the hash covers exactly what makes the piece what it is --
    its grid, its colours and where its anchor sits -- and nothing about where it
    came from."""
    canon = json.dumps({"w": piece["w"], "h": piece["h"], "anchor": piece["anchor"],
                        "cells": piece["cells"]}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()


def tags_for(piece, set_payload):
    rules = (set_payload.get("pieceTags") or {}).get(piece.get("species"))
    tags = list(rules) if rules else list(TAG_RULES.get(piece.get("species"), []))
    tags.insert(0, SLOT_OF_KIND.get(piece.get("kind"), piece.get("kind")))
    if piece.get("style"):
        tags.append(piece["style"])             # the style is a filter worth having: chain, hood
    if piece.get("size"):
        tags.append(piece["size"])
    return sorted(set(tags))


def entry_for(piece, set_id, set_payload, file_name):
    return {
        "id": piece["id"],
        "set": set_id,
        "file": file_name,
        "kind": piece["kind"],
        "slot": SLOT_OF_KIND.get(piece["kind"], piece["kind"]),
        "section": section_of(SLOT_OF_KIND.get(piece["kind"], piece["kind"])),
        "species": piece.get("species"),
        "size": piece.get("size"),
        "w": piece["w"],
        "h": piece["h"],
        "anchor": piece["anchor"],
        "shadow": piece.get("shadow"),
        "frames": piece.get("frames", 1),
        "directions": piece.get("directions", 1),
        "tags": tags_for(piece, set_payload),
        "hash": piece_hash(piece),
    }


def build_index():
    sets = []
    pieces = []
    for name in sorted(os.listdir(SETS)) if os.path.isdir(SETS) else []:
        if not name.endswith(".json"):
            continue
        payload = read_json(os.path.join(SETS, name))
        set_id = payload.get("set") or os.path.splitext(name)[0]
        entries = [entry_for(p, set_id, payload, "sets/" + name) for p in payload["pieces"]]
        pieces.extend(entries)
        sets.append({
            "id": set_id,
            "label": payload.get("label") or set_id,
            "file": "sets/" + name,
            "generator": payload.get("generator"),
            "seed": payload.get("seed"),
            "cell": payload.get("cell"),
            "isoFlat": payload.get("isoFlat"),
            "floorTone": payload.get("floorTone"),
            "shadowInk": payload.get("shadowInk"),
            "slots": sorted({e["slot"] for e in entries}),
            "tags": sorted({t for e in entries for t in e["tags"]}),
            "counts": {slot: sum(1 for e in entries if e["slot"] == slot)
                       for slot in sorted({e["slot"] for e in entries})},
            "pieceCount": len(entries),
        })
    index = {
        "version": BANK_VERSION,
        "generator": "bank.py",
        "slots": sorted({e["slot"] for e in pieces}),
        "tags": sorted({t for e in pieces for t in e["tags"]}),
        "sets": sets,
        "pieces": pieces,
    }
    write_json(INDEX, index)
    return index


def select(index, slot=None, tag=None, set_id=None, species=None, section=None):
    out = []
    for e in index["pieces"]:
        if slot and e["slot"] != slot:
            continue
        if section and e.get("section") != section:
            continue
        if tag and tag not in e["tags"]:
            continue
        if set_id and e["set"] != set_id:
            continue
        if species and e["species"] != species:
            continue
        out.append(e)
    return sorted(out, key=lambda e: (SIZE_ORDER.get(e["size"], 9), e["id"]))


# --- the browser --------------------------------------------------------------
def compose(prop, shadow, floor):
    """The piece as the engine would draw it: the shadow first (it is flat and lies
    with the floor), the prop standing on top, both placed by their ANCHOR."""
    ground = prop["h"] - 1
    below = (shadow["h"] - 1 - shadow["anchor"]["y"]) if shadow else 0
    rows = prop["h"] + below
    canvas = [[" "] * prop["w"] for _ in range(rows)]
    colors = [[""] * prop["w"] for _ in range(rows)]
    if shadow:
        sh_x = prop["anchor"]["x"] - shadow["anchor"]["x"]
        sh_y = ground - shadow["anchor"]["y"]
        for y, row in enumerate(shadow["cells"]):
            wy = sh_y + y
            for x in range(shadow["w"]):
                wx = sh_x + x
                if row["g"][x] == " " or not (0 <= wx < prop["w"] and 0 <= wy < rows):
                    continue
                canvas[wy][wx] = row["g"][x]
                colors[wy][wx] = row["c"][x]
    base = ground - prop["anchor"]["y"]
    for y, row in enumerate(prop["cells"]):
        for x in range(prop["w"]):
            if row["g"][x] == " ":
                continue
            canvas[base + y][x] = row["g"][x]
            colors[base + y][x] = row["c"][x]
    return [{"g": "".join(r), "c": colors[y]} for y, r in enumerate(canvas)], ground


def compose_decal(shadow):
    """A decal on its own: a library of discs is useful by itself -- another game
    can pick a contact shadow and pair it with anything."""
    return [{"g": row["g"], "c": row["c"]} for row in shadow["cells"]], shadow["anchor"]["y"]


PAGE_HEAD = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>artforge — banco de peças</title>
<style>
  :root {
    --panelw: min(1240px, calc(100vw - 40px));
    --bg: #05070a; --panel: #0b0f14; --line: #1c2430;
    --ink: #e9e5d8; --dim: #8b8f92; --accent: #cfa855;
    --mono: "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 30px 20px 52px; color: var(--ink); font-family: var(--mono);
         line-height: 1.5; background: radial-gradient(120% 70% at 50% 0%, #111a26 0%, var(--bg) 58%, #030405 100%); }
  .wrap { width: var(--panelw); margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 6px; }
  .lede { color: var(--dim); font-size: 12.5px; margin: 0 0 16px; max-width: 96ch; }
  .lede b { color: var(--accent); font-weight: 600; }
  .bar { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 8px; }
  button.f { font: inherit; font-size: 11.5px; color: var(--ink); background: #101721;
             border: 1px solid var(--line); border-radius: 6px; padding: 4px 10px; cursor: pointer; }
  button.f[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
  .field { font: inherit; font-size: 12px; color: var(--ink); background: #101721;
           border: 1px solid var(--line); border-radius: 6px; padding: 5px 9px; min-width: 190px; }
  .count { color: var(--dim); font-size: 11.5px; margin: 6px 0 14px; }
  /* A gallery of FIXED cells: the tracks do not resize with the content, and every art
     area is one height, so the cards line up and the piece sits centred inside it. */
  .grid { display: grid; grid-template-columns: repeat(auto-fill, 300px);
          grid-auto-rows: 1fr; gap: 14px; justify-content: center; }
  .card { border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
          overflow: hidden; display: flex; flex-direction: column; }
  .card.decal { border-color: #2d3a4a; }
  .badge { display: inline-block; border: 1px solid var(--accent); color: var(--accent);
           border-radius: 4px; padding: 0 5px; font-size: 10px; margin-right: 6px; }
  .art { flex: 0 0 auto; display: flex; align-items: center; justify-content: center;
         height: var(--framh, 240px); padding: 8px; overflow: hidden; }
  pre { margin: 0; font-family: var(--mono); font-size: __FS__px; line-height: 1.1;
        white-space: pre; font-variant-ligatures: none; -webkit-font-smoothing: antialiased;
        text-align: center; }
  pre i { font-style: normal; }
  .meta { flex: 1; padding: 8px 12px 11px; border-top: 1px solid var(--line);
          font-size: 11px; color: var(--dim); }
  .meta b { color: var(--accent); font-weight: 600; }
  .meta .id { color: var(--ink); display: block; margin-bottom: 3px; }
  .tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 6px; }
  .tag { border: 1px solid var(--line); border-radius: 4px; padding: 1px 6px; font-size: 10.5px; }
  .tag.slot { border-color: var(--accent); color: var(--accent); }
  .copy { font: inherit; font-size: 10.5px; color: var(--ink); background: #101721;
          border: 1px solid var(--line); border-radius: 5px; padding: 2px 8px; cursor: pointer; margin-top: 8px; }
  .hidden { display: none; }
  /* One card per THING, and the resolutions behind a button. The rule is gated on a
     class the script sets on <html>, so with JavaScript off every resolution is on the
     page and the bank is complete -- same deal as the filters. */
  .js .res { display: none; }
  .js .res.on { display: block; }
  .cap { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: center;
         padding: 8px 12px 7px; border-bottom: 1px solid var(--line);
         font-size: 11px; color: var(--dim); }
  .cap b { color: var(--accent); font-weight: 600; }
  .rbar { display: flex; flex-wrap: wrap; gap: 5px; margin-left: auto; }
  button.r { font: inherit; font-size: 10.5px; color: var(--dim); background: #101721;
             border: 1px solid var(--line); border-radius: 5px; padding: 1px 7px; cursor: pointer; }
  button.r[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
  /* The two halves of the bank, as sections: the world's art and the inventory's art are
     different problems and reading them mixed together is how you pick the wrong piece. */
  .sec h2 { font-size: 14px; margin: 28px 0 10px; color: var(--ink); font-weight: 600; }
  .sec:first-of-type h2 { margin-top: 8px; }
  .sec h2 .n { color: var(--dim); font-size: 11.5px; font-weight: 400; margin-left: 8px; }
  footer { color: var(--dim); font-size: 11.5px; border-top: 1px solid var(--line); padding-top: 12px; margin-top: 18px; }
  code { color: var(--accent); }
</style>
<script>document.documentElement.className = "js";</script>
</head><body><div class="wrap">
<h1>artforge — banco de peças</h1>
<p class="lede">__LEDE__</p>
<div class="bar" id="slots"></div>
<div class="bar" id="tags"></div>
<div class="bar"><input class="field" id="q" placeholder="filtrar por id, espécie, tag…" aria-label="filtro"></div>
<p class="count" id="count"></p>
__CARDS__
<footer>__FOOTER__</footer>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
  var index = JSON.parse(document.getElementById("data").textContent);
  var state = {slot: null, tag: null, q: ""};
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));

  function button(label, kind, value) {
    var b = document.createElement("button");
    b.className = "f";
    b.textContent = label;
    b.dataset.kind = kind;
    b.dataset.value = value == null ? "" : value;
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () {
      state[kind] = (state[kind] === value) ? null : value;
      sync();
    });
    return b;
  }

  var slots = document.getElementById("slots");
  slots.appendChild(button("todos", "slot", null));
  index.slots.forEach(function (s) { slots.appendChild(button(s, "slot", s)); });
  var tags = document.getElementById("tags");
  index.tags.forEach(function (t) { tags.appendChild(button(t, "tag", t)); });

  function matches(meta) {
    if (state.slot && meta.slot !== state.slot) return false;
    if (state.tag && meta.tags.indexOf(state.tag) === -1) return false;
    if (state.q) {
      var hay = (meta.ids.join(" ") + " " + meta.species.join(" ") + " "
                 + meta.tags.join(" ")).toLowerCase();
      if (hay.indexOf(state.q.toLowerCase()) === -1) return false;
    }
    return true;
  }

  // The count is PIECES, not cards: one card can carry three resolutions, and counting
  // cards would report a filter as having lost pieces it is still showing.
  function sync() {
    document.querySelectorAll("button.f").forEach(function (b) {
      var on = state[b.dataset.kind] === (b.dataset.value || null);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    var shown = 0, total = 0;
    cards.forEach(function (card) {
      var meta = JSON.parse(card.dataset.meta);
      var ok = matches(meta);
      card.classList.toggle("hidden", !ok);
      total += meta.ids.length;
      if (ok) shown += meta.ids.length;
    });
    // A section with nothing visible is a heading over an empty space: hide it too.
    document.querySelectorAll(".sec").forEach(function (sec) {
      var any = false;
      sec.querySelectorAll(".card").forEach(function (c) {
        if (!c.classList.contains("hidden")) any = true;
      });
      sec.classList.toggle("hidden", !any);
    });
    document.getElementById("count").textContent =
      shown + " de " + total + " peças em " + cards.length + " cartões";
  }

  // Resolution switch. Each card opens on the biggest piece; the buttons swap which
  // resolution block is showing, and the copy button goes with it.
  function showRes(card, id) {
    card.querySelectorAll(".res").forEach(function (r) {
      r.classList.toggle("on", r.dataset.id === id);
    });
    card.querySelectorAll("button.r").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.target === id ? "true" : "false");
    });
  }
  document.querySelectorAll("button.r").forEach(function (b) {
    b.addEventListener("click", function () {
      showRes(this.closest(".card"), this.dataset.target);
    });
  });

  document.getElementById("q").addEventListener("input", function () {
    state.q = this.value;
    sync();
  });

  document.querySelectorAll(".copy").forEach(function (b) {
    b.addEventListener("click", function () {
      var text = this.dataset.json;
      var done = function () { b.textContent = "copiado"; setTimeout(function () { b.textContent = "copiar peça"; }, 1200); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (e) { /* clipboard blocked */ }
        document.body.removeChild(ta);
        done();
      }
    });
  });

  sync();
</script>
</div></body></html>
"""


def render_res(e, by_id):
    """One resolution of one piece: the art plus its metadata.

    Returns the markup AND the size of the art in cells, because the card's art area is
    a FIXED box: without knowing the biggest piece in the section there is nothing to
    size it against, and a box that hugs its content makes a ragged gallery.
    """
    piece, payload = by_id[e["id"]]
    if e["slot"] == "prop":
        shadow = by_id.get(e["shadow"], (None, None))[0]
        rows, _ground = compose(piece, shadow, payload.get("floorTone"))
        detail = "%s &times; %s células · âncora %d,%d<br>mancha <code>%s</code>" % (
            e["w"], e["h"], e["anchor"]["x"], e["anchor"]["y"], e.get("shadow") or "-")
    elif e["slot"] == "mancha":
        rows, _ground = compose_decal(piece)
        detail = ("%s &times; %s células · âncora %d,%d<br>disco rx %.2f × ry %.2f células "
                  "(2:1 na tela)" % (e["w"], e["h"], e["anchor"]["x"], e["anchor"]["y"],
                                     piece["disc"]["rx"], piece["disc"]["ry"]))
    else:
        rows = [{"g": row["g"], "c": row["c"]} for row in piece["cells"]]
        detail = ("%s &times; %s células · âncora %d,%d (centro)<br>resolução <b>%s</b>%s"
                  % (e["w"], e["h"], e["anchor"]["x"], e["anchor"]["y"],
                     SIZE_LABEL.get(e.get("size"), "única"),
                     " · estilo <b>%s</b>" % piece["style"] if piece.get("style") else ""))
    body, _inked = af.run_length_html(rows)
    snippet = json.dumps({"id": e["id"], "kind": e["kind"], "slot": e["slot"], "w": e["w"],
                          "h": e["h"], "anchor": e["anchor"], "shadow": e.get("shadow"),
                          "file": e["file"], "hash": e["hash"]},
                         ensure_ascii=False, separators=(",", ":")).replace('"', "&quot;")
    html = (
        '<div class="res" data-id="%s">\n'
        '  <div class="art" style="background:%s"><pre>%s</pre></div>\n'
        '  <div class="meta"><b class="id">%s</b>%s<br>hash <code>%s</code>'
        '<div class="tags">%s</div>'
        '<button class="copy" data-json="%s">copiar peça</button></div>\n'
        '</div>'
        % (e["id"],
           payload.get("floorTone", "#2a231c" if e["slot"] == "icone" else "#3a352c"), body,
           ('<span class="badge">só a mancha</span>' if e["slot"] == "mancha" else "")
           + e["id"],
           detail, e["hash"][:12],
           "".join('<span class="tag%s">%s</span>'
                   % (" slot" if t == e["slot"] else "", t) for t in e["tags"]),
           snippet))
    return html, len(rows), max(len(r["g"]) for r in rows)


def build_page(index):
    by_id = {}
    for setinfo in index["sets"]:
        payload = read_json(os.path.join(BANK, setinfo["file"]))
        for p in payload["pieces"]:
            by_id[p["id"]] = (p, payload)

    # One card per THING -- its resolutions live behind a button -- and the cards are
    # grouped into the two halves of the bank, which are nothing alike: a piece of the
    # world is placed on a tile and has to compose with its neighbours, an inventory item
    # is a picture that sits in a list.
    groups = {}
    for e in index["pieces"]:
        groups.setdefault((section_of(e["slot"]), family_of(e["id"])), []).append(e)

    cards_by_section, counts, frames = {}, {}, {}
    for (section, _fam), entries in groups.items():
        entries.sort(key=lambda e: SIZE_ORDER.get(e.get("size"), 3))    # small..large
        # Displayed biggest first: the small art is a different drawing, not a thumbnail,
        # but the big one is the one worth the space, so it is the one that shows.
        order = list(reversed(entries))
        blocks = []
        for e in order:
            html, rh, rw = render_res(e, by_id)
            blocks.append(html)
            (fh, fw) = frames.get(section, (0, 0))
            frames[section] = (max(fh, rh), max(fw, rw))
        blocks[0] = blocks[0].replace('class="res"', 'class="res on"', 1)
        header = ""
        if len(order) > 1:
            btns = "".join('<button class="r" data-target="%s">%s <small>%d×%d</small></button>'
                           % (e["id"], SIZE_LABEL.get(e.get("size"), "?"), e["w"], e["h"])
                           for e in order)
            header = ('<div class="cap"><b>%s</b><span>%d resoluções</span>'
                      '<span class="rbar">%s</span></div>'
                      % (_fam, len(order), btns))
        meta = json.dumps({"ids": [x["id"] for x in entries], "slot": entries[0]["slot"],
                           "species": sorted({x["species"] for x in entries
                                              if x.get("species")}),
                           "tags": sorted({t for x in entries for t in x["tags"]})},
                          ensure_ascii=False).replace('"', "&quot;")
        card = ('<article class="card %s" data-meta="%s">\n%s\n%s\n</article>'
                % (entries[0]["slot"], meta, header, "\n".join(blocks)))
        cards_by_section.setdefault(section, []).append(card)
        counts[section] = counts.get(section, 0) + len(entries)

    # The art area is a fixed box, sized once for the whole page so every piece is at the
    # SAME scale (a 16-cell sword is 16 cells in the game) and centred inside the card.
    # The font shrinks until the tallest piece fits: a box that hugs its content gives a
    # ragged gallery, and scaling the font per card would make the pieces incomparable --
    # which is the one thing a catalogue of pieces cannot afford.
    tallest = max([h for (h, _w) in frames.values()] or [8])
    fs = round(max(6.5, min(13.0, 330.0 / (tallest * 1.1))), 2)

    body = []
    for (key, label, _slots) in SECTIONS:
        cards = cards_by_section.get(key)
        if not cards:
            continue
        frame_h = int(round(frames[key][0] * 1.1 * fs + 8))
        body.append('<section class="sec" data-section="%s" style="--framh:%dpx">\n'
                    '<h2>%s <span class="n">%d peças em %d cartões</span></h2>\n'
                    '<div class="grid">\n%s\n</div>\n</section>'
                    % (key, frame_h, label, counts[key], len(cards), "\n".join(cards)))

    lede = ("<b>%d conjuntos</b>, <b>%d peças</b> em <b>%d cartões</b>, separadas em "
            "<b>duas metades que não se misturam</b>: a <b>cena</b> (paisagem e natureza — "
            "piso, bloco, prop, ator, mancha) e os <b>itens</b> (o slot <code>icone</code>). "
            "Cada cartão abre na <b>maior resolução</b> e as outras ficam nos botões ao "
            "lado. A grade é de <b>célula fixa</b> e a peça fica <b>centrada</b> nela, todas "
            "na mesma escala de fonte (<b>%.1f px</b>) — escalar a fonte por cartão deixaria "
            "as peças incomparáveis. Cada peça carrega o tamanho em células, a "
            "<b>âncora</b> (a célula que vai para o centro do tile — ou do centro da caixa, "
            "num item) e um <b>hash de conteúdo</b>. Sem JavaScript a página mostra o banco "
            "inteiro, com todas as resoluções."
            % (len(index["sets"]), len(index["pieces"]), len(groups), fs))
    footer = ("Índice em <code>bank/index.json</code> · conjuntos em <code>bank/sets/</code> · "
              "gerado por <code>bank.py</code> · para levar uma fatia para outro jogo: "
              "<code>bank.py export --section itens --out itens.json</code>")
    html = (PAGE_HEAD.replace("__LEDE__", lede)
            .replace("__FS__", ("%.2f" % fs).rstrip("0").rstrip("."))
            .replace("__CARDS__", "\n".join(body))
            .replace("__FOOTER__", footer)
            .replace("__DATA__", json.dumps(
                {"slots": index["slots"], "tags": index["tags"]}, ensure_ascii=False)))
    for marker in ("__LEDE__", "__FS__", "__CARDS__", "__FOOTER__", "__DATA__"):
        if marker in html:
            raise SystemExit("marker survived the bank build: %s" % marker)
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    return sum(len(v) for v in cards_by_section.values())


# --- commands -----------------------------------------------------------------
def cmd_ingest(path):
    payload = read_json(path)
    set_id = payload.get("set") or os.path.splitext(os.path.basename(path))[0]
    os.makedirs(SETS, exist_ok=True)
    target = os.path.join(SETS, set_id + ".json")
    shutil.copyfile(path, target)
    print("ingested %s -> %s (%d pieces)" % (os.path.relpath(path, HERE),
                                             os.path.relpath(target, HERE),
                                             len(payload["pieces"])))
    index = build_index()
    build_page(index)
    print("index  : %d sets, %d pieces" % (len(index["sets"]), len(index["pieces"])))


def cmd_build():
    index = build_index()
    cards = build_page(index)
    print("bank: %d sets, %d pieces (%d cards)" % (len(index["sets"]), len(index["pieces"]), cards))
    print("  index : %s" % os.path.relpath(INDEX, HERE))
    print("  page  : %s" % os.path.relpath(PAGE, HERE))


def cmd_list(slot=None, tag=None, set_id=None, species=None, section=None):
    index = read_json(INDEX)
    chosen = select(index, slot, tag, set_id, species, section)
    print("%-26s %-8s %-7s %-8s %6s %-12s %s"
          % ("id", "section", "slot", "species", "cells", "anchor", "tags"))
    for e in chosen:
        print("%-26s %-8s %-7s %-8s %2dx%-3d %-12s %s"
              % (e["id"], e.get("section", "-"), e["slot"], e["species"] or "-",
                 e["w"], e["h"],
                 "%d,%d" % (e["anchor"]["x"], e["anchor"]["y"]), " ".join(e["tags"])))
    print("\n%d pieces%s" % (len(chosen),
                             " of %d" % len(index["pieces"]) if len(chosen) != len(index["pieces"]) else ""))


def cmd_export(out, slot=None, tag=None, set_id=None, with_shadows=True, section=None):
    index = read_json(INDEX)
    chosen = select(index, slot, tag, set_id, section=section)
    ids = {e["id"] for e in chosen}
    payload = {
        "version": 1,
        "generator": "bank.py export",
        "from": sorted({e["set"] for e in chosen}),
        "filter": {k: v for k, v in (("slot", slot), ("tag", tag), ("set", set_id)) if v},
        "cell": index["sets"][0]["cell"] if index["sets"] else None,
        "floorTone": index["sets"][0]["floorTone"] if index["sets"] else None,
        "shadowInk": index["sets"][0]["shadowInk"] if index["sets"] else None,
        "pieces": [],
    }
    for e in chosen:
        st = read_json(os.path.join(BANK, e["file"]))
        for p in st["pieces"]:
            if p["id"] == e["id"]:
                payload["pieces"].append(p)
            elif with_shadows and e.get("shadow") == p["id"] and p["id"] in ids:
                payload["pieces"].append(p)
    for e in chosen:
        if with_shadows and e.get("shadow") and e["shadow"] not in ids:
            st = read_json(os.path.join(BANK, e["file"]))
            for p in st["pieces"]:
                if p["id"] == e["shadow"] and all(q["id"] != p["id"] for q in payload["pieces"]):
                    payload["pieces"].append(p)
    write_json(out, payload)
    print("exported %d pieces -> %s (%.0f KB)" % (len(payload["pieces"]),
                                                  os.path.relpath(out, HERE),
                                                  os.path.getsize(out) / 1024.0))


def cmd_check():
    index = read_json(INDEX)
    problems = []
    seen_ids, seen_hashes = {}, {}
    for e in index["pieces"]:
        if e["id"] in seen_ids:
            problems.append("duplicate id %s" % e["id"])
        seen_ids[e["id"]] = e
        seen_hashes.setdefault(e["hash"], []).append(e["id"])
        path = os.path.join(BANK, e["file"])
        if not os.path.exists(path):
            problems.append("%s: missing file %s" % (e["id"], e["file"]))
            continue
        st = read_json(path)
        piece = next((p for p in st["pieces"] if p["id"] == e["id"]), None)
        if piece is None:
            problems.append("%s: absent from %s" % (e["id"], e["file"]))
            continue
        if piece_hash(piece) != e["hash"]:
            problems.append("%s: hash mismatch (set file changed)" % e["id"])
        if (piece["w"], piece["h"], piece["anchor"]) != (e["w"], e["h"], e["anchor"]):
            problems.append("%s: geometry in the index differs from the set" % e["id"])
        if e["kind"] == "prop":
            if e.get("shadow") not in seen_ids and e.get("shadow") not in {p["id"] for p in st["pieces"]}:
                problems.append("%s: shadow %s not in the bank" % (e["id"], e.get("shadow")))
            for t in e["tags"]:
                if t not in index["tags"]:
                    problems.append("%s: tag %s missing from the index" % (e["id"], t))
    dupes = {h: ids for h, ids in seen_hashes.items() if len(ids) > 1}
    for h, ids in dupes.items():
        problems.append("identical pieces: %s (they are the same art)" % ", ".join(ids))
    page = os.path.exists(PAGE) and os.path.getsize(PAGE) > 1000
    if not page:
        problems.append("bank.html missing or empty -- run bank.py build")
    print("bank check: %d sets, %d pieces, %d tags%s"
          % (len(index["sets"]), len(index["pieces"]), len(index["tags"]),
             ", %d identical pairs" % len(dupes) if dupes else ""))
    for p in problems:
        print("  FAIL %s" % p)
    if problems:
        sys.exit(1)
    print("  ok: every indexed piece resolves in its set file, hashes match, no duplicates")


def main():
    ap = argparse.ArgumentParser(description="the piece library")
    ap.add_argument("command", choices=["ingest", "build", "list", "check", "export"])
    ap.add_argument("path", nargs="?", default=DEFAULT_SET)
    ap.add_argument("--slot")
    ap.add_argument("--tag")
    ap.add_argument("--set")
    ap.add_argument("--species")
    ap.add_argument("--section", choices=[k for (k, _l, _s) in SECTIONS],
                    help="cena (paisagem e natureza) ou itens (inventário)")
    ap.add_argument("--out", default=os.path.join(HERE, "game.json"))
    args = ap.parse_args()

    if args.command == "ingest":
        cmd_ingest(args.path)
    elif args.command == "build":
        cmd_build()
    elif args.command == "list":
        cmd_list(args.slot, args.tag, args.set, args.species, args.section)
    elif args.command == "check":
        cmd_check()
    else:
        cmd_export(args.out, args.slot, args.tag, args.set, section=args.section)


if __name__ == "__main__":
    main()
