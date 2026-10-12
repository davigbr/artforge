# artforge

Gerador de **peças de arte em texto** para jogos isométricos de grade de caracteres (o motor é o
[isoforge](../isoforge/)). Uma **peça** é o que o motor consome: uma grade pequena de (glifo, cor) mais
uma **âncora** — a célula que vai para o centro do tile.

Primeiro conjunto: **árvores estáticas** — 8 espécies × 3 tamanhos = **24 props** + **18 discos** de
contato (a sombra, que é uma peça separada).

Segundo conjunto: **armas e armaduras** — 28 itens × 3 resoluções = **84 ícones** (12 armas; 6 elmos —
barrete, elmo de ferro, fechado, com chifres, capuz, coroa; 6 peças de torso — gibão, cota de malha,
peitoral, escamas, túnica, peitoral dourado; 3 escudos — redondo, em gota, torre; 1 anel).

```bash
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 artforge.py            # gera as árvores
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/audit.py         # 34 checagens
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 weapons.py             # gera as armas
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 tools/items_audit.py   # 24 checagens
open trees.html ; open weapons.html                                        # ou dois cliques
```

- `artforge.py` — o gerador das árvores. Determinístico: mesma semente, mesmos bytes.
- `weapons.py` — o gerador das armas (importa as primitivas de `artforge.py`: mesma amostragem, mesma tinta).
- `tools/shrink.js` — a redução em tempo real, embutida na página (a página é um arquivo só).
- `assets/trees.json`, `assets/weapons.json` — os conjuntos que os geradores escrevem.
- `bank.py` + `bank/` — **o banco de peças**: índice de tudo, com tags e hash de conteúdo.
- `trees.html`, `weapons.html` — as folhas de contato (abrem offline, um arquivo cada).
- `bank/bank.html` — o navegador do banco: filtra por slot, tag e busca.
- `tools/audit.py`, `tools/items_audit.py` — invariantes do catálogo + medição no navegador + nos pixels.
- `tools/bank_audit.py` — o banco medido no navegador (os filtros contados contra o índice).
- `reports/` — screenshot e um recorte por painel, para inspeção visual.

## O banco de peças

O conjunto é o que um script produziu para um jogo; o banco é o **estoque**. Ele guarda os arquivos de
conjunto sem tocá-los, indexa cada peça com o que outro projeto precisa para escolher (slot, espécie,
tamanho, tags, tamanho em células, **âncora**, sua mancha) e dá a cada peça um **hash de conteúdo**, para
a mesma peça chegando de dois conjuntos ser reconhecida como uma só coisa.

```bash
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py ingest          # entra o conjunto
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py build           # índice + página
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py list --tag conifer
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py check           # o banco confere consigo mesmo
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py export --tag conifer --out pines.json
```

O **slot** é o vocabulário por que o motor desenha, e é por ele que o banco se organiza:

| slot | o que é |
|---|---|
| `piso` | o chão, repetido em todo tile — precisa **emendar consigo mesmo** |
| `bloco` | tile com altura: parede, penhasco, tronco grosso |
| `prop` | objeto parado em cima do tile (uma árvore) |
| `ator` | o que anda e anima |
| `mancha` | plano, desenhado com o piso, **nunca oclui** (a sombra de contato) |
| `efeito` | fogo, fumaça, brilho |
| `icone` | peça de **inventário**: não tem chão, é **centralizada** |

O banco se parte em **duas metades que não se misturam**, e a divisão está no índice (dá para filtrar e
exportar) e na página (uma seção cada):

- **cena** — paisagem e natureza: o que é *colocado num tile* e tem de compor com o vizinho (o piso emenda
  consigo mesmo, o prop pisa no chão, a mancha vai junto com o piso);
- **itens** — o que é *uma figura numa lista* e não compõe com nada (o slot `icone`).

```bash
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py list --section itens    # 84 peças
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python3 bank.py export --section itens --out itens.json
```

Na página, **um cartão por coisa**: as três resoluções de um item (ou de uma árvore) são um cartão só, que
abre na **maior** — a pequena é outro desenho, não uma miniatura — e as outras ficam em botões ao lado. Sem
JavaScript a página mostra tudo, com as três resoluções abertas.

