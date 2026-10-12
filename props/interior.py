#!/usr/bin/env python3
"""interior -- props de INTERIOR para o cenário do artforge: os móveis da casa.

Mesmo problema do resto dos props: o objeto fica num tile, tem pé e sombra de
contato. O que muda é a ESCALA DA LEITURA -- um móvel é grande e tem partes
finas, e no grid de caracteres uma parte fina simplesmente some. Por isso:

  * tudo aqui e desenhado em CELULAS (nunca pixel), pelo kit de weapons.py;
  * nenhum traco e mais fino que ~0.4 celula (os pes do primeiro rascunho
    desapareciam na amostragem);
  * luz em cima/na esquerda (metal_light), corpo (metal), sombra embaixo/na
    direita e nas juntas (metal_dark) -- uma cor so le como mancha.

Este arquivo NAO substitui as rotinas de scenery.py: ele as ACRESCENTA. A lista
NEW_PROPS de baixo usa exatamente o mesmo formato da tabela PROPS de la, entao
o build do cenário pode somar as duas.

Uso:
    PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 interior_selftest.py
"""

import random

import artforge as af
import weapons as wk
import scenery as sc

# O kit de desenho (celula, nao pixel) -- um lugar so para o aspecto da celula, e a
# largura de traco vem do kit porque ela tem de acompanhar a escala da tile.
from props.kit import cline, crect, cpoly, cellipse, circle       # noqa: E402
cellipse = wk.cellipse
circle = wk.circle

GROUND = sc.GROUND


# --- madeira: o material de todos os moveis ------------------------------------
def wood():
    return GROUND["wood"]


# --- 1. Mesa --------------------------------------------------------------------
def p_table(d, w, h):
    """Tampo e quatro pes. O tampo e a leitura: face de cima clara, borda de frente
    escura, o avental embaixo separando o tampo dos pes. Os pes de tras entram
    escuros e recuados, os da frente claros -- e o que da a profundidade."""
    W = wood()
    cx = w / 2.0
    x0, x1 = w * 0.055, w * 0.945            # o tampo, de ponta a ponta
    top = h * 0.09
    slab = h * 0.19                          # espessura do tampo
    base = h - 0.35                          # o pe toca aqui
    lw = w * 0.085                           # largura do pe (>= 1 celula sempre)

    # pes de tras: recuados, escuros
    for bx in (cx - w * 0.28, cx + w * 0.28):
        crect(d, bx - lw * 0.5, top + slab * 0.4, bx + lw * 0.5, base, W["metal_dark"])

    # tampo: corpo, face de cima clara, borda de frente escura
    crect(d, x0, top, x1, top + slab, W["metal"])
    crect(d, x0, top, x1, top + slab * 0.44, W["metal_light"])
    crect(d, x0, top + slab * 0.72, x1, top + slab, W["metal_dark"])
    # avental: a sombra sob o tampo que separa tampo e pes
    crect(d, x0, top + slab, x1, top + slab + 0.4, W["metal_dark"])

    # pes da frente: claros, com aresta interna escura
    for lx in (x0 + w * 0.07, x1 - w * 0.07):
        crect(d, lx - lw * 0.5, top + slab, lx + lw * 0.5, base, W["metal"])
        crect(d, lx - lw * 0.5, top + slab, lx - lw * 0.10, base, W["metal_light"])
        crect(d, lx + lw * 0.28, top + slab, lx + lw * 0.5, base, W["metal_dark"])


