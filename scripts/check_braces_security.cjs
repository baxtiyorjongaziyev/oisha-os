// Run against the installed package path in each workspace after pnpm install.
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
let packagePath = process.argv[2];
if (!packagePath) {
  const store = path.resolve('node_modules/.pnpm');
  const patched = fs.readdirSync(store).filter(name =>
    name.startsWith('braces@3.0.3') && name.includes('patch_hash='));
  assert.equal(patched.length, 1, 'Expected exactly one patched braces package');
  packagePath = path.join(store, patched[0], 'node_modules/braces');
}
const braces = require(path.resolve(packagePath));
assert.deepEqual(braces.expand('file{1,2}.js'), ['file1.js', 'file2.js']);
assert.deepEqual(braces.expand('a{b,{c,d}}'), ['ab', 'ac', 'ad']);
assert.deepEqual(braces.expand('file{1..3}'), ['file1', 'file2', 'file3']);
for (const [open, close] of [['{', '}'], ['(', ')']]) {
  const nested = open.repeat(4000) + 'x' + close.repeat(4000);
  for (const operation of ['parse', 'compile', 'expand']) {
    assert.throws(() => braces[operation](nested), {
      name: 'SyntaxError',
      message: 'Brace pattern exceeds maximum nesting depth (64)',
    });
  }
}
assert.deepEqual(braces.expand('{' + 'a,'.repeat(1000) + 'b}').length, 1001);
console.log('braces depth limit and normal expansion: passed');
