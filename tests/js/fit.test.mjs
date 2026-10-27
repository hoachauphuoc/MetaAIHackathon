import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fitWithin } from '../../static/fit.js';

test('a 12 MP landscape photo is scaled to the long edge and keeps its shape', () => {
  assert.deepEqual(fitWithin(4000, 3000, 1600), { width: 1600, height: 1200, scaled: true });
});

test('a portrait photo is limited by its height', () => {
  assert.deepEqual(fitWithin(3000, 4000, 1600), { width: 1200, height: 1600, scaled: true });
});

test('a small image is left as it is and never enlarged', () => {
  assert.deepEqual(fitWithin(800, 600, 1600), { width: 800, height: 600, scaled: false });
});

test('a very thin image keeps at least one pixel', () => {
  assert.equal(fitWithin(20000, 3, 1600).height, 1);
});