O `check` já pagou por si: na primeira execução ele acusou **seis pares de sombras idênticas** — a sombra
estava sendo gerada por árvore, e `oak.small` e `autumn.small` produziam o mesmo desenho sob ids
diferentes. A mancha é função do **disco**, não da espécie: agora o conjunto emite **18 discos
compartilhados** para 24 props (`shadow.disc.r4.6` e afins) e o banco não tem arte repetida.

`bank/bank.html` mostra tudo: um cartão por peça sobre o piso, com o id, o slot, as tags, as dimensões, a
âncora, o hash e um botão que copia o registro da peça para levar para outro jogo. Os filtros são CSS +
JS: sem JavaScript a página mostra o banco inteiro.

## Isometria: as três regras que fazem a peça ler em 3D

A primeira versão lia como adesivo colado de frente, e o motivo é específico: copa redonda. Numa projeção
2:1 a câmera olha **de cima e de lado** — então:

1. **Disco horizontal vira elipse mais larga que alta.** `ISO_FLAT = 0.5` (`isoFlat` no JSON, a mesma
   proporção do losango do tile). Vale para a copa, para a sombra e para o pé do tronco. Copa redonda é o
   que entrega "2D de frente"; a silhueta tem de ser larga e baixa, e a diferença entre espécies vive na
   **largura** e no empilhamento das massas, não na altura.
2. **O tronco é vertical, então ele NÃO encurta** — árvore alta é tronco comprido com copa baixa e larga
   por cima.
3. **Nada está no plano sem pegada no chão.** O tronco termina numa elipse (não cortado pela linha do
   chão) e cada árvore traz a **mancha** de contato, como peça separada.

E a luz vem de **cima**: a face superior é a mais clara. No pinheiro isso é o que faz os anéis lerem como
discos empilhados vistos de cima — a ponta é o que mais recebe luz e cada anel escurece para baixo, porque
o anel de cima sombreia o de baixo. O contrário (ponta escura, base clara) é um triângulo chapado de frente.

**A sombra é uma mancha (decal), não parte do prop.** Ela é plana, desenhada junto com o piso e **nunca
oclui** — é a ordem de desenho do motor (piso → sombra → entidades). A âncora dela é o **centro** do
disco: o disco apoia em volta do ponto que vai para o centro do tile, metade para perto, metade para longe.

## Ícones de item: o item não tem chão

Um item é o **problema inverso** de uma árvore. A árvore é um `prop`: pisa num tile, a âncora é o **pé**, e
a sombra vai junto com o piso. O item é um `icone`: não toca chão nenhum, é **centralizado**, e o que tem
de sobreviver é a **silhueta** — em 5 células de largura uma espada lê pelo contorno ou não lê.

Consequências no código, todas em `weapons.py`:

1. **A âncora é o centro da caixa**, não a última linha. E o desenho é **deslocado depois da amostragem**
   até a caixa da silhueta cair no meio da caixa da peça (`shift_grid`) — o eixo em que a peça se centra é o
   da silhueta, que é o que o olho lê como "centrado". O deslocamento é em células inteiras, então ele
   **itera duas vezes**: uma passada só pode parar a uma célula do alvo (foi assim que a alabarda grande
   ficou 1 célula fora).
2. **A caixa nunca é cortada.** Numa árvore o `bbox` justo é a regra (o tamanho da caixa de desenho só
   controla o detalhe). Num ícone a caixa **declara a resolução** — cortar jogaria fora exatamente o que a
   caixa foi escolhida para ser.
3. **Silhueta cheia precisa de margem de 1 célula na caixa.** Escudo e elmo desenhados até a borda da caixa
   saíam com **91–95 % de tinta** — um retângulo sólido, sem forma para ler.
4. **Nada de contorno escuro.** O contorno é para fundo claro; o painel é escuro, e a peça brilha por si.
5. **O que é redondo passa pelo `circle()`.** A célula é **1,66× mais alta que larga**, então uma elipse de
   raios iguais em unidades de célula sai **oval na tela** — era por isso que o anel parecia uma bola
   achatada. O `circle()` faz a correção em um lugar só, e cada círculo desenhado fica **declarado no
   JSON** (`circles`), porque o que é redondo **não se confere numa grade de células** — confere-se no
   número, como o 2:1 da mancha. Cuidado com o caso oposto: o disco *visto de cima* (copa, sombra) é
   achatado **de propósito** — isso é a isometria, e mora no `ISO_FLAT`.