# --- 2. Banquinho ---------------------------------------------------------------
def p_stool(d, w, h):
    """Assento e tres pes A B E R T O S. Pequeno: o que le e o contraste e o vazio
    entre os pes, nao o detalhe. O pe de tras e fino, escuro e mais curto -- se ele
    for cheio ate o chao, o banquinho vira um poste macico. O vao claro entre os tres
    pes e o que faz ler 'banquinho' e nao 'toco'."""
    W = wood()
    cx = w / 2.0
    s0, s1 = w * 0.05, w * 0.95
    top = h * 0.20
    slab = h * 0.16
    base = h - 0.45

    # pe de tras: fino, no centro, escuro, e mais curto que os da frente
    crect(d, cx - w * 0.055, top + slab, cx + w * 0.055, base - h * 0.30,
          W["metal_dark"])

    # pes da frente: finos, abertos para fora (o desenho que distingue do banco reto)
    for side in (-1, 1):
        tx = cx + side * w * 0.15
        bx = cx + side * w * 0.28
        hwt, hwb = w * 0.060, w * 0.075
        cpoly(d, [(tx - hwt, top + slab * 0.7), (tx + hwt, top + slab * 0.7),
                  (bx + hwb, base), (bx - hwb, base)], W["metal"])
        cpoly(d, [(tx - side * hwt, top + slab * 0.7),
                  (tx - side * w * 0.015, top + slab * 0.7),
                  (bx - side * w * 0.020, base), (bx - side * hwb, base)],
              W["metal_light"])
        cpoly(d, [(tx + side * w * 0.020, top + slab * 0.7),
                  (tx + side * hwt, top + slab * 0.7),
                  (bx + side * hwb, base), (bx + side * w * 0.020, base)],
              W["metal_dark"])

    # assento: corpo, cima clara, frente escura
    crect(d, s0, top, s1, top + slab, W["metal"])
    crect(d, s0, top, s1, top + slab * 0.40, W["metal_light"])
    crect(d, s0, top + slab * 0.70, s1, top + slab, W["metal_dark"])


# --- 3. Cama --------------------------------------------------------------------
def p_bed(d, w, h):
    """Espaldar a esquerda, colchao e cobertor de pano (o azul contrasta com a
    madeira), travesseiro claro na cabeceira, saia de madeira e quatro pes."""
    W = wood()
    C = GROUND["cloth"]
    P = GROUND["plaster"]
    base = h - 0.5
    fx0, fx1 = w * 0.16, w * 0.975           # a caixa do leito

    # pes de tras: recuados e escuros
    for lx in (w * 0.25, w * 0.90):
        crect(d, lx - w * 0.026, h * 0.60, lx + w * 0.026, base, W["metal_dark"])

    # espaldar: corpo, face esquerda clara, aresta direita escura, remate no topo
    hb0, hb1 = w * 0.030, w * 0.165
    crect(d, hb0, h * 0.09, hb1, h * 0.74, W["metal"])
    crect(d, hb0, h * 0.09, hb0 + (hb1 - hb0) * 0.42, h * 0.74, W["metal_light"])
    crect(d, hb1 - (hb1 - hb0) * 0.26, h * 0.09, hb1, h * 0.74, W["metal_dark"])
    crect(d, hb0, h * 0.09, hb1, h * 0.09 + 0.55, W["metal_light"])

    # saia de madeira do leito
    crect(d, fx0, h * 0.60, fx1, h * 0.78, W["metal"])
    crect(d, fx0, h * 0.60, fx1, h * 0.645, W["metal_light"])
    crect(d, fx0, h * 0.745, fx1, h * 0.78, W["metal_dark"])

    # colchao + cobertor: cima clara, borda de baixo escura
    crect(d, fx0, h * 0.44, fx1, h * 0.60, C["metal"])
    crect(d, fx0, h * 0.44, fx1, h * 0.485, C["metal_light"])
    crect(d, fx0, h * 0.575, fx1, h * 0.60, C["metal_dark"])
    # a dobra do cobertor, descendo pela frente
    crect(d, w * 0.44, h * 0.44, w * 0.475, h * 0.78, C["metal_dark"])
    crect(d, w * 0.475, h * 0.44, w * 0.50, h * 0.78, C["metal_light"])

    # travesseiro na cabeceira: claro, com realce
    cellipse(d, w * 0.245, h * 0.42, w * 0.105, h * 0.10, P["metal"])
    cellipse(d, w * 0.235, h * 0.40, w * 0.060, h * 0.055, P["metal_light"])

    # pes da frente: claros
    for lx in (w * 0.21, w * 0.94):
        crect(d, lx - w * 0.028, h * 0.78, lx + w * 0.028, base, W["metal"])
        crect(d, lx - w * 0.028, h * 0.78, lx - w * 0.006, base, W["metal_light"])


