// 一次性：打印指定引擎函数的注册体（看清它到底读哪些参数键）
import fs from "node:fs";
import path from "node:path";

const root = "C:/Users/fsafsafsa/Desktop/cppcshap/MF_Mathematics";
const want = process.argv.slice(2);
const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (!["build", ".git", "__pycache__"].includes(e.name)) walk(p); }
    else if (e.name.endsWith(".cpp")) files.push(p);
  }
})(root);

for (const fn of want) {
  const tag = `register_function("${fn}"`;
  let found = false;
  for (const f of files) {
    const t = fs.readFileSync(f, "utf8");
    const i = t.indexOf(tag);
    if (i < 0) continue;
    found = true;
    const start = t.indexOf("(", i + "register_function".length);
    let depth = 0, j = start, end = start;
    for (; j < t.length; j++) {
      const c = t[j];
      if (c === '"') { j++; while (j < t.length && t[j] !== '"') { if (t[j] === "\\") j++; j++; } continue; }
      if (c === "(") depth++;
      else if (c === ")") { depth--; if (!depth) { end = j; break; } }
    }
    const body = t.slice(start, end + 1).replace(/\s+/g, " ");
    const keys = [...body.matchAll(/(?:get_\w+\(\s*args\s*,\s*"([^"]+)"|args\s*\[\s*"([^"]+)"\s*\])/g)]
      .map((m) => m[1] || m[2]);
    console.log(`===== ${fn}  (${path.basename(f)})`);
    console.log(`  参数键: ${[...new Set(keys)].join(", ") || "(无)"}`);
    console.log("  " + body.slice(0, 380));
  }
  if (!found) console.log(`===== ${fn} 未找到`);
}
