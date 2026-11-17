# qet-simulador

Simulador de comandos elétricos que lê arquivos `.qet` do [QElectroTech](https://qelectrotech.org).
*Electrical control-circuit simulator that reads QElectroTech `.qet` files.*

> **Status:** protótipo (prova de conceito). / *Prototype (proof of concept).*

## O que faz / What it does

Lê um diagrama de comando desenhado no QElectroTech e simula, no terminal, o
comportamento de botoeiras, bobinas e contatos: selo, intertravamento, desligamento
e temporizadores (retardo na energização e na desenergização). No circuito de força, mostra se o
motor gira, o sentido de rotação, falta de fase e curto-circuito, com disjuntor e relé térmico
(o disjuntor dispara sozinho em curto-circuito entre fases).

*Reads a control diagram drawn in QElectroTech and simulates push buttons, coils and
contacts in the terminal (self-holding, interlocking, stop, on-delay and off-delay timers). In the
power circuit it shows motor running, direction of rotation, missing phase and short circuits, with
circuit breaker and thermal overload relay.*

Exemplo (reversão com intertravamento) / *Example (reversing starter with interlock):*

```
> S1
  pressiona S1   -> K1=ENERGIZADA, K2=desligada   [estável]
> S2
  pressiona S2   -> K1=ENERGIZADA, K2=desligada   [estável]   <- intertravamento / interlock
> S0
  pressiona S0   -> K1=desligada, K2=desligada   [estável]
> S2
  pressiona S2   -> K1=desligada, K2=ENERGIZADA   [estável]
```

Exemplos incluídos / *Included examples* (`circuitos-qet/`): partida direta, reversão com intertravamento,
partida temporizada, estrela-triângulo (comando), partida direta e reversão com força / *DOL,
reversing, timed start, star-delta (control), DOL and reversing with power circuit*.

## Versão gráfica / *Graphical version*

**Online:** https://tonymarim.github.io/qet-simulador/ (com circuitos de exemplo / *with example circuits*)

Abra `web/index.html` no navegador (duplo clique) e escolha um arquivo `.qet`. O diagrama aparece como
no QElectroTech e pode ser simulado: **clique e segure** uma botoeira para pressioná-la (**Shift+clique**
mantém pressionada), clique no **disjuntor** para ligar/desligar e no **relé térmico** para simular
sobrecarga. Fios energizados ficam vermelhos (fase) ou azuis (neutro), bobinas energizadas e contatos
atuados ficam realçados, o motor mostra o sentido de giro e os temporizadores correm em tempo real.
Funciona sem internet; `index.html` e `motor.js` precisam ficar na mesma pasta.

*Open `web/index.html` in a browser and pick a `.qet` file. Press and hold push buttons (Shift+click
latches), click the breaker or the thermal relay. Works offline; keep `index.html` and `motor.js`
together.*

**Testes de paridade / *Parity tests*:** `python tests/paridade.py` e `node tests/paridade.js`
(requer `npm i @xmldom/xmldom`) devem produzir a mesma saída. / *must produce identical output.*

## Como usar / How to use

Requer Python 3.8+ (sem bibliotecas extras). / *Requires Python 3.8+ (no extra libraries).*

```
cd simulador
python simulador.py ../circuitos-qet/reversao.qet
```

Comandos / *Commands*: `S1` pulso / *pulse* · `+S1` mantém / *hold* · `-S1` solta / *release* ·
`t 5` avança 5 s / *advance 5 s* · `tempo KT1 3` ajusta KT1 para 3 s / *set KT1 to 3 s* ·
`Q1` liga/desliga disjuntor / *breaker on/off* · `F1` sobrecarga no térmico / *thermal overload trip/reset* · `sair` / *quit*

## Regras para o desenho / Drawing rules

1. **Vincule cada contato à sua bobina** pela referência cruzada do QElectroTech
   (texto digitado não vale). / *Link each contact to its coil via cross-reference.*
2. **Botoeiras:** o tipo NA/NF é deduzido, em ordem, pela numeração IEC dos bornes
   (13–14 = NA, 21–22 = NF), pelo nome do arquivo do símbolo (`_no`, `_nf`...) e pelo nome do
   elemento na biblioteca. Se nada servir, o simulador avisa. Botões de pressão "mestres"
   (`poussoir`, tipo `commutator`) também são aceitos, e contatos vinculados a eles seguem o botão.
   / *Push-button NO/NC type is inferred from IEC terminal numbers, then the symbol file name,
   then the element name; a warning is shown if none works. Master push buttons (`commutator`)
   are supported, and contacts linked to them follow the button.*
3. **Dê nome a todas as botoeiras** (S0, S1...). / *Name every push button.*
4. **Temporizadores:** o tipo vem do contato (`delayOn` / `delayOff`). O QElectroTech não tem campo de
   tempo: o padrão é 5 s, ou escreva o valor (ex.: `5s`) em um campo de texto da bobina.
   / *Timer type comes from the contact; default time is 5 s, or write e.g. `5s` in a coil text field.*
   ⚠️ Em PT/EN, os contatos `con_simple_tmp_r` e `con_simple_tmp_t` têm o mesmo nome na biblioteca;
   o de "conta e liga" é o `_t` (FR: *tempo travail*). / *In PT/EN both share the same name; on-delay is `_t`.*

Detalhes do formato: [`notas/formato-qet.md`](notas/formato-qet.md)

## Limitações atuais / Current limitations

- Uma folha por projeto / *single sheet*
- Força: motores trifásicos simples (3 bornes + PE); ainda sem motor de 6 bornes (estrela-triângulo)
  / *power: simple 3-phase motors only; no 6-terminal motor yet*
- Cargas em série não suportadas / *series loads not supported*

## Licença / License

GPL-3.0
