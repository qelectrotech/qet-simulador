"""Executa os cenários de tests/cenarios.json no motor Python e imprime o estado após cada ação.
Uso: python tests/paridade.py  (a saída deve ser idêntica à de: node tests/paridade.js)"""
import json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "simulador"))
from simulador import ler_circuito, Simulador

def rodar(arquivo, acoes):
    sim = Simulador(*ler_circuito(os.path.join(AQUI, "..", "circuitos-qet", arquivo)))
    sim.resolver()
    linhas = [f"{arquivo} inicio: {sim.estado()}"]
    def nome_para(nome, papeis):
        return next(u for u, e in sim.el.items() if e["nome"].lower() == nome.lower() and e["papel"] in papeis)
    for tipo, arg in acoes:
        msgs = []
        if tipo == "p":
            u = nome_para(arg, ["botoeira"])
            for v in (True, False):
                sim.pressionado[u] = v; sim.resolver(); msgs += sim.disparos_por_curto()
        elif tipo == "x":
            u = nome_para(arg, ["disjuntor", "termico"])
            if u in sim.disj_ligado: sim.disj_ligado[u] = not sim.disj_ligado[u]
            else: sim.disparado[u] = not sim.disparado[u]
            sim.resolver(); msgs += sim.disparos_por_curto()
        elif tipo == "t":
            for _ in range(int(round(arg / 0.1))):
                sim.relogio += 0.1
                for b in sim.energizada:
                    if sim.energizada[b]: sim.t_ligada[b] += 0.1
                    else: sim.t_desligada[b] += 0.1
                sim.resolver(); msgs += sim.disparos_por_curto()
        linhas.append(f"{arquivo} {tipo} {arg}: {sim.estado()}" + (f" || {'; '.join(msgs)}" if msgs else ""))
    return linhas

for arq, acoes in json.load(open(os.path.join(AQUI, "cenarios.json"), encoding="utf-8")).items():
    print("\n".join(rodar(arq, acoes)))
