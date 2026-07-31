const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('templates/index.html', 'utf8');
const script = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)][0][1];
const start = script.indexOf('function bindingKey');
const end = script.indexOf('function deviceBindingToRaw');

assert(start >= 0 && end > start, 'Device binding codec source was not found');

const tests = `
const ids = new Map([
  ['zip_dyn_scale', 39],
  ['layer_overlay_secondary', 40],
  ['layer_overlay_tertiary', 41],
  ['layer_overlay_secondary_space', 42],
]);
assert.deepStrictEqual(
  bindingFromParsedRaw(parseRawBinding('&zip_dyn_scale ZDS_SC ZDS_DEC'), ids, {}),
  {behaviorId: 39, param1: 1, param2: 2}
);
assert.deepStrictEqual(
  bindingFromParsedRaw(parseRawBinding('&layer_overlay_secondary'), ids, {}),
  {behaviorId: 40, param1: 0, param2: 0}
);
assert.deepStrictEqual(
  bindingFromParsedRaw(parseRawBinding('&layer_overlay_secondary_space 0 SPACE'), ids, {}),
  {behaviorId: 42, param1: 0, param2: 458796}
);
assert.strictEqual(normalizeDeviceConstantName('SELECT_PROFILE'), 'BT_SEL');
assert.strictEqual(normalizeDeviceConstantName('TOGGLE_OUTPUTS'), 'OUT_TOG');
`;

vm.runInNewContext(
  'const SHIFTED_KEY_ALIASES = {};\n' + script.slice(start, end) + tests,
  {assert, console}
);

console.log('Device binding codec tests OK');
