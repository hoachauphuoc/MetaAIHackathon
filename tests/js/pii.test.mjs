import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { maskPii } from '../../static/pii.js';

const cases = JSON.parse(readFileSync(new URL('./pii_cases.json', import.meta.url)));
// Names cannot be found by patterns. They are listed so the limit is measured, not hidden.
const KNOWN_MISSES = cases.pii.filter(([type]) => type === 'name').map(([, text]) => text);
const detectable = cases.pii.filter(([type]) => type !== 'name');

test('every detectable personal item is masked with the right type', () => {
  for (const [type, text] of detectable) {
    const { items } = maskPii(text);
    assert.ok(items.some((i) => i.type === type), `${type} not found in: ${text}`);
  }
});

test('masked text no longer contains the original value', () => {
  for (const [, text] of detectable) {
    const { text: masked, items } = maskPii(text);
    for (const item of items) assert.ok(!masked.includes(item.original), text);
  }
});

test('ordinary business numbers are left alone', () => {
  for (const text of cases.clean) {
    const result = maskPii(text);
    assert.deepEqual(result.items, [], text);
    assert.equal(result.text, text);
  }
});

test('names are a documented limit: none are detected', () => {
  for (const text of KNOWN_MISSES) assert.deepEqual(maskPii(text).items, [], text);
});

test('two emails get two placeholders', () => {
  const { text } = maskPii('billing@x.io, finance@x.io both');
  assert.equal(text, '[EMAIL_1], [EMAIL_2] both');
});

test('coverage summary', () => {
  const found = detectable.filter(([type, text]) => maskPii(text).items.some((i) => i.type === type)).length;
  const falseAlarms = cases.clean.filter((t) => maskPii(t).items.length).length;
  console.log(`# pii coverage: ${found}/${detectable.length} detectable, ${KNOWN_MISSES.length} names missed by design, ${falseAlarms}/${cases.clean.length} false alarms`);
});
