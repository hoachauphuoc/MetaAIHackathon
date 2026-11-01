import test from 'node:test';
import assert from 'node:assert/strict';

// app.js runs the owner page on import, so only the pure label function is copied here; keep it in step with static/app.js.
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../../static/app.js', import.meta.url), 'utf8');
const body = source.match(/export function chartLabel[\s\S]*?\r?\n}\r?\n/)[0].replace('export ', '');
const chartLabel = new Function(`${body}; return chartLabel;`)();

test('a chart Wonder answered is labelled Designed by Muse Wonder', () => {
  assert.deepEqual(chartLabel({ source: 'wonder', demo_mode: false }), ['Designed by Muse Wonder', 'ok']);
});

test('a chart that fell back is labelled Template, never Wonder', () => {
  assert.deepEqual(chartLabel({ source: 'template', demo_mode: true }), ['Template', 'warn']);
  assert.notEqual(chartLabel({ source: 'wonder', demo_mode: true })[0], 'Designed by Muse Wonder');
});

test('a chart reopened from the company record is not credited to Wonder', () => {
  assert.deepEqual(chartLabel({ source: 'saved', demo_mode: false }), ['Saved chart', 'info']);
});
