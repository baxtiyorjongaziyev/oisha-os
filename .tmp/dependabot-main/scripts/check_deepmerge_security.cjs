const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

function verify(merge) {
  const payload = () => JSON.parse('{"__proto__":{"injected":true}}');
  for (const target of [Object.create(null), payload(), {}]) {
    for (const result of [merge(target, payload()), merge(payload(), target)]) {
      assert.equal(Object.getPrototypeOf(result), Object.prototype);
      assert.equal(result.injected, undefined);
      assert.equal(Object.hasOwn(result, '__proto__'), false);
    }
  }
  for (const value of [null, undefined, 0, false, '']) {
    const result = merge({ session: value }, { session: payload() });
    assert.equal(Object.getPrototypeOf(result.session), Object.prototype);
    assert.equal(result.session.injected, undefined);
  }
  const symbol = Symbol('supported');
  const result = merge({ config: { a: 1 }, list: [1] }, {
    config: { b: 2 }, list: [2], [symbol]: { enabled: true }
  });
  assert.deepEqual(result.config, { a: 1, b: 2 });
  assert.deepEqual(result.list, [1, 2]);
  assert.deepEqual(result[symbol], { enabled: true });
  assert.deepEqual(merge.all([{ a: 1 }, { b: 2 }]), { a: 1, b: 2 });
  assert.deepEqual(merge([1], [2], { arrayMerge: (_, source) => source }), [2]);
  assert.equal(({}).injected, undefined);
}

const store = path.resolve('node_modules/.pnpm');
const consumers = process.argv[2] ? [path.resolve(process.argv[2])] : fs
  .readdirSync(store)
  .filter(name => !name.startsWith('deepmerge@'))
  .map(name => path.join(store, name, 'node_modules/deepmerge'))
  .filter(name => fs.existsSync(name));
assert.ok(consumers.length > 0, 'Expected installed consumer links to deepmerge');
for (const packagePath of new Set(consumers.map(name => fs.realpathSync(name)))) {
  for (const entry of ['dist/cjs.js', 'dist/umd.js']) {
    verify(require(path.join(packagePath, entry)));
  }
}
console.log(`deepmerge prototype protection and compatible merges: passed (${consumers.length} consumer links)`);
