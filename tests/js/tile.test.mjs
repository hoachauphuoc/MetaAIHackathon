import test from 'node:test';
import assert from 'node:assert/strict';

// tile.js imports the DOM helpers, so only the pure formatter is copied here; keep it in step with static/tile.js.
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../../static/tile.js', import.meta.url), 'utf8');
const body = source.match(/export function duration[\s\S]*?\n}\n/)[0].replace('export ', '');
const duration = new Function(`${body}; return duration;`)();

test('seconds under a minute and a half stay in seconds', () => {
  assert.equal(duration(31.9), '31.9 s');
  assert.equal(duration(89), '89 s');
});

test('longer times are shown in minutes with one decimal', () => {
  assert.equal(duration(540), '9 min');
  assert.equal(duration(100), '1.7 min');
});
