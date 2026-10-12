# artforge

Gerador de **peças de arte em texto** para jogos isométricos de grade de caracteres (o motor é o
[isoforge](../isoforge/)). Uma **peça** é o que o motor consome: uma grade pequena de (glifo, cor) mais
uma **âncora** — a célula onde a peça toca o chão.

Primeiro conjunto: **árvores estáticas**, 8 espécies × 3 tamanhos = 24 peças.

```bash
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 artforge.py            # gera as peças
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/audit.py         # 25 checagens
open trees.html                                                            # ou dois cliques
```

- `artforge.py` — o gerador. Determinístico: mesma semente, mesmos bytes.
- `assets/trees.json` — o catálogo, o contrato com o motor.
- `trees.html` — a folha de contato para olhar (abre offline, um arquivo, sem dependência).
- `tools/audit.py` — invariantes do catálogo + medição no navegador + medição nos pixels.
- `reports/` — screenshot e um recorte por painel, para inspeção visual.

## A peça (contrato)

```json
{ "id": "tree.oak.medium", "kind": "prop", "w": 12, "h": 15,
  "anchor": { "x": 6, "y": 14 },
  "frames": 1, "directions": 1,
  "cells": [ { "g": "  I@MKYZ1u", "c": ["", "", "#5b8c3f", …] }, … ] }
```

`cells` é linha a linha: `g` é a string de glifos, `c` a cor de cada célula (`""` = vazia, e o motor
deixa o fundo aparecer). `anchor` é a coluna do tronco na última linha — o motor posiciona a peça pelo
pé, não pelo centro da caixa (a palmeira entorta, e o corte desloca a coluna). `frames` e `directions`
já estão no contrato para o dia em que a peça animar.

## Pipeline

Desenha em **PIL 4× (supersampling)** → **média de área** (`Image.BOX`) para a grade de caracteres →
**glifo pela luminância** com auto-níveis por peça → **cor média** quantizada de 4 em 4. É o mesmo
caminho do navio pirata (`ascii-art/references/color-html-pipeline.md`).

## Regras que custaram iteração

1. **Desenhe em unidade de célula, nunca em pixel supersampleado.** Uma célula tem `UX = CELL_W * SS`
   pixels de largura no canvas. Tudo que eu desenhei com menos de ~0,6 célula (tronco, galho, fronde)
   foi dissolvido pela média de área e sumiu da peça pronta: o carvalho saiu com copa e sem tronco, o
   pinheiro com o miolo vazio, a árvore seca como um poste.
2. **O pé da peça é tinta por construção.** Depois de desenhar, um retângulo de contato é carimbado na
   coluna da âncora. Antes disso o arbusto simplesmente flutuava (última linha vazia) — peça que flutua
   no motor é defeito silencioso, e não se aposta na geometria para evitá-lo.
3. **O centro do tronco fica no centro de uma CÉLULA, não na divisa.** `cx = (âncora + 0.5) * UX`. Na
   divisa o tronco se divide em duas células meio-iluminadas e o contato cai uma coluna ao lado.
4. **Auto-níveis por peça antes de escolher o glifo.** A rampa de 91 caracteres sobre cor escura devolve
   pontuação esparsa: casca de luminância 82 mapeia para `.`. Esticar a peça para o próprio p02..p99 é o
   que faz a massa ler como massa. E o piso do auto-nível **não pode apagar** célula que passou no teste
   de vazio — era assim que o pé sumia.
5. **O boost é o do motor, não o do teste de olhar.** `sat 1.24 · ganho 1.60 · lift 15`. Com o boost
   fraco (`ganho 1.06 · lift 5`) a tinta ficou em p10 17 / p50 73 e sujeito fino (seca, palmeira) sumia
   na página; com o do motor, p10 25 / p50 112. Medido nas duas direções, não escolhido no gosto.
6. **Frondes rombas, não agulhas.** Fronde afinando em ponta amostra para células soltas e a coroa
   deixa de ler como leque. Lâmina com ponta de 42% da base, mais uma "saia" de frondes mortas sob a
   coroa, é o que liga a coroa ao tronco.
7. **Corte justo no bbox.** A peça sai do gerador com a caixa exata do desenho; o tamanho da caixa de
   desenho só controla o detalhe, não o tamanho final.

## Verificado (25/25)

| medida | resultado |
|---|---|
| peças | 24 (8 espécies × 3 tamanhos), semente 20261012 |
| determinismo | mesma semente → **bytes idênticos** (41.893 B) |
| âncora | célula da âncora tinta em 24/24, contato em **uma única corrida** passando pela âncora |
| linha de base | as três árvores param na **mesma linha**, espalhamento de 3 px (uma linha = 19 px, medido nos pixels) |
| tinta | p10 25 · p25 51 · **p50 112**; quartil claro ≥ 66 em 24/24 |
| paleta | 1.017 cores, p90 **198**; 8 paletas distintas; outono 39° contra carvalho 105° na tela |
| página | 66 KB, sem canvas, sem imagem, sem requisição externa; sem overflow em 1440×900 e 390×844 |

Checagem que nunca falhou não prova nada: cada limiar aqui tem o valor da regressão ao lado (o boost
fraco medido em 17 / 35 / 73), e o número da tinta é o **quartil claro**, não a mediana — a mediana de
uma espécie rarefeita mede a magreza do sujeito, não se a tinta aparece.

## A página

Uma faixa por espécie, as três árvores apoiadas na mesma linha de base, com a altura em células e px.
Dois botões: **cores** (desliga a cor e deixa só o glifo, para julgar a silhueta) e **linha de base**.

## Falta

- Animação: `frames`/`directions` estão no contrato e não há nenhuma peça com mais de um quadro —
  é o próximo eixo (herói, monstro, tocha).
- Espécies: piso (grama, terra, areia), bloco (penhasco, muro) e mancha (sombra, trilha) são outros
  tipos de peça, com outras regras — a sombra, por exemplo, é plana e nunca oclui.
- O `imagegen` como desenhista: gerar uma referência e passar pelo mesmo conversor, para comparar com o
  procedural.
- Integração: o isoforge ainda espera `assets/art.json` na âncora `ART_TEMPLATES`; falta o adaptador
  que lê este catálogo.