6. **O tamanho da caixa responde ao traço, inclusive quando o traço é um buraco.** O anel pequeno em 5×5
   saía como um borrão porque o **furo** ficava com menos de uma célula (a célula tem 6,6 × 11 px, não há
   onde pôr um furo de 3 px). Com 7×7 o furo aparece. Sem grade de slots, quem decide é o traço.
7. **O aspecto se confere em PIXEL, não em célula.** Uma caixa quadrada **em células** é 1,66:1 **na tela** —
   foi assim que os seis peitorais ficaram com 60 × 99 px, uma coluna onde vai um torso, e o elmo fechado
   com 0,77 onde um elmo é ~0,9. Cada item **declara o aspecto pretendido** (`aspect` no JSON) e a auditoria
   mede a caixa de tinta em pixels contra ele (±18%). Sem o número declarado não há como pegar a regressão:
   "a caixa parece certa" não diz nada sobre como a peça lê.

## O tamanho responde à legibilidade, não a um footprint

A primeira versão deste conjunto era um **inventário de grade quadrada** (estilo Diablo): cada item ocupava
N×M slots e o tamanho pequeno era o que cabia no footprint. Isso foi **abandonado**, e a consequência é
direta: sem grade não há footprint, e o tamanho pequeno passa a responder a uma pergunta só — **cabe o
traço que faz o item ser o que é?** (na espada a guarda, no elmo a fenda da viseira).

Foi o que consertou os dois defeitos que o slot apertava, e os dois estão no código, não no olho:

- a espada pequena saiu de 4×9 para **6×13** e a guarda passou a ser uma barra de 5 células contra uma
  lâmina de 2 — antes ela lia como "arma de lâmina" (adaga, espada ou estaca);
- a caixa pequena tem um **piso de legibilidade** (≥ 5 células no lado curto), checado na auditoria, e a
  espada **mantém a guarda mais larga que a própria lâmina em todos os três tamanhos** (medido, não
  conferido no olho).

## As três resoluções, e a redução em tempo real

"Faça menor" em arte de texto não é um problema, são dois:

| | o que é | o que custa |
|---|---|---|
| **reduzir** (`shrink`) | média de blocos 2×2 da grade maior → uma célula, glifo pela luminância média | **o contraste interno**: a guarda de 1 célula e o miolo claro da lâmina param de ser diferentes dos vizinhos |
| **desenhar menor** | a caixa é parâmetro e o que se desenha também | trabalho: um desenho por tamanho |

O conjunto faz as duas: cada item tem **pequena, média e grande desenhadas** (a grande ganha detalhe — o
vão da lâmina, o gume da guarda, as voltas do punho — porque há células para isso), e a página traz o
`shrink` **rodando ao vivo no navegador** para o tamanho que não casa com nenhuma das três.

A cadeia é **1× / 1,5× / 2×** de propósito: a grande é exatamente o dobro da pequena nos dois eixos, então
`shrink(grande, 2)` cai **na grade da pequena** e as duas se comparam célula a célula. O `tools/shrink.js`
decide glifo e cor com as **mesmas regras** do `weapons.shrink` do Python (mesma rampa, mesma gama,
mesma quantização — inclusive o `round` meio-para-par do Python), e a auditoria cobra isso: as duas grades
têm de sair **glifo por glifo iguais**.

O que a medição diz (28 itens, pequena desenhada × grande reduzida na mesma grade):

| medida | resultado |
|---|---|
| contraste interno (desvio-padrão da luminância das células) | **65,6 desenhada · 56,9 reduzida**; nas peças de traço fino 63,2 → 55,4, nas maciças 69,4 → 59,2 |
| tinta | 55 % desenhada · 62 % reduzida — a redução **ganha** tinta em 21 dos 28 |
| onde a redução ganha em contraste | 4 dos 28, todas maciças |

