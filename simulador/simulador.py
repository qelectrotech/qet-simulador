"""
Protótipo do simulador de comandos elétricos (Passo 2).

Lê um arquivo .qet do QElectroTech e simula o circuito de comando
no terminal. Sem interface gráfica: o objetivo é validar o modelo.

Uso:
    python simulador.py ..\\circuitos-qet\\partida_direta.qet
Depois digite os comandos (ex.: S1, +S1, -S1, t 5, sair).
"""
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, deque


# ---------------------------------------------------------------
# 1. LEITURA DO ARQUIVO .qet
# ---------------------------------------------------------------
def ler_definicoes(raiz):
    """Lê a 'biblioteca' embutida no .qet: o que cada símbolo é."""
    defs = {}
    for el in raiz.find("collection").iter("element"):
        d = el.find("definition")
        if d is None:
            continue
        kind = {}
        ki = d.find("kindInformations")
        if ki is not None:
            for k in ki:
                kind[k.attrib.get("name")] = (k.text or "").strip()
        bornes = {t.attrib["uuid"]: t.attrib.get("name", "")
                  for t in d.iter("terminal")}
        nomes = [(n.text or "").strip() for n in d.iter("name")]  # nome em cada idioma
        geo = {t.attrib["uuid"]: (float(t.attrib.get("x", 0)), float(t.attrib.get("y", 0)))
               for t in d.iter("terminal")}
        defs[el.attrib["name"]] = {
            "link_type": d.attrib.get("link_type", "simple"),
            "kind": kind,
            "bornes": bornes,
            "nomes": nomes,
            "geo": geo,                      # posição de cada borne no símbolo
        }
    return defs


def tipo_botoeira(nome_arquivo, definicao):
    """Decide se uma botoeira é NA (NO) ou NF (NC). Tenta, em ordem:
    1. numeração IEC dos bornes (x3-x4 = NA, x1-x2 = NF);
    2. nome do arquivo do símbolo (ex.: foot_no.elmt, poussoir_nf.elmt);
    3. nome do elemento na biblioteca, em qualquer idioma (ex.: "Botão de pressão (NA)").
    Devolve (estado, origem) ou (None, None) se não for possível decidir."""
    nomes = [n for n in definicao["bornes"].values() if n]
    # só vale para bornes numerados (13-14, 21-22...), não para A1-A2 ou L-N
    finais = {n[-1:] for n in nomes} if nomes and all(n.isdigit() for n in nomes) else set()
    if finais == {"3", "4"}:
        return "NO", "bornes"
    if finais == {"1", "2"}:
        return "NC", "bornes"

    partes = set(re.split(r"[^a-z]+", nome_arquivo.lower().rsplit(".", 1)[0]))
    no, nc = bool(partes & {"no", "na"}), bool(partes & {"nc", "nf"})
    if no != nc:
        return ("NO" if no else "NC"), "nome do arquivo"

    texto = " ".join(definicao["nomes"])
    no = bool(re.search(r"\b(NO|NA)\b", texto))
    nc = bool(re.search(r"\b(NC|NF)\b", texto))
    if no != nc:
        return ("NO" if no else "NC"), "nome do elemento"
    return None, None


def e_emergencia(tipo, definicao):
    """Parada de emergência: fica travada quando acionada (só destrava ao acionar de novo)."""
    return bool(re.search(r"urgence|emergenc|emergênc|not-?aus|e-?stop", tipo, re.I)
                or re.search(r"emergency|urgence|emerg[eê]ncia|not-?aus", " ".join(definicao["nomes"]), re.I))


