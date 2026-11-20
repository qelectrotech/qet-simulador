# Eletropneumática: rascunho (19/11/2026)

Ainda **não simulado**. Decisão de seguir fica para depois.

## Circuito de referência: `circuitos-qet/eletropneumatica_A+A-.qet`
A+ A- semiautomático: S1 liga K1 (selo), K1 energiza Y1, o cilindro 1A avança,
o fim de curso 1S2 (NF, fim do avanço) derruba K1, Y1 desliga e a mola recua o cilindro.

## O que a biblioteca do QElectroTech oferece (e o que não oferece)
- Válvulas (≈200) e cilindros (≈70) em **Pneumática**: vias **sem nome**, sem números 1–5 escritos,
  sem `link_type` master/slave. As vias internas de cada posição existem só como desenho.
- Solenoide: no pneumático faz parte do desenho da válvula (ex.: "5/2e [elec]-[spring]",
  `502010602010_5_2_way_010.elmt`, só 5 vias pneumáticas); no elétrico é a **"Eletroválvula"**
  (`electrovanne.elmt`, bornes A1/A2), sem vínculo com a válvula.
- Não há símbolo de marca de fim de curso no cilindro: traço + texto com as formas básicas (só desenho).
- Escape: **Silenciador pneumático** (Pneumática > Ar comprimido > componentes funcionais > fluxo de ar).

## Convenção adotada (ISO 1219 / Festo didática): vínculo pelo NOME
- Eletroválvula do comando e válvula pneumática com o **mesmo nome** (Y1; duplo solenoide Y1/Y2).
- Cilindro **1A**; sensores **1S1** (recuado) e **1S2** (avançado): o 1º número = cilindro, o 2º = posição.

## Geometria conferida
- 5/2e [elec]-[spring]: vias (10,-20)=4, (30,-20)=2, (10,10)=5, (20,10)=1, (30,10)=3.
  Repouso (mola): 1→2, 4→5. Com Y1: 1→4, 2→3.
- Cilindro dupla ação `5030101100_double_effet.elmt`: êmbolo à esquerda, haste sai pela direita;
  (-30,20) = câmara traseira (avanço), (20,20) = câmara da haste (recuo).

## Plano, se for adiante
1. Vínculo pelo nome (Y1↔Y1, 1S1/1S2↔1A).
2. Tabelas de vias por símbolo: 5/2 solenoide-mola, 5/2 duplo solenoide, 3/2 solenoide-mola,
   cilindros simples/dupla ação, fonte de ar, silenciador.
3. Propagação do ar (pressão ~ L, escape ~ N), mesma ideia do comando elétrico.
4. Cilindro se move no tempo (curso ~1 s) e aciona 1S1/1S2 sozinho.
5. Tela: haste em movimento, linhas pressurizadas destacadas.
Estimativa: 2–3× o trabalho do sensor indutivo, nas duas versões (Python e JS).
Fora de alcance: hidráulica proporcional (pressão/vazão/sinal analógico).