**Duas explicações para o ganho de tinta foram medidas e derrubadas**, e o registro fica para ninguém
repetir a suposição: não é preencher buracos internos (só **1** peça do conjunto tem um, e ela não ganha
tinta ao ser reduzida) e não é dilatação uniforme (só **16** das 28 crescem em silhueta, **7** encolhem).
O que se sustenta é o **contraste**, e é ele que a auditoria afirma. (Uma terceira tentativa, medir a
"quebra entre linhas", também foi descartada: dá **155** no elmo apertado que era o defeito e **85** no
conserto — mede o contrário do que eu queria.)

O eixo que sobrou, e que vale para qualquer redução: **o que a redução come é contraste interno**, e a
redução não substitui a pequena desenhada.

## O motor do isoforge: o que ele exige da arte (revisado no motor 0.7.0)

O motor mudou debaixo deste conjunto e duas coisas dele **obrigaram** mudança aqui:

1. **A resolução da tile é parâmetro, e o projeto de teste fixou a dele.** O motor entrega
   `tileCellsW/tileCellsH/wallHeightCells` e deriva projeção, culling, malha e margem; a
   **cripta** (o projeto de teste) roda `20 × 6` com parede `8` — `20*3/10` e `20*4/10`. O
   conjunto estava em `12 × 4` com parede 4, e 12×4 **nem era um losango 2:1** (12 células
   de largura são 7,2 unidades, 4 de altura são 4: 1,8:1). A regra: `h = w*3/10`. Agora o
   padrão é 20×6/8, e `--tile 10` gera o 10×3/4 original do motor.
2. **A arte escala por um fator, não por uma segunda cópia.** A cripta desenha tudo em
   deslocamentos a partir do centro do tile e multiplica por `ART = tileCellsW / 10`. Este
   conjunto faz igual: as caixas dos props são autorais numa base de 10 células e
   multiplicadas por `ART`, então **um desenho serve as duas resoluções**. Uma largura de
   traço é a exceção — largura está em células, e um traço desenhado para 10 células fica
   com metade da espessura num tile de 20 (medido: sem corrigir isso, mato seco, juncos,
   tocha e escada saíram com 19–22% de tinta contra 33–56% do resto).
3. **O motor tem um slot de ATOR e nada neste projeto produzia um.** O contrato é
   `art.entity[kind] = function (r, ctx)`, e `ctx.entity` traz `facing` (+1 = direita da
   tela), com o pintor espelhando o desenho para −1. Então: **o herói, o esqueleto e o
   carniçal são desenhados de frente para a direita** e a outra face é o espelho.
4. **O tamanho do herói não foi inventado.** A cripta desenha o dela `A(6)` acima do chão
   com `A() = 2` — **12 células** de altura num tile de 20. O `ator.heroi` tem 14 linhas de
   caixa com 12 de tinta. Um ator é uma coisa de tamanho fixo no mundo: ele **não** é
   reescalado com a tile como um prop é.
5. **Um prop pode ser coberto por outro, e isso não é defeito.** O motor desenha por
   profundidade, então props se sobrepõem de verdade numa cena. A checagem de composição
   aceita a célula da âncora de uma peça **ou** a célula de uma peça desenhada depois cuja
   caixa cobre aquele ponto — e informa quantas âncoras foram cobertas. Tratar sobreposição
   legítima como defeito é como uma checagem deixa de significar alguma coisa.

O que **ainda falta para o jogo consumir isto** — e é do lado do jogo, não daqui: o motor
chama `art.floor / art.block / art.prop[kind] / art.entity[kind]`, e hoje a cripta desenha
esses callbacks proceduralmente em JS. Este conjunto entrega as mesmas células como dados
(`assets/scenery.json`, ingestável no banco), então o que falta é um blitter de ~30 linhas
no `art.js` do jogo que leia a grade e pinte célula a célula. **O motor não precisa mudar
nada** para isso: o contrato dele já é o certo (ele sabe a ORDEM e o CULLING, não a arte).

## O cenário: piso, bloco, prop, ator e mancha

