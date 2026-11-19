const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');

test('2FA completion shows connected while first dialog refresh is pending', async () => {
  const elements = new Map();
  const element = () => ({
    textContent: '', value: '', dataset: {}, append() {},
    classList: {
      hidden: true,
      toggle(name, enabled) { if (name === 'hidden') this.hidden = enabled; },
      add() {}, remove() {},
    },
  });
  const calls = [];
  let connected = false;
  const pendingRefresh = new Promise(() => {});
  const context = {
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, element());
        return elements.get(id);
      },
      createElement: element,
    },
    fetch: async (url) => {
      calls.push(url);
      if (url.endsWith('/chats/refresh')) return pendingRefresh;
      if (url.endsWith('/qr/password')) {
        connected = true;
        return {status: 200, ok: true, json: async () => ({state: 'done'})};
      }
      const data = url.endsWith('/status')
        ? {connected, connected_at: 1, allowed_chats: 0, attempt: {state: 'password_required'}}
        : url.endsWith('/chats') ? {chats: []} : {events: []};
      return {status: 200, ok: true, json: async () => data};
    },
    setInterval() {}, clearInterval() {},
  };
  vm.runInNewContext(fs.readFileSync('src/static/connect/connect.js', 'utf8'), context);
  await new Promise(setImmediate);
  assert.equal(elements.get('pw-step').classList.hidden, false);
  context.document.getElementById('pw').value = 'synthetic-test-password';
  await elements.get('btn-pw').onclick();
  await new Promise(setImmediate);
  assert.equal(elements.get('pw').value, '');
  assert.equal(elements.get('pw-step').classList.hidden, true);
  assert.equal(elements.get('connected').classList.hidden, false);
  assert.ok(calls.includes('/api/connect/chats/refresh'));
  assert.ok(calls.includes('/api/connect/audit'));
});
