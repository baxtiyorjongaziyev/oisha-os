// Runs model-written script inside `node --permission` (no net/child/worker/fs-write).
// Only channel out: JSON lines on stdout; replies arrive on stdin.
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import vm from "node:vm";

const [scriptPath, namespaces = "telegram", allowedDir] = process.argv.slice(2);
if (!/^[a-z][a-z0-9_]*(,[a-z][a-z0-9_]*)*$/.test(namespaces)) throw new Error("bad namespaces");
// Script must be a regular, non-symlink file directly inside the managed directory.
const st = fs.lstatSync(scriptPath);
const real = fs.realpathSync(scriptPath);
const base = fs.realpathSync(allowedDir);
if (!st.isFile() || st.isSymbolicLink() || path.dirname(real) !== base) {
  throw new Error("script path outside managed directory");
}
const code = fs.readFileSync(real, "utf8");
const rl = readline.createInterface({ input: process.stdin });
const pending = new Map();
let nextId = 1;

rl.on("line", (line) => {
  const msg = JSON.parse(line);
  const p = pending.get(msg.id);
  if (!p) return;
  pending.delete(msg.id);
  msg.error ? p.reject(new Error(msg.error)) : p.resolve(msg.result);
});

const makeApi = (ns) => new Proxy({}, {
  get: (_, name) => (args = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      process.stdout.write(JSON.stringify({ id, name: `${ns}.${String(name)}`, args }) + "\n");
    }),
});

// Layer 2: fresh vm context -> no fetch, require, process, dynamic import().
// NOT a hard boundary (vm escapes exist); real isolation = container/Worker w/o network.
const ctx = vm.createContext({
  ...Object.fromEntries(namespaces.split(",").map((ns) => [ns, makeApi(ns)])),
  console: { log() {} },
});
try {
  const result = await vm.runInContext(`(async () => {
${code}
})()`, ctx, { timeout: 5000 });
  process.stdout.write(JSON.stringify({ done: true, result: result ?? null }) + "\n");
} catch (e) {
  process.stdout.write(JSON.stringify({ done: true, error: String(e?.message ?? e) }) + "\n");
}
process.exit(0);