`scenery.py` gera o outro conjunto: o que compõe ambiente, interno ou externo. Quatro slots, que são
exatamente os que o motor desenha — **piso** (`tile`), **bloco** (`block`, com altura), **prop** (o que
pisa numa tile) e **mancha** (`decal`, desenhada junto com o piso e que nunca oclui). 35 peças nesta
primeira rodada: 9 pisos, 6 blocos, 15 props, 5 manchas.

A tile é **12 × 4 células** (79,4 × 44,0 px — 2:1 na tela, a proporção da isometria), então o piso de um
ambiente se monta com nada além dele mesmo. O bloco tem a altura da parede do motor (4 células) sobre a
face de cima. O prop ancora no pé, como uma árvore. A mancha carrega o próprio desenho (moita, musgo,
poça, neve) e é pintada com o piso, antes de qualquer coisa pisar nele.

### Regras que custaram iteração (cenário)

1. **O piso emenda com MEIA tile, não com uma.** Com o escalonamento iso o vizinho de uma tile está a
   `(+w/2, +h/2)`, então o campo tem de ser periódico em **(6,2)**, não em (12,4): toda pincelada — cada
   lâmina, cada seixo, cada junta — é desenhada também nos deslocamentos de meia tile. Uma textura com
   período de uma tile inteira encaixa com um degrau nas bordas, invisível numa tile e visível num piso.
2. **A checagem da emenda se faz na COMPOSIÇÃO, não na tile.** A primeira versão media a borda esquerda
   da tile contra a direita — que uma tile iso nunca encosta uma na outra — e devolvia `0,0` para todo
   piso, inclusive para os que não emendavam. A medida que vale: compor o piso *n×n* e **deslocá-lo de
   uma tile**; se o campo é periódico, a figura não muda. Medido: **0 de 108 células** mudam no pior
   piso.
3. **O piso usa a metade baixa da rampa.** Um piso de contraste cheio compete com tudo que está em cima
   dele (medido: os degraus internos da tile, p75 42–84 de luminância, eram da ordem de uma tocha contra
   o chão). O piso é a superfície; o prop é o assunto; a rampa é onde isso se decide.
4. **O bloco é um cubo, não uma parede pintada de plano.** A face de cima é o losango da própria tile
   (12 × 4) e as duas faces laterais descem dela. A primeira versão desenhou o losango 12 × 6: não era
   um losango 2:1, era um bloco em cima de um bloco mais alto.
5. **Peça de mundo não se centraliza na caixa.** `weapons.to_cells` centra a tinta — certo para um
   ícone, porque item não tem chão — e por isso cinco props saíram **flutuando**, com a âncora vazia: a
   centralização empurrava o pé uma linha para cima. `scenery.to_ground` amostra sem deslocar; a caixa é
   a resolução, e o pé é o pé.
6. **O pé é desenhado pelo laço, não por cada rotina.** Traço mais fino que uma célula não sobrevive à
   média de área (haste de cogumelo, ripa de escada) e a peça fica sem contato. O carimbo de contato sai
   uma vez, para todos os props — e no tom **médio** do material: no tom escuro ele ficava abaixo do
   nível de tinta da própria peça (cogumelos, flores, juncos) e a última linha voltava vazia.
7. **A cena compõe na ordem do motor — piso → mancha → sombra → prop — e se verifica pelo encaixe.** A
   checagem é a célula da âncora do prop na composição ser a célula do próprio prop; procurar um trecho
   de caractere no texto acusa sobreposição legítima (o que veio depois desenha por cima) como se fosse
   defeito.
8. **As sombras de contato são EMPRESTADAS do conjunto das árvores.** O banco recusa duas peças com a
   mesma arte, e um disco de raio *r* é a mesma arte em qualquer conjunto: o cenário referencia
   `shadow.disc.rN` do conjunto das árvores em vez de emitir cópias idênticas. Consequência: o conjunto
   das árvores tem de estar ingerido antes (o `bank.py check` cobra isso).

### Verificado no cenário (36/36)

