// Test utility: evaluates the formula subset used by auditWorkbook (spreadsheet semantics: a blank cell is 0 in
// arithmetic and not a number for ISNUMBER; AVERAGE skips non-numbers). Not used by the page.
// evalWorkbook(model) -> {sheetName: rows of computed values}
"use strict";
const ERR = {err: true};
function colNum(s) { let n = 0; for (const ch of s) n = n * 26 + ch.charCodeAt(0) - 64; return n - 1; }
function tokenize(src) {
  const t = [], re = /\s*(?:('(?:[^']|'')+'!|[A-Za-z_][A-Za-z0-9_ ]*!)?(\$?[A-Z]{1,2}\$?\d+)|(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|("(?:[^"]|"")*")|([A-Z]+)\(|(<=|>=|<>|[-+*/^(),<>=]))/y;
  let m; re.lastIndex = 0;
  while (re.lastIndex < src.length) {
    const at = re.lastIndex; m = re.exec(src);
    if (!m) throw new Error("cannot parse at " + at + ": " + src);
    if (m[2]) t.push({ref: m[2].replace(/\$/g, ""), sheet: m[1] ? m[1].slice(0, -1).replace(/^'|'$/g, "").replace(/''/g, "'") : null});
    else if (m[3]) t.push({num: +m[3]});
    else if (m[4]) t.push({str: m[4].slice(1, -1).replace(/""/g, '"')});
    else if (m[5]) t.push({fn: m[5]});
    else t.push({op: m[6]});
  }
  return t;
}
function evalWorkbook(model) {
  const rows = {}, memo = {};
  model.sheets.forEach(s => { rows[s.name] = s.rows; memo[s.name] = {}; });
  function cell(sheet, ref) {
    const key = ref; if (key in memo[sheet]) return memo[sheet][key];
    const m = /^([A-Z]+)(\d+)$/.exec(ref), r = +m[2] - 1, c = colNum(m[1]);
    const row = rows[sheet][r], x = row && row[c];
    memo[sheet][key] = ERR;  // cycle guard
    const v = !x ? null : "f" in x ? evalFormula(x.f, sheet) : x.v;
    memo[sheet][key] = v; return v;
  }
  const num = v => v === null || v === undefined || v === "" ? 0 : typeof v === "number" ? v : typeof v === "boolean" ? +v : ERR;
  function evalFormula(f, sheet) {
    const t = tokenize(f.replace(/^=/, "")); let i = 0;
    const peek = () => t[i], take = () => t[i++];
    function args() { const a = []; if (peek() && peek().op === ")") { take(); return a; }
      for (;;) { a.push(parseCmp()); const n = take(); if (n.op === ")") return a; if (n.op !== ",") throw new Error("bad args " + f); } }
    function primary() {
      const x = take();
      if (x.num !== undefined) return () => x.num;
      if (x.str !== undefined) return () => x.str;
      if (x.ref) return () => cell(x.sheet || sheet, x.ref);
      if (x.op === "(") { const e = parseCmp(); take(); return e; }
      if (x.op === "-") { const e = power(); return () => { const v = num(e()); return v === ERR ? ERR : -v; }; }
      if (x.op === "+") return power();
      if (x.fn) { const a = args(), F = x.fn;
        return () => {
          if (F === "IF") { const c = a[0](); if (c === ERR) return ERR; return (typeof c === "string" ? c !== "" : num(c) !== 0) ? a[1]() : a.length > 2 ? a[2]() : false; }
          const v = a.map(g => g());
          if (F === "ISNUMBER") return typeof v[0] === "number";
          if (F === "COUNT") return v.filter(z => typeof z === "number").length;
          if (F === "HYPERLINK") return v[1];
          if (v.some(z => z === ERR)) return ERR;
          if (F === "AND") return v.every(z => num(z) !== 0);
          if (F === "ABS") return Math.abs(num(v[0]));
          if (F === "MAX") return Math.max(...v.map(num));
          if (F === "AVERAGE") { const n = v.filter(z => typeof z === "number"); return n.length ? n.reduce((s, z) => s + z, 0) / n.length : ERR; }
          throw new Error("function " + F);
        }; }
      throw new Error("unexpected token in " + f + ": " + JSON.stringify(x));
    }
    function power() { let l = primary(); while (peek() && peek().op === "^") { take(); const L = l, r = primary(); l = () => { const a = num(L()), b = num(r()); return a === ERR || b === ERR ? ERR : Math.pow(a, b); }; } return l; }
    function term() { let l = power(); while (peek() && (peek().op === "*" || peek().op === "/")) { const o = take().op, L = l, r = power();
      l = () => { const a = num(L()), b = num(r()); if (a === ERR || b === ERR) return ERR; if (o === "/") return b === 0 ? ERR : a / b; return a * b; }; } return l; }
    function sum() { let l = term(); while (peek() && (peek().op === "+" || peek().op === "-")) { const o = take().op, L = l, r = term();
      l = () => { const a = num(L()), b = num(r()); return a === ERR || b === ERR ? ERR : o === "+" ? a + b : a - b; }; } return l; }
    function parseCmp() { let l = sum(); while (peek() && ["<", ">", "<=", ">=", "=", "<>"].includes(peek().op)) { const o = take().op, L = l, r = sum();
      l = () => { let a = L(), b = r(); if (a === ERR || b === ERR) return ERR; if (typeof a !== "string" || typeof b !== "string") { a = typeof a === "string" ? a : num(a); b = typeof b === "string" ? b : num(b); }
        return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b, "=": a === b, "<>": a !== b}[o]; }; } return l; }
    const e = parseCmp(); if (i !== t.length) throw new Error("trailing tokens in " + f);
    return e();
  }
  const out = {};
  model.sheets.forEach(s => { out[s.name] = s.rows.map((row, r) => (row || []).map((x, c) => x ? cell(s.name, String.fromCharCode(65 + c) + (r + 1)) : null)); });
  return out;
}
module.exports = {evalWorkbook, ERR};
