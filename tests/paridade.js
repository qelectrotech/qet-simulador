/* Executa os cenários de tests/cenarios.json no motor JavaScript (web/motor.js).
   Uso: npm i @xmldom/xmldom && node tests/paridade.js
   A saída deve ser idêntica à de: python tests/paridade.py */
const fs = require("fs"), path = require("path");
const { DOMParser } = require("@xmldom/xmldom");
const { lerCircuito, Simulador } = require("../web/motor.js");
const AQUI = __dirname;

function rodar(arquivo, acoes) {
  const xml = fs.readFileSync(path.join(AQUI, "..", "circuitos-qet", arquivo), "utf8");
  const sim = new Simulador(lerCircuito(new DOMParser().parseFromString(xml, "text/xml")));
  sim.resolver();
  const linhas = [`${arquivo} inicio: ${sim.estado()}`];
  for (const [tipo, arg] of acoes) {
    let msgs = [];
    if (tipo === "p") {
      const u = sim.uuidDe(arg, ["botoeira"]);
      msgs = msgs.concat(sim.pressionar(u, true).disparos, sim.pressionar(u, false).disparos);
    } else if (tipo === "x") {
      msgs = msgs.concat(sim.protecao(sim.uuidDe(arg, ["disjuntor", "termico"])).disparos);
    } else if (tipo === "t") {
      for (let i = 0; i < Math.round(arg / 0.1); i++) msgs = msgs.concat(sim.passo(0.1).disparos);
    }
    linhas.push(`${arquivo} ${tipo} ${arg}: ${sim.estado()}` + (msgs.length ? ` || ${msgs.join("; ")}` : ""));
  }
  return linhas;
}

const cen = JSON.parse(fs.readFileSync(path.join(AQUI, "cenarios.json"), "utf8"));
for (const [arq, acoes] of Object.entries(cen)) console.log(rodar(arq, acoes).join("\n"));