def classificar(tipo, definicao):
    """Decide o papel do elemento no simulador. Devolve (papel, estado, origem)."""
    lt, kind = definicao["link_type"], definicao["kind"]
    nomes_bornes = set(definicao["bornes"].values())
    arquivo = tipo.split("/")[-1].lower()
    texto = " ".join(definicao["nomes"])
    if lt in ("next_report", "previous_report"):
        return "renvoi", None, None            # referência de página: liga um fio entre folhas
    if lt == "simple" and nomes_bornes and nomes_bornes <= {"L", "N"}:
        return "fonte", None, None             # fonte L+N, ou só fase (L) ou só neutro (N)
    if {"L1", "L2", "L3"} <= nomes_bornes:
        return "fonte3f", None, None
    if lt == "master" and kind.get("type") == "coil":
        return "bobina", None, None
    if lt == "master" and kind.get("type") == "protection":
        # Relé térmico: os polos de força nunca abrem; o disparo atua os contatos auxiliares.
        # Disjuntor/seccionador: os polos abrem quando ele é desligado.
        if arquivo.startswith("relais_therm") or re.search(
                r"thermal relay|relais thermique|rel[eé] t[eé]rmico|thermorelais",
                texto, re.I):
            return "termico", None, None
        return "disjuntor", None, None
    if lt == "simple" and len(definicao["bornes"]) == 2 and (
            re.search(r"lamp|voyant|lampara|signal", arquivo)
            or re.search(r"\blight\b|\blamp|\blampe\b|l[aá]mpara|l[aâ]mpada|\bvoyant", texto, re.I)):
        return "lampada", None, None           # lâmpada de sinalização: carga entre L e N
    if lt == "simple" and (re.search(r"fus[eií]|pojistka", arquivo) or "/10_fuses/" in tipo
                           or re.search(r"\bfuse|\bfusible|\bfus[ií]vel", texto, re.I)):
        return "fusivel", None, None           # fusível: sempre conduz
    if lt == "simple" and (arquivo.startswith("moto")
                           or re.search(r"\bmotor|\bmoteur", texto, re.I)):
        return "motor", None, None
    if lt == "slave":
        return "contato", kind.get("state", "NO"), "kindInformations"  # NO ou NC

    # Botoeira: elemento de 2 bornes, "simple" ou mestre do tipo "commutator"
    # (os botões de pressão da biblioteca do QElectroTech são desse tipo)
    if len(definicao["bornes"]) == 2 and (lt == "simple"
                                          or kind.get("type") == "commutator"):
        arquivo = tipo.split("/")[-1]
        estado, origem = tipo_botoeira(arquivo, definicao)
        if e_emergencia(tipo, definicao):
            # Parada de emergência: NF, a não ser que a numeração dos bornes diga outra coisa
            return "botoeira", (estado if origem == "bornes" else "NC"), "parada de emergência"
        if estado:
            return "botoeira", estado, origem
        if kind.get("type") == "commutator" or "push_button" in tipo:
            return "botoeira", None, None      # é botoeira, mas NA/NF indefinido
    return "desconhecido", None, None


def ler_circuito(caminho):
    raiz = ET.parse(caminho).getroot()
    defs = ler_definicoes(raiz)
    diagramas = raiz.findall("diagram")      # todas as folhas do projeto

    elementos = {}
    for e in (e for dg in diagramas for e in dg.find("elements")):
        arquivo = e.attrib["type"].split("/")[-1]
        d = defs[arquivo]
        info = {}
        ei = e.find("elementInformations")
        if ei is not None:
            info = {i.attrib.get("name"): (i.text or "").strip() for i in ei}
        papel, estado, origem = classificar(e.attrib["type"], d)
        elementos[e.attrib["uuid"]] = {
            "papel": papel,
            "estado_normal": estado,
            "origem_estado": origem,
            "nome": info.get("label", ""),
            "bornes": d["bornes"],          # uuid do borne -> nome (A1, 13...)
            "geo": d["geo"],
            "vinculos": [l.attrib["uuid"] for l in e.iter("link_uuid")],
            "tipo_contato": d["kind"].get("type", "simple"),  # simple, delayOn, delayOff
            "trava": papel == "botoeira" and e_emergencia(e.attrib["type"], d),
            "info": info,
        }

    # Contato sem nome herda o nome da bobina vinculada
    for el in elementos.values():
        if el["papel"] == "contato" and not el["nome"] and el["vinculos"]:
            el["nome"] = elementos[el["vinculos"][0]]["nome"]

    fios = [((c.attrib["element1"], c.attrib["terminal1"]),
             (c.attrib["element2"], c.attrib["terminal2"]))
            for dg in diagramas for c in dg.find("conductors")]
    # Referência de página (renvoi de folio): o borne de cada ponta é o mesmo ponto elétrico
    for u, el in elementos.items():
        for v in el["vinculos"]:
            par = elementos.get(v)
            if el["papel"] == "renvoi" and par and par["papel"] == "renvoi" and u < v:
                fios.append(((u, next(iter(el["bornes"]))), (v, next(iter(par["bornes"])))))
    return elementos, fios


