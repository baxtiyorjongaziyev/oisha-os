// Run against the installed package path in each workspace after pnpm install.
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
let packagePaths = process.argv[2] ? [process.argv[2]] : [];
if (!packagePaths.length) {
  const store = path.resolve("node_modules/.pnpm");
  // Verify the actual consumer links, not stale packages kept in pnpm's store.
  packagePaths = fs
    .readdirSync(store)
    .filter((name) => name.startsWith("micromatch@"))
    .map((name) => path.join(store, name, "node_modules/braces"))
    .filter((name) => fs.existsSync(name));
  assert.ok(packagePaths.length > 0, "Expected installed micromatch braces links");
}
function verify(packagePath) {
  const braces = require(path.resolve(packagePath));
  assert.deepEqual(braces.expand("file{1,2}.js"), ["file1.js", "file2.js"]);
  assert.deepEqual(braces.expand("a{b,{c,d}}"), ["ab", "ac", "ad"]);
  assert.deepEqual(braces.expand("file{1..3}"), ["file1", "file2", "file3"]);
  for (const [open, close] of [
    ["{", "}"],
    ["(", ")"]
  ]) {
    const nested = open.repeat(4000) + "x" + close.repeat(4000);
    for (const operation of ["parse", "compile", "expand"]) {
      assert.throws(() => braces[operation](nested), {
        name: "SyntaxError",
        message: "Brace pattern exceeds maximum nesting depth (64)"
      });
    }
  }
  assert.deepEqual(braces.expand("{" + "a,".repeat(1000) + "b}").length, 1001);
}
packagePaths.forEach(verify);
console.log("braces depth limit and normal expansion: passed");
