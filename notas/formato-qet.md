# Formato .qet: o que o simulador precisa

Notas a partir de `circuitos-qet/partida_direta.qet` (QElectroTech 0.100.0).

## Estrutura geral

O `.qet` é um XML com três blocos que interessam:

```
<project>
  <diagram>                 ← o desenho (folha)
    <elements>              ← cada símbolo colocado
    <conductors>            ← cada fio
  </diagram>
  <collection>              ← definições embutidas dos símbolos usados
</project>
```

## Elementos (`diagram/elements/element`)

- `uuid`: identificador único do elemento no desenho.
- `type`: caminho do símbolo (ex.: `.../01_coils/comm_electronique.elmt`).
- `elementInformations/elementInformation[@name="label"]`: o nome (S1, K1...).
- `links_uuids/link_uuid`: vínculo mestre/escravo. Existe **nos dois sentidos**:
  a bobina aponta para o contato e o contato aponta para a bobina.

## Definições (`collection/.../element/definition`)

- `link_type`:
  - `master`: bobina (com `kindInformations/type = coil`)
  - `slave`: contato (com `kindInformations/state = NO` ou `NC`)
  - `simple`: botoeiras, fonte etc.
- `terminal`: cada borne, com `uuid` e `name` (L, N, A1, A2, 13, 14, 21, 22).

## Fios (`diagram/conductors/conductor`)

Cada fio liga dois bornes:
`element1` + `terminal1` ↔ `element2` + `terminal2`.
Os `terminal*` são os uuid dos bornes da definição (não os `id` numéricos do elemento).

## O que está e o que não está no arquivo

| Necessidade | No `.qet`? |
|---|---|
| Ligação dos fios | Sim, por borne |
| Nome dos bornes | Sim |
| Bobina = mestre, contato = escravo | Sim (`link_type`) |
| Contato NA ou NF | Sim (`state`) |
| Contato pertence a qual bobina | Sim, **se vinculado** no QElectroTech |
| Botoeira NA ou NF | **Não**: deduzir pela numeração IEC (x3–x4 = NA, x1–x2 = NF) |

## Armadilhas encontradas

1. **Texto digitado não é vínculo.** Escrever "K1" sobre um contato só cria um
   texto livre (`text_from="UserText"`). O vínculo real é feito na aba de
   referência cruzada do contato e aparece como `link_uuid`.
2. **Mudança na tela ≠ arquivo salvo.** Conferir o asterisco na barra de título.
3. **Contato vinculado pode ter `label` vazio:** o nome vem da bobina mestre.
4. **Maiúsculas e minúsculas:** a bobina foi salva como `k1`. O simulador compara
   nomes sem diferenciar maiúsculas e minúsculas.

## Temporizadores

- A bobina do temporizador é uma bobina comum (`link_type="master"`, `type=coil`).
- O **tipo de temporização fica no contato** (`kindInformations/type`):
  `delayOn` = retardo na energização ("conta e liga"); `delayOff` = retardo na desenergização.
- **Não existe campo de tempo.** O simulador usa 5 s por padrão, aceita o comando `tempo KT1 3`
  e lê um valor como `5s` escrito em qualquer campo de texto da bobina.
- **Defeito na biblioteca do QElectroTech:** `con_simple_tmp_r.elmt` (`delayOff`) e
  `con_simple_tmp_t.elmt` (`delayOn`) têm o **mesmo nome em PT e EN**
  ("tempo retardado de ligado" / "switch-on delay timer"). Em FR e DE os nomes estão certos
  (*tempo repos* / *abfallverzögert* para o `_r`; *tempo travail* / *ansprechverzögert* para o `_t`).

## Mais armadilhas

5. **Elementos sobrepostos:** um contato colado exatamente sobre outro fica invisível na tela.
   O simulador avisa contatos sem vínculo.
6. **Editar o .qet com o QElectroTech aberto:** ao salvar, o programa grava por cima das alterações
   feitas fora dele.

## Botoeiras na biblioteca do QElectroTech

- Os botões de pressão "de verdade" (`20_push_buttons/poussoir.elmt`, `poussoir_nf.elmt`, `au.elmt`...)
  são **mestres** (`link_type="master"`) do tipo `commutator`, com bornes **sem número** e **sem**
  `state` no `kindInformations`. NA/NF só aparece no nome ("Botão de pressão (NA)").
- `foot_no.elmt` / `foot_nc.elmt` são **interruptores de pedal**: elementos `simple` com bornes
  numerados (13-14 / 21-22).
- Ordem usada pelo simulador (sugestão de Laurent/scorpio810 no fórum): numeração dos bornes →
  nome do arquivo → nome do elemento → aviso.
- Outra inconsistência da biblioteca: `arret-urgence_no.elmt` diz "NF" em francês e "NA" em
  português; o simulador segue o nome do arquivo (`_no`).

## Circuito de força

- Fonte trifásica (`src_3p_pe_n.elmt`): bornes nomeados `L1`, `L2`, `L3`, `N`, `PE`.
- Contatos principais do contator: escravos com `type="power"`, `state="NO"`, `number="4"` e 8 bornes
  **sem nome**. Cada polo = par de bornes na mesma coluna (mesmo `x`) do símbolo.
- Disjuntor (`dis_mag_term_4f-1.elmt`) e relé térmico (`relais_therm4_1_wide.elmt`): mestres com
  `type="protection"`. O simulador distingue o térmico pelo nome; os polos do térmico nunca abrem,
  o disparo atua os contatos auxiliares vinculados (NF 95-96).
- Motor (`moto_ac_3ph.elmt`): elemento simples com 4 bornes sem nome (3 fases + PE). A ordem U, V, W
  é a ordem dos bornes no próprio símbolo (pelo `x`), então o sentido de rotação não depende de como o
  motor foi girado no desenho.
- Armadilha vista: o NF de proteção no comando foi vinculado primeiro ao **Q1** em vez do **F1**.
  O simulador mostra a quais contatos cada proteção está ligada.

## Motor de 6 bornes, fontes separadas, fusível e emergência

- Motor `moteur_tri_de.elmt`: bornes nomeados `U1 V1 W1 U2 V2 W2 PE`. Estrela = U2, V2 e W2 unidos
  entre si; triângulo (IEC) = U1-W2, V1-U2, W1-V2, ou seja, U2/V2/W2 recebem as fases de V1/W1/U1.
- Fontes `src_p.elmt` (borne `L`) e `src_n.elmt` (borne `N`) podem ser elementos separados.
- Fusível `pojistka1p.elmt` (pasta `10_fuses`): sempre conduz.
- Parada de emergência `arret_urgence_deverrouillage_a_cle.elmt`: mestre `commutator`, bornes sem
  número e sem NA/NF no nome; o simulador a trata como NF que trava ao acionar.
- Armadilha vista de novo: contato de potência duplicado, colado exatamente sobre outro (mesmo x, y),
  recebendo os fios no lugar do contato verdadeiro.