# ---------------------------------------------------------------
# 2. MOTOR DE SIMULAÇÃO
# ---------------------------------------------------------------
class Simulador:
    def __init__(self, elementos, fios):
        self.el = elementos
        self.fios = fios
        self.pressionado = {u: False for u, e in elementos.items()
                            if e["papel"] == "botoeira"}
        self.energizada = {u: False for u, e in elementos.items()
                           if e["papel"] == "bobina"}
        # Temporização: tempo ajustado (s) e cronômetros de cada bobina
        self.relogio = 0.0
        self.t_ajuste = {u: tempo_do_desenho(elementos[u])
                         for u in self.energizada if self.e_temporizador(u)}
        self.t_ligada = {u: 0.0 for u in self.energizada}            # há quanto tempo energizada
        self.t_desligada = {u: float("inf") for u in self.energizada} # há quanto tempo desligada
        # Proteções: disjuntor começa ligado; térmico começa sem disparo
        self.disj_ligado = {u: True for u, e in elementos.items() if e["papel"] == "disjuntor"}
        self.disparado = {u: False for u, e in elementos.items() if e["papel"] == "termico"}

    def e_temporizador(self, bobina):
        """Uma bobina é temporizador se algum contato dela for retardado."""
        return any(e["papel"] == "contato" and bobina in e["vinculos"]
                   and e["tipo_contato"] in ("delayOn", "delayOff")
                   for e in self.el.values())

    # --- estado de cada chave/contato ---------------------------
    def fechado(self, uuid):
        e = self.el[uuid]
        if e["papel"] == "botoeira":
            atuado = self.pressionado[uuid]
        elif e["papel"] == "contato":
            atuado = any(self.mestre_atuado(e["tipo_contato"], m) for m in e["vinculos"])
        else:
            return False
        if e["estado_normal"] is None:     # botoeira de tipo indefinido: fica aberta
            return False
        return atuado if e["estado_normal"] == "NO" else not atuado

    def mestre_atuado(self, tipo, mestre):
        """O contato está atuado? Depende do tipo de elemento ao qual ele está vinculado."""
        if mestre in self.energizada:
            return self.contato_atuado(tipo, mestre)
        if mestre in self.disj_ligado:      # auxiliar de disjuntor: atua com ele ligado
            return self.disj_ligado[mestre]
        if mestre in self.disparado:        # auxiliar de térmico: atua no disparo
            return self.disparado[mestre]
        return self.pressionado.get(mestre, False)

    def contato_atuado(self, tipo, bobina):
        ligada = self.energizada[bobina]
        T = self.t_ajuste.get(bobina, 0.0)
        if tipo == "delayOn":     # retardo na energização
            return ligada and self.t_ligada[bobina] >= T - 1e-9
        if tipo == "delayOff":    # retardo na desenergização
            return ligada or self.t_desligada[bobina] < T - 1e-9
        return ligada             # contato comum

    # --- polos: pares de bornes que uma chave liga entre si --------
    def polos(self, u):
        """Um contato de 2 bornes tem 1 polo. Em contatos de potência, disjuntores e
        térmicos, cada polo é o par de bornes alinhados verticalmente no símbolo."""
        bornes = list(self.el[u]["bornes"])
        if len(bornes) == 2:
            return [tuple(bornes)]
        colunas = defaultdict(list)
        for t in bornes:
            x, y = self.el[u]["geo"][t]
            colunas[round(x)].append((y, t))
        return [(c[0][1], c[-1][1]) for c in
                (sorted(v) for v in colunas.values()) if len(c) == 2]

    def conduz(self, u):
        papel = self.el[u]["papel"]
        if papel in ("botoeira", "contato"):
            return self.fechado(u)
        if papel == "disjuntor":
            return self.disj_ligado[u]
        if papel in ("termico", "fusivel"):  # polos do térmico e fusível sempre conduzem
            return True
        return False

    def grafo(self):
        viz = defaultdict(set)
        for a, b in self.fios:                      # fios sempre conduzem
            viz[a].add(b); viz[b].add(a)
        for u in self.el:                           # chaves fechadas conduzem
            if self.conduz(u):
                for t1, t2 in self.polos(u):
                    viz[(u, t1)].add((u, t2)); viz[(u, t2)].add((u, t1))
        return viz

    # --- quais bornes estão "vivos" a partir de uma origem ----------
    def alcancaveis(self, nome_origem, papel_fonte="fonte", viz=None):
        viz = viz if viz is not None else self.grafo()
        origem = [(u, t) for u, e in self.el.items() if e["papel"] == papel_fonte
                  for t, n in e["bornes"].items() if n == nome_origem]
        vistos, fila = set(origem), deque(origem)
        while fila:
            n = fila.popleft()
            for m in viz[n] - vistos:
                vistos.add(m); fila.append(m)
        return vistos

    # --- circuito de força ---------------------------------------
    def forca(self):
        """Estado de cada motor e avisos de curto-circuito."""
        viz = self.grafo()
        fases = {f: self.alcancaveis(f, "fonte3f", viz) for f in ("L1", "L2", "L3")}
        avisos = []
        for a, b in (("L1", "L2"), ("L2", "L3"), ("L1", "L3")):
            if fases[a] & fases[b]:
                avisos.append(f"CURTO-CIRCUITO {a}-{b}")
        motores = []
        for u, e in self.el.items():
            if e["papel"] != "motor":
                continue
            nome = e["nome"] or "motor"
            por_nome = {n: t for t, n in e["bornes"].items()}
            if {"U1", "V1", "W1", "U2", "V2", "W2"} <= set(por_nome):
                motores.append(f"{nome}: {self.motor_6_bornes(u, por_nome, fases, viz)}")
                continue
            # bornes na ordem do símbolo (U, V, W) e a fase que chega em cada um
            ordem = sorted(e["bornes"], key=lambda t: e["geo"][t])
            chegam = [[f for f in fases if (u, t) in fases[f]] for t in ordem]
            recebidas = [c[0] for c in chegam if len(c) == 1]
            if any(len(c) > 1 for c in chegam):
                motores.append(f"{nome}: EM CURTO (duas fases no mesmo borne)")
            elif len(recebidas) == 3 and len(set(recebidas)) == 3:
                i = recebidas.index("L1")
                seq = recebidas[i:] + recebidas[:i]
                sentido = "horário" if seq == ["L1", "L2", "L3"] else "anti-horário"
                motores.append(f"{nome}: GIRANDO ({sentido})")
            elif recebidas:
                motores.append(f"{nome}: FALTA DE FASE ({', '.join(sorted(set(recebidas)))})")
            else:
                motores.append(f"{nome}: parado")
        return motores, avisos

    def motor_6_bornes(self, u, t, fases, viz):
        """Motor de 6 bornes: estrela se U2, V2 e W2 estão unidos entre si (sem fase);
        triângulo se U2, V2 e W2 recebem as fases de V1, W1 e U1 (U1-W2, V1-U2, W1-V2)."""
        fase = lambda n: [f for f in fases if (u, t[n]) in fases[f]]
        ent = [fase(n) for n in ("U1", "V1", "W1")]
        sai = [fase(n) for n in ("U2", "V2", "W2")]
        if any(len(c) > 1 for c in ent + sai):
            return "EM CURTO (duas fases no mesmo borne)"
        if not all(len(c) == 1 for c in ent) or len({c[0] for c in ent}) != 3:
            recebidas = sorted({c[0] for c in ent + sai if c})
            return f"FALTA DE FASE ({', '.join(recebidas)})" if recebidas else "parado"
        seq = [c[0] for c in ent]
        i = seq.index("L1")
        sentido = "horário" if seq[i:] + seq[:i] == ["L1", "L2", "L3"] else "anti-horário"
        if not any(sai):
            # ponto estrela: U2, V2 e W2 ligados entre si
            comp, fila = {(u, t["U2"])}, deque([(u, t["U2"])])
            while fila:
                n = fila.popleft()
                for m in viz[n] - comp:
                    comp.add(m); fila.append(m)
            if (u, t["V2"]) in comp and (u, t["W2"]) in comp:
                return f"GIRANDO em estrela ({sentido})"
            return "ENROLAMENTOS ABERTOS (sem fechamento estrela ou triângulo)"
        if [c[0] if c else None for c in sai] == [seq[1], seq[2], seq[0]]:
            return f"GIRANDO em triângulo ({sentido})"
        return "LIGAÇÃO INCORRETA dos enrolamentos"

    # --- resolve até estabilizar ---------------------------------
    def resolver(self, max_iter=50):
        for _ in range(max_iter):
            viz = self.grafo()
            vL, vN = self.alcancaveis("L", viz=viz), self.alcancaveis("N", viz=viz)
            mudou = False
            for u in self.energizada:
                a, b = [(u, t) for t in self.el[u]["bornes"]]
                novo = (a in vL and b in vN) or (b in vL and a in vN)
                if novo != self.energizada[u]:
                    self.energizada[u] = novo
                    if novo:
                        self.t_ligada[u] = 0.0
                    else:
                        self.t_desligada[u] = 0.0
                    mudou = True
            if not mudou:
                return "estável"
        return "OSCILANDO"

    # --- disjuntor dispara sozinho em curto-circuito ----------------
    def disparos_por_curto(self):
        """Se houver curto entre fases, desarma o disjuntor que o alimenta."""
        _, avisos = self.forca()
        curtos = [a for a in avisos if a.startswith("CURTO-CIRCUITO")]
        msgs = []
        for u in self.disj_ligado:
            if not curtos:
                break
            if not self.disj_ligado[u]:
                continue
            self.disj_ligado[u] = False            # testa: desligar este resolve o curto?
            _, depois = self.forca()
            resolvidos = [c for c in curtos if c not in depois]
            if resolvidos:
                fases = ", ".join(c.replace("CURTO-CIRCUITO ", "") for c in resolvidos)
                msgs.append(f"{self.el[u]['nome'] or 'disjuntor'} DISPAROU (curto-circuito {fases})")
                curtos = [c for c in curtos if c in depois]
            else:
                self.disj_ligado[u] = True         # não era este; volta a ligar
        if msgs:
            self.resolver()
        return msgs

    def mostrar_disparos(self):
        for m in self.disparos_por_curto():
            print(f"  t={self.relogio:5.1f}s  >>> {m}  -> {self.estado()}")

    # --- interação ----------------------------------------------
    def uuid_de(self, nome):
        for u, e in self.el.items():
            if e["nome"].lower() == nome.lower() and e["papel"] == "botoeira":
                return u
        raise KeyError(f"Botoeira '{nome}' não encontrada")

    def lampadas(self, viz=None):
        """Lâmpada acesa: fase (L) num borne e neutro (N) no outro, como uma bobina."""
        viz = viz if viz is not None else self.grafo()
        vL, vN = self.alcancaveis("L", viz=viz), self.alcancaveis("N", viz=viz)
        r = {}
        for u, e in self.el.items():
            if e["papel"] == "lampada":
                a, b = [(u, t) for t in e["bornes"]]
                r[u] = (a in vL and b in vN) or (b in vL and a in vN)
        return r

    def estado(self):
        txt = ", ".join(
            f"{self.el[u]['nome']}={'ENERGIZADA' if v else 'desligada'}"
            for u, v in self.energizada.items())
        acesas = self.lampadas()
        if acesas:
            txt += " | " + ", ".join(f"{self.el[u]['nome'] or 'lâmpada'}={'ACESA' if v else 'apagada'}"
                                     for u, v in acesas.items())
        motores, avisos = self.forca()
        if motores:
            txt += " | " + ", ".join(motores)
        viz = self.grafo()
        if self.alcancaveis("L", viz=viz) & self.alcancaveis("N", viz=viz):
            avisos.append("CURTO-CIRCUITO L-N no comando")
        if avisos:
            txt += " | ATENÇÃO: " + ", ".join(avisos)
        return txt

    def acao(self, nome, pressionar):
        self.pressionado[self.uuid_de(nome)] = pressionar
        situacao = self.resolver()
        verbo = "pressiona" if pressionar else "solta    "
        print(f"  t={self.relogio:5.1f}s {verbo} {nome:<4} -> {self.estado()}   [{situacao}]")
        self.mostrar_disparos()

    def avancar(self, segundos, dt=0.1):
        """Avança o tempo simulado em passos de dt, mostrando só o que muda."""
        passos = int(round(segundos / dt))
        anterior = self.estado()
        for _ in range(passos):
            self.relogio += dt
            for u in self.energizada:
                if self.energizada[u]:
                    self.t_ligada[u] += dt
                else:
                    self.t_desligada[u] += dt
            situacao = self.resolver()
            atual = self.estado()
            if atual != anterior:
                print(f"  t={self.relogio:5.1f}s           -> {atual}   [{situacao}]")
                self.mostrar_disparos()
                anterior = self.estado()
        print(f"  t={self.relogio:5.1f}s (fim)      -> {self.estado()}")

    def protecao(self, nome):
        """Liga/desliga um disjuntor ou provoca/rearma a sobrecarga de um térmico."""
        for u, e in self.el.items():
            if e["nome"].lower() != nome.lower():
                continue
            if u in self.disj_ligado:
                self.disj_ligado[u] = not self.disj_ligado[u]
                acao = "liga     " if self.disj_ligado[u] else "desliga  "
            elif u in self.disparado:
                self.disparado[u] = not self.disparado[u]
                acao = "SOBRECARGA" if self.disparado[u] else "rearma   "
            else:
                continue
            situacao = self.resolver()
            print(f"  t={self.relogio:5.1f}s {acao} {e['nome']:<4} -> {self.estado()}   [{situacao}]")
            self.mostrar_disparos()
            return True
        return False

    def ajustar_tempo(self, nome, segundos):
        for u in self.t_ajuste:
            if self.el[u]["nome"].lower() == nome.lower():
                self.t_ajuste[u] = segundos
                print(f"  {self.el[u]['nome']} ajustado para {segundos:g} s")
                return
        raise KeyError(f"Temporizador '{nome}' não encontrado")


