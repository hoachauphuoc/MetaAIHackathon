import assert from 'node:assert/strict';
import { test } from 'node:test';
import { maskPii } from '../../static/pii.js';

test('listed client names are masked as whole words, in any case, and nothing else changes', () => {
  const got = maskPii('Harbor Foods asked, then HARBOR FOODS paid. Harborview is another site.', ['Harbor Foods']);
  assert.equal(got.text, '[CLIENT_1] asked, then [CLIENT_2] paid. Harborview is another site.');
  assert.equal(got.items.length, 2);
});

test('the names themselves never appear in the masked text', () => {
  const names = ['Acme Foods', 'Lan (Dental)'];
  const got = maskPii('Acme Foods and Lan (Dental) and a note about Acme Foods.', names);
  for (const n of names) assert.equal(got.text.includes(n), false);
});

test('with no names listed, only the pattern rules run', () => {
  assert.equal(maskPii('Acme Foods pays.', []).text, 'Acme Foods pays.');
});