| medida | resultado |
|---|---|
| conjunto | 41 peças (9 piso, 6 bloco, 15 prop, 3 atores, 8 manchas), semente 20261014 |
| resolução | **20 × 6 células com parede de 8** — o `tileCellsW: 20 / tileCellsH: 6 / wallHeightCells: 8` da cripta |
| determinismo | duas corridas frescas → **bytes idênticos** |
| emenda do piso | deslocar o piso composto de uma tile muda **0 de 270** células no pior piso |
| piso na rampa | nenhum glifo acima de 55% da rampa em 9/9 pisos |
| bloco | losango da face de cima com a largura máxima no meio e paredes de largura constante, 6/6; altura 20×**14** = tile (6) + parede (8) |
| pé | âncora tinta e centrada em **18/18** props e atores; tinta entre 19,5% e 85% |
| ator | herói com **12 linhas de tinta** (o `A(6)` da cripta com `A()=2`); 3 atores com `facing ±1` declarado |
| sombra | todos os discos resolvem: emprestados do conjunto das árvores ou **feitos aqui** (o raio da base dobrada passa do maior disco das árvores) |
| disco próprio | o único disco novo confere em 2:1 e com o centro na âncora |
| mancha | 7 manchas de piso na grade da tile; sangue é respingo, ossos são ossos — a primeira versão desenhou os dois como mancha e o banco acusou **arte repetida** |
| arte repetida | 41 peças distintas |
| composição | duas cenas (externa 180×71, cripta 160×76, 85% e 76% de tinta), sem borda rasgada, e **toda âncora de prop/ator confere** (o que ficou coberto, ficou por peça desenhada depois) |
| banco | ingest ok, 41/41 no índice, slots certos com `ator`, `bank.py check` passa |
| página | arquivo único, 712 KB, **sem `<script>`**, 11 quadros, sem overflow a 1440×900 e 390×844 |

## A peça (contrato)

```json
{ "id": "tree.oak.medium", "kind": "prop", "w": 12, "h": 12,
  "anchor": { "x": 6, "y": 11 }, "shadow": "tree.oak.medium.shadow",
  "frames": 1, "directions": 1,
  "cells": [ { "g": "  I@MKYZ1u", "c": ["", "", "#5b8c3f", …] }, … ] }
```

```json
{ "id": "tree.oak.medium.shadow", "kind": "decal", "layer": "ground", "for": "tree.oak.medium",
  "w": 11, "h": 3, "anchor": { "x": 5, "y": 1 },
  "disc": { "rx": 4.6, "ry": 1.38 },
  "cells": [ { "g": " ░▄▄███▄▄░ ", "c": […] } ] }
```

`cells` é linha a linha: `g` é a string de glifos, `c` a cor de cada célula (`""` = vazia, e o motor deixa
o fundo aparecer). `anchor` é a célula que vai para o centro do tile: no prop é o pé do tronco, na mancha é
o centro do disco. `disc` é a elipse desenhada — o 2:1 se confere nela, não na caixa de células (ver
abaixo). `frames` e `directions` já estão no contrato para o dia em que a peça animar.

## Pipeline

Desenha em **PIL 4× (supersampling)** → **média de área** (`Image.BOX`) para a grade de caracteres →
**glifo pela luminância** com auto-níveis por peça → **cor média** quantizada de 4 em 4. É o mesmo caminho
do navio pirata (`ascii-art/references/color-html-pipeline.md`).

A mancha não passa por esse caminho: é um disco de **uma cor só**, com o glifo saindo da **cobertura de
meio-bloco** de cada célula (`█ ▀ ▄`, mais `▓ ▒ ░` na borda). Um disco 2:1 costuma ter menos de uma célula
de altura, e uma célula de texto só sabe ser inteira — meio-bloco existe para isso.

## Regras que custaram iteração

1. **Desenhe em unidade de célula, nunca em pixel supersampleado.** Uma célula tem `UX = CELL_W * SS`
   pixels de largura no canvas. Tudo que eu desenhei com menos de ~0,6 célula (tronco, galho, fronde) foi
   dissolvido pela média de área e sumiu da peça pronta: o carvalho saiu com copa e sem tronco, o pinheiro
   com o miolo vazio, a árvore seca como um poste.
2. **O pé da peça é tinta por construção.** Depois de desenhar, um retângulo de contato é carimbado na
   coluna da âncora. Antes disso o arbusto simplesmente flutuava (última linha vazia) — peça que flutua no
   motor é defeito silencioso, e não se aposta na geometria para evitá-lo.
