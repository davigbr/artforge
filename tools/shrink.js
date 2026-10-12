// artforge -- runtime piece shrink, the mirror of weapons.shrink() in Python.
//
// An inventory slot will not always match an authored size, so the engine needs a
// fallback: average a block of cells into one. It is cheap (one pass over the grid)
// and it loses the signature first -- a 1-cell crossguard averaged into the blade
// stops being a crossguard. That is why the authored sizes exist; this is the bridge.
//
// The glyph and the colour are chosen with the SAME rules as the Python side, down
// to the gamma and the quantisation, so the two can be compared cell by cell.

var SHRINK_KIT = (function () {
  function luminance(c) { return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; }

  function hexToRgb(hex) {
    return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  }

  function rgbToHex(rgb) {
    return "#" + rgb.map(function (v) {
      var s = Math.max(0, Math.min(255, Math.round(v))).toString(16);
      return s.length === 1 ? "0" + s : s;
    }).join("");
  }

  function quantise(rgb, q) {
    // Python's round() is half-to-even and int() truncates; JS rounds half up and
    // has no trunc-vs-round distinction at 0.5. Mirroring both keeps the glyph the
    // same on the two sides instead of "almost the same".
    return rgb.map(function (v) {
      var x = v / q, f = Math.floor(x), d = x - f;
      var r = d > 0.5 ? f + 1 : (d < 0.5 ? f : (f % 2 === 0 ? f : f + 1));
      return Math.min(255, r * q);
    });
  }

  function glyphFor(lum, lo, hi, ramp, gamma) {
    var span = Math.max(1, hi - lo);
    var t = Math.min(1, Math.max(0, (lum - lo) / span));
    var k = Math.max(1, Math.min(ramp.length - 1, Math.floor(Math.pow(t, gamma) * ramp.length)));
    return ramp[k];
  }

  function shrink(piece, factor, ramp, gamma, quant) {
    var src = piece.cells, w = piece.w, h = piece.h;
    var lo = piece.levels[0], hi = piece.levels[1];
    var ow = Math.max(1, Math.floor(w / factor));
    var oh = Math.max(1, Math.floor(h / factor));
    var rows = [];
    for (var by = 0; by < oh; by++) {
      var glyphs = "", colors = [];
      for (var bx = 0; bx < ow; bx++) {
        var sum = [0, 0, 0], n = 0;
        for (var y = by * factor; y < Math.min(h, (by + 1) * factor); y++) {
          for (var x = bx * factor; x < Math.min(w, (bx + 1) * factor); x++) {
            var hex = src[y].c[x];
            if (src[y].g[x] === " " || !hex) continue;
            var rgb = hexToRgb(hex);
            sum[0] += rgb[0]; sum[1] += rgb[1]; sum[2] += rgb[2];
            n++;
          }
        }
        if (!n) { glyphs += " "; colors.push(""); continue; }
        // Truncate the channels BEFORE measuring the luminance: Python does
        // (int(tot/n)) and a float average here flips the glyph on borderline cells.
        var avg = [Math.trunc(sum[0] / n), Math.trunc(sum[1] / n), Math.trunc(sum[2] / n)];
        glyphs += glyphFor(luminance(avg), lo, hi, ramp, gamma);
        colors.push(rgbToHex(quantise(avg, quant)));
      }
      rows.push({ g: glyphs, c: colors });
    }
    return { w: ow, h: oh, cells: rows, levels: piece.levels };
  }

  // One span per run of equal colour, empty cells left bare -- the same rule the
  // generator uses, so the page costs what the art costs.
  function toHtml(piece, escape) {
    var out = [];
    for (var y = 0; y < piece.h; y++) {
      var glyphs = piece.cells[y].g, colors = piece.cells[y].c;
      var parts = "", start = 0, key = null;
      for (var x = 0; x <= glyphs.length; x++) {
        var col = x < glyphs.length ? colors[x] : "\u0000";
        if (col !== key) {
          if (key !== null && x > start) {
            var text = escape ? escape(glyphs.slice(start, x)) : glyphs.slice(start, x);
            parts += (key === "" || !text.trim()) ? text
              : '<i style="color:' + key + '">' + text + "</i>";
          }
          start = x; key = col;
        }
      }
      out.push(parts);
    }
    return out.join("\n");
  }

  return { shrink: shrink, toHtml: toHtml, luminance: luminance, glyphFor: glyphFor };
})();

// The live panel: pick an item, pick a factor, watch the large piece adapt.
function mountShrinkLab(data) {
  var out = document.getElementById("liveOut");
  var info = document.getElementById("liveInfo");
  if (!out || !data || !data.pieces) return;
  var state = { item: data.pieces[0].id, factor: 2 };

  function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function render() {
    var piece = null;
    for (var i = 0; i < data.pieces.length; i++) if (data.pieces[i].id === state.item) piece = data.pieces[i];
    if (!piece) return;
    var shrunk = SHRINK_KIT.shrink(piece, state.factor, data.ramp, data.gamma, data.quant);
    out.innerHTML = SHRINK_KIT.toHtml(shrunk, escapeHtml);
    var before = piece.w * piece.h, after = shrunk.w * shrunk.h;
    info.textContent = piece.id + " · " + piece.w + "×" + piece.h + " → " + shrunk.w + "×" + shrunk.h
      + " células (÷" + state.factor + "), " + before + " → " + after + " células"
      + " · o glifo e a cor saem da média do bloco, com as mesmas regras do Python.";
  }

  function button(label, kind, value) {
    var b = document.createElement("button");
    b.className = "f";
    b.textContent = label;
    b.setAttribute("data-" + kind, value);
    b.addEventListener("click", function () { state[kind] = value; sync(); });
    return b;
  }

  var bar = document.getElementById("liveItems");
  data.pieces.forEach(function (p) { bar.appendChild(button(p.label || p.id, "item", p.id)); });
  var factors = document.getElementById("liveFactors");
  [2, 3, 4].forEach(function (f) { factors.appendChild(button("÷" + f, "factor", f)); });

  function sync() {
    Array.prototype.forEach.call(document.querySelectorAll(".f"), function (b) {
      var on = (b.dataset.item && b.dataset.item === state.item)
        || (b.dataset.factor && Number(b.dataset.factor) === state.factor);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    render();
  }
  sync();
}
