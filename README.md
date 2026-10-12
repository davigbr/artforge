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
| `icone` | peça de **inventário**: não tem chão, é **centralizada no slot** |

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
| banco | `bank.py check`: 126 peças em 2 conjuntos, 46 tags, **zero arte repetida**; `tools/bank_audit.py`: **12/12**, com cada filtro contado contra o índice (conifer → 3, mancha → 18, "palm" → 3, icone → 84, chain → 3) |

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
