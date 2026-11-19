/* ============================================================
   qet-simulador · motor de simulação (JavaScript)
   Tradução do simulador/simulador.py. Os dois precisam dar o
   mesmo resultado: tests/paridade.js compara os dois.
   Funciona no navegador e no Node (para os testes).
   ============================================================ */
(function (raiz) {
"use strict";

/* ---------- utilidades de XML (DOM do navegador ou xmldom) ---------- */
function filhos(no, tag) {
  const r = [];
  if (!no) return r;
  for (let c = no.firstChild; c; c = c.nextSibling)
    if (c.nodeType === 1 && (!tag || c.tagName === tag)) r.push(c);
  return r;
}
const filho = (no, tag) => filhos(no, tag)[0] || null;
const texto = no => (no && no.textContent ? no.textContent : "").trim();
const todos = (no, tag) => (no ? Array.from(no.getElementsByTagName(tag)) : []);

/* ---------- 1. leitura do arquivo .qet ---------- */
function lerDefinicoes(projeto) {
  // Coleção embutida: categorias aninhadas -> caminho "import/10_electric/.../x.elmt"
  const defs = {};
  const percorrer = (no, caminho) => {
    for (const c of filhos(no)) {
      if (c.tagName === "category") percorrer(c, caminho.concat(c.getAttribute("name")));
      else if (c.tagName === "element") {
        const d = filho(c, "definition");
        if (!d) continue;
        const kind = {};
        for (const k of filhos(filho(d, "kindInformations"), "kindInformation"))
          kind[k.getAttribute("name")] = texto(k);
        const bornes = {}, geo = {};
        for (const t of todos(d, "terminal")) {
          bornes[t.getAttribute("uuid")] = t.getAttribute("name") || "";
          geo[t.getAttribute("uuid")] = [parseFloat(t.getAttribute("x") || 0),
                                         parseFloat(t.getAttribute("y") || 0)];
        }
        defs[caminho.concat(c.getAttribute("name")).join("/")] = {
          link_type: d.getAttribute("link_type") || "simple",
          kind, bornes, geo,
          nomes: todos(d, "name").map(texto),          // nome em cada idioma
        };
      }
    }
  };
  percorrer(filho(projeto, "collection"), []);
  return defs;
}

function tipoBotoeira(arquivo, def) {
  /* NA (NO) ou NF (NC), nesta ordem: numeração IEC dos bornes, nome do arquivo,
     nome do elemento na biblioteca. Devolve [estado, origem] ou [null, null]. */
  const nomes = Object.values(def.bornes).filter(n => n);
  // só vale para bornes numerados (13-14, 21-22...), não para A1-A2 ou L-N
  const finais = nomes.length && nomes.every(n => /^\d+$/.test(n)) ? new Set(nomes.map(n => n.slice(-1))) : new Set();
  const iguais = (a, b) => a.size === b.length && b.every(x => a.has(x));
  if (iguais(finais, ["3", "4"])) return ["NO", "bornes"];
  if (iguais(finais, ["1", "2"])) return ["NC", "bornes"];

  const partes = new Set(arquivo.toLowerCase().replace(/\.[^.]*$/, "").split(/[^a-z]+/));
  let no = partes.has("no") || partes.has("na"), nc = partes.has("nc") || partes.has("nf");
  if (no !== nc) return [no ? "NO" : "NC", "nome do arquivo"];

  const t = def.nomes.join(" ");
  no = /\b(NO|NA)\b/.test(t); nc = /\b(NC|NF)\b/.test(t);
  if (no !== nc) return [no ? "NO" : "NC", "nome do elemento"];
  return [null, null];
}

function eEmergencia(tipo, def) {
  // Parada de emergência: fica travada quando acionada (só destrava ao acionar de novo)
  return /urgence|emergenc|emergênc|not-?aus|e-?stop/i.test(tipo)
    || /emergency|urgence|emerg[eê]ncia|not-?aus/i.test(def.nomes.join(" "));
}

function classificar(tipo, def) {
  /* Papel do elemento no simulador: [papel, estado, origem]. */
  const lt = def.link_type, kind = def.kind;
  const nomesBornes = new Set(Object.values(def.bornes));
  const arquivo = tipo.split("/").pop();
  const arq = arquivo.toLowerCase();
  if (lt === "next_report" || lt === "previous_report")
    return ["renvoi", null, null];          // referência de página: liga um fio entre folhas
  const t = def.nomes.join(" ");
  if (lt === "simple" && nomesBornes.size && [...nomesBornes].every(n => n === "L" || n === "N"))
    return ["fonte", null, null];            // fonte L+N, ou só fase (L) ou só neutro (N)
  if (["L", "N", "L+", "L-"].every(n => nomesBornes.has(n)))
    return ["fonte_cc", null, null];         // fonte retificadora: entrada L/N, saída L+/L-
  if (["L1", "L2", "L3"].every(n => nomesBornes.has(n))) return ["fonte3f", null, null];
  if (lt === "master" && kind.type === "coil") return ["bobina", null, null];
  if (lt === "master" && kind.type === "protection") {
    // Térmico: polos de força nunca abrem. Disjuntor: polos abrem quando desligado.
    if (arq.startsWith("relais_therm") ||
        /thermal relay|relais thermique|rel[eé] t[eé]rmico|thermorelais/i.test(t))
      return ["termico", null, null];
    return ["disjuntor", null, null];
  }
  if (lt === "simple" && Object.keys(def.bornes).length === 2 && (/lamp|voyant|lampara|signal/.test(arq)
      || /\blight\b|\blamp|\blampe\b|l[aá]mpara|l[aâ]mpada|\bvoyant/i.test(t)))
    return ["lampada", null, null];          // lâmpada de sinalização: carga entre L e N
  if (lt === "simple" && (/fus[eií]|pojistka/i.test(arq) || tipo.includes("/10_fuses/")
                          || /\bfuse|\bfusible|\bfus[ií]vel/i.test(t)))
    return ["fusivel", null, null];          // fusível: sempre conduz
  if (lt === "simple" && (arq.startsWith("moto") || /\bmotor|\bmoteur/i.test(t)))
    return ["motor", null, null];
  if (lt === "slave") return ["contato", kind.state || "NO", "kindInformations"];
  if (Object.keys(def.bornes).length === 2 && (lt === "simple" || kind.type === "commutator")) {
    const [estado, origem] = tipoBotoeira(arquivo, def);
    if (eEmergencia(tipo, def))              // NF, salvo se a numeração dos bornes disser outra coisa
      return ["botoeira", origem === "bornes" ? estado : "NC", "parada de emergência"];
    if (estado) return ["botoeira", estado, origem];
    if (kind.type === "commutator" || tipo.includes("push_button")) return ["botoeira", null, null];
  }
  return ["desconhecido", null, null];
}

function lerCircuito(doc) {
  const projeto = doc.documentElement;
  const defs = lerDefinicoes(projeto);
  const diagramas = filhos(projeto, "diagram");      // todas as folhas do projeto
  const elementos = {};
  for (const e of diagramas.flatMap(dg => filhos(filho(dg, "elements"), "element"))) {
    const tipo = e.getAttribute("type");
    const d = defs[tipo.replace("embed://", "")];
    if (!d) continue;
    const info = {};
    for (const i of filhos(filho(e, "elementInformations"), "elementInformation"))
      info[i.getAttribute("name")] = texto(i);
    const [papel, estado, origem] = classificar(tipo, d);
    elementos[e.getAttribute("uuid")] = {
      papel, estado_normal: estado, origem_estado: origem,
      nome: info.label || "",
      bornes: d.bornes, geo: d.geo,
      vinculos: todos(e, "link_uuid").map(l => l.getAttribute("uuid")),
      tipo_contato: d.kind.type || "simple",
      trava: papel === "botoeira" && eEmergencia(tipo, d),
      info,
    };
  }
  // Contato sem nome herda o nome da bobina/mestre vinculado
  for (const el of Object.values(elementos))
    if (el.papel === "contato" && !el.nome && el.vinculos.length && elementos[el.vinculos[0]])
      el.nome = elementos[el.vinculos[0]].nome;
  const fios = diagramas.flatMap(dg => filhos(filho(dg, "conductors"), "conductor")).map(c => [
    [c.getAttribute("element1"), c.getAttribute("terminal1")],
    [c.getAttribute("element2"), c.getAttribute("terminal2")]]);
  // Referência de página (renvoi de folio): o borne de cada ponta é o mesmo ponto elétrico
  for (const [u, el] of Object.entries(elementos))
    for (const v of el.vinculos) {
      const par = elementos[v];
      if (el.papel === "renvoi" && par && par.papel === "renvoi" && u < v)
        fios.push([[u, Object.keys(el.bornes)[0]], [v, Object.keys(par.bornes)[0]]]);
    }
  return { elementos, fios };
}

function tempoDoDesenho(el, padrao = 5) {
  // Tempo escrito em qualquer campo do elemento (ex.: "5s", "t=2,5 s"); senão, o padrão.
  for (const v of Object.values(el.info)) {
    const m = /(\d+(?:[.,]\d+)?)\s*s\b/.exec(v);
    if (m) return parseFloat(m[1].replace(",", "."));
  }
  return padrao;
}

/* ---------- 2. motor de simulação ---------- */
const no = (u, t) => u + "|" + t;           // chave de um borne no grafo

class Simulador {
  constructor({ elementos, fios }) {
    this.el = elementos;
    this.fios = fios;
    const de = papel => Object.keys(elementos).filter(u => elementos[u].papel === papel);
    this.pressionado = Object.fromEntries(de("botoeira").map(u => [u, false]));
    this.energizada = Object.fromEntries(de("bobina").map(u => [u, false]));
    this.relogio = 0;
    this.t_ajuste = {};
    for (const u of Object.keys(this.energizada))
      if (this.eTemporizador(u)) this.t_ajuste[u] = tempoDoDesenho(elementos[u]);
    this.t_ligada = Object.fromEntries(Object.keys(this.energizada).map(u => [u, 0]));
    this.t_desligada = Object.fromEntries(Object.keys(this.energizada).map(u => [u, Infinity]));
    this.disj_ligado = Object.fromEntries(de("disjuntor").map(u => [u, true]));
    this.disparado = Object.fromEntries(de("termico").map(u => [u, false]));
  }

  eTemporizador(bobina) {
    return Object.values(this.el).some(e => e.papel === "contato" && e.vinculos.includes(bobina)
      && (e.tipo_contato === "delayOn" || e.tipo_contato === "delayOff"));
  }

  /* --- estado de cada chave/contato --- */
  atuado(u) {
    const e = this.el[u];
    if (e.papel === "botoeira") return this.pressionado[u];
    if (e.papel === "contato") return e.vinculos.some(m => this.mestreAtuado(e.tipo_contato, m));
    return false;
  }
  fechado(u) {
    const e = this.el[u];
    if (e.papel !== "botoeira" && e.papel !== "contato") return false;
    if (e.estado_normal === null) return false;          // botoeira de tipo indefinido: aberta
    const a = this.atuado(u);
    return e.estado_normal === "NO" ? a : !a;
  }
  mestreAtuado(tipo, mestre) {
    if (mestre in this.energizada) return this.contatoAtuado(tipo, mestre);
    if (mestre in this.disj_ligado) return this.disj_ligado[mestre];  // auxiliar de disjuntor
    if (mestre in this.disparado) return this.disparado[mestre];      // auxiliar de térmico
    return !!this.pressionado[mestre];
  }
  contatoAtuado(tipo, bobina) {
    const ligada = this.energizada[bobina], T = this.t_ajuste[bobina] ?? 0;
    if (tipo === "delayOn") return ligada && this.t_ligada[bobina] >= T - 1e-9;
    if (tipo === "delayOff") return ligada || this.t_desligada[bobina] < T - 1e-9;
    return ligada;
  }

  /* --- polos: pares de bornes que uma chave liga entre si --- */
  polos(u) {
    const bornes = Object.keys(this.el[u].bornes);
    if (bornes.length === 2) return [[bornes[0], bornes[1]]];
    const colunas = new Map();
    for (const t of bornes) {
      const [x, y] = this.el[u].geo[t];
      const k = Math.round(x);
      if (!colunas.has(k)) colunas.set(k, []);
      colunas.get(k).push([y, t]);
    }
    const r = [];
    for (const c of colunas.values()) {
      if (c.length !== 2) continue;
      c.sort((a, b) => a[0] - b[0]);
      r.push([c[0][1], c[1][1]]);
    }
    return r;
  }
  conduz(u) {
    const p = this.el[u].papel;
    if (p === "botoeira" || p === "contato") return this.fechado(u);
    if (p === "disjuntor") return this.disj_ligado[u];
    if (p === "termico" || p === "fusivel") return true;   // térmico e fusível sempre conduzem
    return false;
  }
  grafo() {
    const viz = new Map();
    const liga = (a, b) => {
      if (!viz.has(a)) viz.set(a, new Set());
      if (!viz.has(b)) viz.set(b, new Set());
      viz.get(a).add(b); viz.get(b).add(a);
    };
    for (const [a, b] of this.fios) liga(no(...a), no(...b));
    for (const u of Object.keys(this.el))
      if (this.conduz(u)) for (const [t1, t2] of this.polos(u)) liga(no(u, t1), no(u, t2));
    return viz;
  }
  alcancaveis(nomeOrigem, papelFonte = "fonte", viz = null) {
    viz = viz || this.grafo();
    // Comando alimentado pela fonte trifásica: qualquer fase vale como L, e o N dela como N
    const extra = papelFonte === "fonte" ? ({ L: ["L1", "L2", "L3"], N: ["N"] }[nomeOrigem] || []) : [];
    const origem = [];
    for (const [u, e] of Object.entries(this.el))
      for (const [t, n] of Object.entries(e.bornes))
        if ((e.papel === papelFonte && n === nomeOrigem) || (e.papel === "fonte3f" && extra.includes(n)))
          origem.push(no(u, t));
    const conv = Object.keys(this.el).filter(u => this.el[u].papel === "fonte_cc");
    if (!extra.length || !conv.length) return this._bfs(origem, viz);
    // Fonte retificadora: com L e N na entrada, a saída L+ vale como L e a L- como N
    const borne = (u, nome) => Object.entries(this.el[u].bornes).filter(([, n]) => n === nome).map(([t]) => no(u, t));
    const base = { L: [], N: [] };
    for (const [u, e] of Object.entries(this.el))
      for (const [t, n] of Object.entries(e.bornes)) {
        if ((e.papel === "fonte" && n === "L") || (e.papel === "fonte3f" && ["L1", "L2", "L3"].includes(n)))
          base.L.push(no(u, t));
        if ((e.papel === "fonte" || e.papel === "fonte3f") && n === "N") base.N.push(no(u, t));
      }
    let ativos = new Set();
    for (;;) {
      const vL = this._bfs([...base.L, ...[...ativos].flatMap(u => borne(u, "L+"))], viz);
      const vN = this._bfs([...base.N, ...[...ativos].flatMap(u => borne(u, "L-"))], viz);
      const novos = new Set(conv.filter(u => borne(u, "L").some(b => vL.has(b)) && borne(u, "N").some(b => vN.has(b))));
      if (novos.size === ativos.size && [...novos].every(u => ativos.has(u))) return nomeOrigem === "L" ? vL : vN;
      ativos = novos;
    }
  }
  _bfs(origem, viz) {
    const vistos = new Set(origem), fila = [...origem];
    while (fila.length) {
      const n = fila.shift();
      for (const m of viz.get(n) || []) if (!vistos.has(m)) { vistos.add(m); fila.push(m); }
    }
    return vistos;
  }

  /* --- circuito de força --- */
  forca() {
    const viz = this.grafo();
    const fases = {};
    for (const f of ["L1", "L2", "L3"]) fases[f] = this.alcancaveis(f, "fonte3f", viz);
    const avisos = [];
    for (const [a, b] of [["L1", "L2"], ["L2", "L3"], ["L1", "L3"]])
      if ([...fases[a]].some(x => fases[b].has(x))) avisos.push(`CURTO-CIRCUITO ${a}-${b}`);
    const motores = [], detalhe = {};
    for (const [u, e] of Object.entries(this.el)) {
      if (e.papel !== "motor") continue;
      const porNome = {};
      for (const [t, n] of Object.entries(e.bornes)) porNome[n] = t;
      if (["U1", "V1", "W1", "U2", "V2", "W2"].every(n => n in porNome)) {
        const est = this.motor6Bornes(u, porNome, fases, viz);
        motores.push(`${e.nome || "motor"}: ${est.txt}`);
        detalhe[u] = est;
        continue;
      }
      const ordem = Object.keys(e.bornes).sort((p, q) =>
        e.geo[p][0] - e.geo[q][0] || e.geo[p][1] - e.geo[q][1]);
      const chegam = ordem.map(t => Object.keys(fases).filter(f => fases[f].has(no(u, t))));
      const recebidas = chegam.filter(c => c.length === 1).map(c => c[0]);
      const nome = e.nome || "motor";
      let est;
      if (chegam.some(c => c.length > 1)) est = { txt: "EM CURTO (duas fases no mesmo borne)", gira: 0 };
      else if (recebidas.length === 3 && new Set(recebidas).size === 3) {
        const i = recebidas.indexOf("L1");
        const seq = recebidas.slice(i).concat(recebidas.slice(0, i)).join(",");
        const horario = seq === "L1,L2,L3";
        est = { txt: `GIRANDO (${horario ? "horário" : "anti-horário"})`, gira: horario ? 1 : -1 };
      } else if (recebidas.length)
        est = { txt: `FALTA DE FASE (${[...new Set(recebidas)].sort().join(", ")})`, gira: 0 };
      else est = { txt: "parado", gira: 0 };
      motores.push(`${nome}: ${est.txt}`);
      detalhe[u] = est;
    }
    return { motores, avisos, detalhe, fases };
  }

  motor6Bornes(u, t, fases, viz) {
    /* Estrela: U2, V2 e W2 unidos entre si (sem fase). Triângulo: U2, V2 e W2 recebem
       as fases de V1, W1 e U1 (U1-W2, V1-U2, W1-V2). */
    const fase = n => Object.keys(fases).filter(f => fases[f].has(no(u, t[n])));
    const ent = ["U1", "V1", "W1"].map(fase), sai = ["U2", "V2", "W2"].map(fase);
    if (ent.concat(sai).some(c => c.length > 1)) return { txt: "EM CURTO (duas fases no mesmo borne)", gira: 0 };
    if (!ent.every(c => c.length === 1) || new Set(ent.map(c => c[0])).size !== 3) {
      const rec = [...new Set(ent.concat(sai).filter(c => c.length).map(c => c[0]))].sort();
      return rec.length ? { txt: `FALTA DE FASE (${rec.join(", ")})`, gira: 0 } : { txt: "parado", gira: 0 };
    }
    const seq = ent.map(c => c[0]), i = seq.indexOf("L1");
    const horario = seq.slice(i).concat(seq.slice(0, i)).join(",") === "L1,L2,L3";
    const sentido = horario ? "horário" : "anti-horário", gira = horario ? 1 : -1;
    if (!sai.some(c => c.length)) {
      const ini = no(u, t.U2), comp = new Set([ini]), fila = [ini];
      while (fila.length) {
        const n = fila.shift();
        for (const m of viz.get(n) || []) if (!comp.has(m)) { comp.add(m); fila.push(m); }
      }
      if (comp.has(no(u, t.V2)) && comp.has(no(u, t.W2)))
        return { txt: `GIRANDO em estrela (${sentido})`, gira, ligacao: "estrela" };
      return { txt: "ENROLAMENTOS ABERTOS (sem fechamento estrela ou triângulo)", gira: 0 };
    }
    if (sai.map(c => c[0]).join(",") === [seq[1], seq[2], seq[0]].join(","))
      return { txt: `GIRANDO em triângulo (${sentido})`, gira, ligacao: "triângulo" };
    return { txt: "LIGAÇÃO INCORRETA dos enrolamentos", gira: 0 };
  }

  /* --- resolve até estabilizar --- */
  resolver(maxIter = 50) {
    for (let i = 0; i < maxIter; i++) {
      const viz = this.grafo();
      const vL = this.alcancaveis("L", "fonte", viz), vN = this.alcancaveis("N", "fonte", viz);
      let mudou = false;
      for (const u of Object.keys(this.energizada)) {
        const [a, b] = Object.keys(this.el[u].bornes).map(t => no(u, t));
        const novo = (vL.has(a) && vN.has(b)) || (vL.has(b) && vN.has(a));
        if (novo !== this.energizada[u]) {
          this.energizada[u] = novo;
          if (novo) this.t_ligada[u] = 0; else this.t_desligada[u] = 0;
          mudou = true;
        }
      }
      if (!mudou) return "estável";
    }
    return "OSCILANDO";
  }

  /* --- disjuntor dispara sozinho em curto-circuito --- */
  disparosPorCurto() {
    let curtos = this.forca().avisos.filter(a => a.startsWith("CURTO-CIRCUITO"));
    const msgs = [];
    for (const u of Object.keys(this.disj_ligado)) {
      if (!curtos.length) break;
      if (!this.disj_ligado[u]) continue;
      this.disj_ligado[u] = false;
      const depois = this.forca().avisos;
      const resolvidos = curtos.filter(c => !depois.includes(c));
      if (resolvidos.length) {
        const f = resolvidos.map(c => c.replace("CURTO-CIRCUITO ", "")).join(", ");
        msgs.push(`${this.el[u].nome || "disjuntor"} DISPAROU (curto-circuito ${f})`);
        curtos = curtos.filter(c => depois.includes(c));
      } else this.disj_ligado[u] = true;
    }
    if (msgs.length) this.resolver();
    return msgs;
  }

  /* --- lâmpada acesa: fase (L) num borne e neutro (N) no outro, como uma bobina --- */
  lampadas(viz = null) {
    viz = viz || this.grafo();
    const vL = this.alcancaveis("L", "fonte", viz), vN = this.alcancaveis("N", "fonte", viz);
    const r = {};
    for (const [u, e] of Object.entries(this.el)) {
      if (e.papel !== "lampada") continue;
      const [a, b] = Object.keys(e.bornes).map(t => no(u, t));
      r[u] = (vL.has(a) && vN.has(b)) || (vL.has(b) && vN.has(a));
    }
    return r;
  }

  /* --- texto de estado (mesmo formato do simulador.py) --- */
  estado() {
    let txt = Object.entries(this.energizada)
      .map(([u, v]) => `${this.el[u].nome}=${v ? "ENERGIZADA" : "desligada"}`).join(", ");
    const acesas = Object.entries(this.lampadas());
    if (acesas.length)
      txt += " | " + acesas.map(([u, v]) => `${this.el[u].nome || "lâmpada"}=${v ? "ACESA" : "apagada"}`).join(", ");
    const { motores, avisos } = this.forca();
    if (motores.length) txt += " | " + motores.join(", ");
    const viz = this.grafo();
    const vL = this.alcancaveis("L", "fonte", viz), vN = this.alcancaveis("N", "fonte", viz);
    if ([...vL].some(x => vN.has(x))) avisos.push("CURTO-CIRCUITO L-N no comando");
    if (avisos.length) txt += " | ATENÇÃO: " + avisos.join(", ");
    return txt;
  }

  /* --- ações --- */
  uuidDe(nome, papeis) {
    for (const [u, e] of Object.entries(this.el))
      if (e.nome.toLowerCase() === nome.toLowerCase() && papeis.includes(e.papel)) return u;
    return null;
  }
  pressionar(u, valor) {
    this.pressionado[u] = valor;
    const s = this.resolver();
    return { situacao: s, disparos: this.disparosPorCurto() };
  }
  protecao(u) {
    if (u in this.disj_ligado) this.disj_ligado[u] = !this.disj_ligado[u];
    else if (u in this.disparado) this.disparado[u] = !this.disparado[u];
    else return null;
    const s = this.resolver();
    return { situacao: s, disparos: this.disparosPorCurto() };
  }
  passo(dt = 0.1) {
    this.relogio += dt;
    for (const u of Object.keys(this.energizada)) {
      if (this.energizada[u]) this.t_ligada[u] += dt; else this.t_desligada[u] += dt;
    }
    const s = this.resolver();
    return { situacao: s, disparos: this.disparosPorCurto() };
  }

  /* --- para a interface: o que está energizado --- */
  energia() {
    const viz = this.grafo();
    const { fases, detalhe, avisos } = this.forca();
    const vL = this.alcancaveis("L", "fonte", viz), vN = this.alcancaveis("N", "fonte", viz);
    const fase = new Set([...vL, ...fases.L1, ...fases.L2, ...fases.L3]);
    return { fase, neutro: vN, motores: detalhe, avisos, lampadas: this.lampadas(viz) };
  }
}

const api = { lerCircuito, classificar, tipoBotoeira, Simulador, tempoDoDesenho };
if (typeof module !== "undefined" && module.exports) module.exports = api;
else raiz.QetMotor = api;
})(typeof window !== "undefined" ? window : globalThis);