3. **O centro do sujeito fica no centro de uma CÉLULA, não na divisa.** `cx = (âncora + 0.5) * UX`. Na
   divisa ele se divide em duas células meio-iluminadas e o contato cai uma coluna ao lado.
4. **Auto-níveis por peça antes de escolher o glifo.** A rampa de 91 caracteres sobre cor escura devolve
   pontuação esparsa: casca de luminância 82 mapeia para `.`. Esticar a peça para o próprio p02..p99 é o
   que faz a massa ler como massa. E o piso do auto-nível **não pode apagar** célula que passou no teste de
   vazio — era assim que o pé sumia.
5. **O boost é o do motor, não o do teste de olhar.** `sat 1.24 · ganho 1.60 · lift 15`. Com o boost fraco
   (`ganho 1.06 · lift 5`) a tinta ficou em p10 17 / p50 73 e sujeito fino (seca, palmeira) sumia na
   página; com o do motor, p10 28 / p50 94. Medido nas duas direções, não escolhido no gosto.
6. **Frondes rombas, não agulhas.** Fronde afinando em ponta amostra para células soltas e a coroa deixa de
   ler como leque. Lâmina com ponta de 42% da base, mais uma "saia" de frondes mortas sob a coroa, é o que
   liga a coroa ao tronco.
7. **Corte justo no bbox.** A peça sai do gerador com a caixa exata do desenho; o tamanho da caixa de
   desenho só controla o detalhe, não o tamanho final.
8. **Luz de cima, e o topo da copa claro em toda a volta.** Ponderar o lado direito para baixo (luz
   lateral) deixava a **primeira** linha da copa mais escura que a segunda. Medido depois do conserto: o
   topo da copa das espécies redondas ficou +52% mais claro que a base dela.

## Verificado (34/34)

| medida | resultado |
|---|---|
| catálogo | 24 props + 24 manchas, semente 20261012 |
| determinismo | mesma semente → **bytes idênticos** |
| âncora | célula da âncora tinta em 24/24, contato em **uma única corrida** passando pela âncora |
| pé | elipse: as 24 peças com contato mais largo que 1 célula (antes o tronco era cortado reto) |
| silhueta iso | a linha mais larga da copa cai a **21% do topo**; no cone/arbusto, a 50% (base larga) |
| luz de cima | copa **+52%** mais clara no topo que na base (pior peça: salgueiro médio, +5%) |
| mancha | disco 2:1 **medido na elipse desenhada** (a grade não consegue 2:1 abaixo de uma célula), mais pesado na linha da âncora, âncora no centro, uma cor, `#1a1814` (lum 24) sob piso `#3a352c` (lum 53) |
| tinta | p10 28 · p25 51 · **p50 94**; quartil claro ≥ 60 em 24/24 |
| paleta | p90 **206**; 8 paletas distintas; outono 42° contra carvalho 96° **na tela** |
| linha de base | as três árvores param na mesma linha: **3 px** de espalhamento, medido nos pixels |
| ícones: resoluções | 28 itens × 3 = 84 peças; grande = **exatamente 2× a pequena** nos dois eixos (28/28) |
| ícones: legibilidade | nenhuma caixa pequena abaixo de 5 células no lado curto (28/28); nas 6 lâminas a **guarda é mais larga que a lâmina** em todos os três tamanhos |
| ícones: centragem | caixa da silhueta no centro da âncora em **84/84 exato** |
| ícones: tinta | 20–85% em 84/84 (o piso é 20 porque **um arco é curvo**: 25% de tinta é a forma honesta de um arco) |
| ícones: redução | `shrink(grande, 2)` cai na grade da pequena em 28/28; o `shrink` do navegador dá **a mesma grade glifo a glifo** que o do Python; o contraste desenhado (65,6) ganha do reduzido (56,9) com a margem de 5 |
| página | sem canvas, sem imagem, sem requisição externa; sem overflow em 1440×900 e 390×844 |
| ícones: redondo | todo círculo declarado no JSON tem `ry/rx = 0,602` (a proporção da célula) — o anel pequeno mede **33 × 33 px de tinta** |
| ícones: aspecto | o aspecto em **pixels** bate com o declarado por item em 28/28 (±18%): torso **73 × 77 px = 0,95** (era 60 × 99 = 0,60), elmo fechado 0,90, com chifres 1,10, redondo 1,05 |
| banco | `bank.py check`: 126 peças em 2 conjuntos, 46 tags, **zero arte repetida**; `tools/bank_audit.py`: **19/19** — 54 cartões (um por coisa) segurando as 126 peças, cena e itens em seções separadas, todo cartão abrindo na maior resolução, o botão trocando de verdade (e o «copiar» indo junto), filtros contados **em peças** (conifer → 3, mancha → 18, "palm" → 3, icone → 84), a seção esvaziada levando o título embora, e sem JavaScript as 126 resoluções na página |