# --- 4. Estante -----------------------------------------------------------------
def p_shelf(d, w, h):
    """Caixa alta aberta: dois montantes, prateleiras e livros. O fundo NAO e
    macico -- os vaos vazios sao o que faz a estante ler como estante e nao como
    um bloco. Os livros (pano, chama, capim, ferro, cal) dao a cor e a leitura."""
    W = wood()
    P = GROUND["plaster"]
    I = GROUND["iron"]
    C = GROUND["cloth"]
    F = GROUND["flame"]
    G = GROUND["grass"]
    cols = (C, F, G, I, P)

    top, bot = h * 0.05, h - 0.5
    p0, p1 = w * 0.045, w * 0.165            # montante esquerdo
    q0, q1 = w * 0.835, w * 0.955            # montante direito

    # montantes: corpo, face esquerda clara, aresta direita escura
    for (a, b) in ((p0, p1), (q0, q1)):
        crect(d, a, top, b, bot, W["metal"])
        crect(d, a, top, a + (b - a) * 0.38, bot, W["metal_light"])
        crect(d, b - (b - a) * 0.30, top, b, bot, W["metal_dark"])

    # tampa de cima e fundo do movel
    crect(d, p0, top, q1, top + h * 0.045, W["metal"])
    crect(d, p0, top, q1, top + h * 0.020, W["metal_light"])
    crect(d, p0, bot - h * 0.045, q1, bot, W["metal"])
    crect(d, p0, bot - h * 0.045, q1, bot - h * 0.018, W["metal_dark"])

    inner0, inner1 = p1, q0
    n = 4                                    # 4 vaos = 4 fileiras de livros
    board_th = h * 0.028

    # tabuas internas (a de cima e a de baixo ja foram desenhadas)
    for k in range(1, n):
        by = top + (bot - top) * (k / float(n))
        crect(d, inner0, by, inner1, by + board_th * 0.55, W["metal_light"])
        crect(d, inner0, by + board_th * 0.35, inner1, by + board_th, W["metal_dark"])

    # livros: EM PE sobre a tabua de baixo do vao, subindo ate a de cima. Deixando AR
    # de proposito -- fileira encostada na outra laria a estante como bloco (dava 82%).
    rng = random.Random(4242)                # determinismo: semente fixa
    for k in range(n):
        ceil = top + (bot - top) * (k / float(n))
        floor = top + (bot - top) * ((k + 1) / float(n))
        room = (floor - ceil) - board_th - 0.30
        if room <= 0.5:
            continue
        x = inner0 + 0.55
        while x < inner1 - 0.6:
            bw = rng.uniform(0.50, 0.78)
            bh = rng.uniform(0.35, 0.55) * room
            col = cols[rng.randrange(len(cols))]
            # as faixas de luz/sombra do livro tem PISO em celulas: escaladas so
            # pela largura elas cairiam abaixo de 0.15 celula nos livros finos.
            lw = max(0.20, bw * 0.34)
            dw = max(0.17, bw * 0.24)
            crect(d, x, floor - bh, x + bw, floor, col["metal"])
            crect(d, x, floor - bh, x + lw, floor, col["metal_light"])
            crect(d, x + bw - dw, floor - bh, x + bw, floor, col["metal_dark"])
            x += bw + rng.uniform(0.42, 0.92)


# --- a lista, no formato da tabela PROPS de scenery.py --------------------------
# (id, rotulo, especie, caixa em celulas, rotina, raio da sombra, material, pe)
NEW_PROPS = [
    ("prop.table", "Mesa", "table", (12, 8), p_table, 4.0, "wood", "wood"),
    ("prop.stool", "Banquinho", "stool", (7, 7), p_stool, 2.6, "wood", "wood"),
    ("prop.bed", "Cama", "bed", (14, 9), p_bed, 4.2, "wood", "wood"),
    ("prop.shelf", "Estante", "shelf", (12, 14), p_shelf, 3.4, "wood", "wood"),
]