def tempo_do_desenho(elemento, padrao=5.0):
    """Procura um tempo escrito em qualquer campo do elemento (ex.: '5s', 't=2,5 s').
    O QElectroTech não tem campo de tempo; se nada for encontrado, usa o padrão."""
    for valor in elemento["info"].values():
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*s\b", valor)
        if m:
            return float(m.group(1).replace(",", "."))
    return padrao


# ---------------------------------------------------------------
# 3. EXECUÇÃO
# ---------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    elementos, fios = ler_circuito(sys.argv[1])

    print("Elementos encontrados:")
    for e in elementos.values():
        extra = f" ({e['estado_normal']})" if e["estado_normal"] else ""
        if e.get("trava"):
            extra += "  [parada de emergência: trava ao acionar]"
        elif e["papel"] == "botoeira" and e["origem_estado"] not in (None, "bornes"):
            extra += f"  [tipo deduzido pelo {e['origem_estado']}]"
        if e["papel"] == "contato" and e["tipo_contato"] == "power":
            extra += ", potência"
        print(f"  {e['papel']:<9} {e['nome'] or '-'}{extra}")
    print(f"Fios: {len(fios)}")
    sem_nome = [e for e in elementos.values()
                if e["papel"] == "botoeira" and not e["nome"]]
    if sem_nome:
        print(f"\nATENÇÃO: {len(sem_nome)} botoeira(s) sem nome no desenho. "
              "Elas não podem ser acionadas. Dê nome a elas no QElectroTech.")

    indefinidas = [e for e in elementos.values()
                   if e["papel"] == "botoeira" and not e["estado_normal"]]
    for e in indefinidas:
        print(f"ATENÇÃO: não foi possível saber se a botoeira {e['nome'] or '(sem nome)'} "
              "é NA ou NF. Numere os bornes (13-14 = NA, 21-22 = NF).")
    desconhecidos = [e for e in elementos.values() if e["papel"] == "desconhecido"]
    if desconhecidos:
        print(f"Aviso: {len(desconhecidos)} elemento(s) ignorado(s) pelo simulador: "
              + ", ".join(sorted({e['nome'] or '(sem nome)' for e in desconhecidos})))
    soltos = [e for e in elementos.values()
              if e["papel"] == "contato" and not e["vinculos"]]
    if soltos:
        print(f"ATENÇÃO: {len(soltos)} contato(s) sem vínculo com bobina. "
              "Eles nunca vão atuar.")
    for u, e in elementos.items():
        if e["papel"] in ("disjuntor", "termico"):
            aux = [c for c in elementos.values() if u in c["vinculos"]]
            desc = ", ".join(f"{c['estado_normal']}" for c in aux) or "nenhum"
            print(f"{'Disjuntor' if e['papel'] == 'disjuntor' else 'Relé térmico'} "
                  f"{e['nome'] or '-'}: contatos auxiliares vinculados: {desc}")

    sim = Simulador(elementos, fios)
    nomes_tipo = {"delayOn": "retardo na energização",
                  "delayOff": "retardo na desenergização"}
    for u, T in sim.t_ajuste.items():
        tipos = {e["tipo_contato"] for e in elementos.values()
                 if u in e["vinculos"] and e["tipo_contato"] != "simple"}
        desc = ", ".join(nomes_tipo.get(t, t) for t in tipos)
        print(f"Temporizador {elementos[u]['nome']}: {T:g} s ({desc})")
    situacao = sim.resolver()
    print(f"\nEstado inicial: {sim.estado()}   [{situacao}]")
    print("""
Comandos:
  S1          pulso (pressiona e solta)
  +S1         mantém pressionada
  -S1         solta
  t 5         avança 5 segundos
  tempo KT1 3 ajusta o temporizador KT1 para 3 s
  Q1          liga/desliga o disjuntor Q1
  F1          provoca/rearma sobrecarga no relé térmico F1
  sair        encerra
""")
    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        if cmd.lower() in ("sair", "q"):
            break
        partes = cmd.split()
        try:
            if partes[0].lower() == "t" and len(partes) == 2:
                sim.avancar(float(partes[1].replace(",", ".")))
            elif partes[0].lower() == "tempo" and len(partes) == 3:
                sim.ajustar_tempo(partes[1], float(partes[2].replace(",", ".")))
            elif cmd[0] == "+":
                sim.acao(cmd[1:], True)
            elif cmd[0] == "-":
                sim.acao(cmd[1:], False)
            elif sim.protecao(cmd):
                pass
            elif sim.el[sim.uuid_de(cmd)].get("trava"):
                u = sim.uuid_de(cmd)                 # parada de emergência: trava/destrava
                sim.acao(cmd, not sim.pressionado[u])
            else:
                sim.acao(cmd, True)
                sim.acao(cmd, False)
        except KeyError as erro:
            print(" ", erro.args[0])
        except ValueError:
            print("  Valor inválido. Exemplo: t 5")


if __name__ == "__main__":
    main()