Checagem que nunca falhou não prova nada: cada limiar aqui tem o valor da regressão ao lado (o boost fraco
medido em 17 / 35 / 73). E duas métricas foram escolhidas justamente por não medirem o que pareciam medir —
o **quartil claro** em vez da mediana (a mediana de uma espécie rarefeita mede a magreza do sujeito, não se
a tinta aparece) e o 2:1 conferido **na elipse** em vez de na caixa de células.

## A página

Uma faixa por espécie, as três árvores na mesma linha de base, sobre um **piso de pedra** (sombra só se
julga contra a superfície que ela escurece). Três botões: **cores** (desliga a cor, para julgar a
silhueta), **piso** (apaga o chão) e **linha de base**.

## Falta

- **Armas: não há variante de material.** A mesma espada em ferro, aço e ouro é o que dá variedade a um
  inventário de verdade (é como o Diablo faz), e a paleta já é parâmetro no gerador
  (`dict(metal=...)`) — falta só multiplicar o conjunto. Hoje a variedade vem do **estilo** (6 elmos, 6
  peças de torso, 3 escudos, cada um com o seu), não do material.
- **Armas: sem dano/estado.** Uma peça por item, sem a versão quebrada ou enferrujada.
- **Elmo pequeno: melhora por construção, não por medida.** A caixa grande (9×8 em vez de 9×6) dá à fenda
  da viseira uma linha própria, em vez de ela disputar a borda do domo com a aba. Isso é **olho, não
  número**: três métricas tentaram separar o elmo apertado do conserto e nenhuma separou (a quebra entre
  linhas mede 155 no defeito e 85 no conserto). Fica registrado como decisão de desenho, não como
  invariante.
- **Peças de torso muito parecidas na pequena.** Em 10×10, gibão, cota, placas e escamas leem como
  "armadura de torso" e o material é o que distingue; a 5 células de largura não há como o padrão de
  escama aparecer. É o próximo item a atacar se o jogo precisar distinguir as quatro na pequena.
- **No cartão do banco, a mancha sozinha continua um borrão.** A elipse é legível na escala maior do
  cartão, mas a *geometria* dela (onde cai a âncora, quanto mede em células) só se lê nos números ao
  lado. Marcar a célula da âncora dentro do cartão é o que falta — um borrão escuro num piso de pedra
  é o que uma sombra de contato É, e não tem como o desenho se explicar sozinho.
- Animação: `frames`/`directions` estão no contrato e não há nenhuma peça com mais de um quadro — é o
  próximo eixo (herói, monstro, tocha).
- Piso e bloco são outros tipos de peça, com outras regras: o piso precisa **emendar consigo mesmo** em
  qualquer direção, o que é um problema diferente de desenhar um objeto.
- Os anéis do pinheiro ainda arredondam para uma linha reta, porque a elipse da base do anel tem menos de
  uma célula de altura — a solução é a mesma da mancha (meio-bloco) e ainda não foi aplicada lá.
- A luz é por peça (auto-níveis). Se o jogo quiser luz do mundo, ela tem de sair do gerador e virar
  **wash** no motor.
- O `imagegen` como desenhista: gerar uma referência e passar pelo mesmo conversor, para comparar com o
  procedural.
- Integração: o isoforge ainda espera `assets/art.json` na âncora `ART_TEMPLATES`; falta o adaptador que
  lê este catálogo (prop + mancha, com as duas âncoras). Use `bank.py export` para tirar a fatia que o
  jogo vai consumir.
