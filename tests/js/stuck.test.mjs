import assert from 'node:assert/strict';
import { test } from 'node:test';
import { reminderText, stuckLine, stuckRows } from '../../static/stuck.js';

const schema = { title_field: 'customer', title: 'Quote' };
const pkg = (extra = {}) => ({ id: 'a', i_sent_it: true, state: 'sent', overdue: false, age_days: 2, taken: false, stage: 0,
  chain: ['ops', 'fin'], to_title: 'Operations', from_title: 'Sales', values: { customer: 'Acme' }, schema,
  sent_on: '2026-10-26', due: null, check_status: 'clear', ...extra });

test('only what I sent and is still waiting is listed, overdue first then oldest', () => {
  const rows = stuckRows([pkg({ id: 'old', age_days: 5 }), pkg({ id: 'late', overdue: true, age_days: 1 }),
    pkg({ id: 'mine-done', state: 'accepted' }), pkg({ id: 'not-mine', i_sent_it: false })]);
  assert.deepEqual(rows.map((p) => p.id), ['late', 'old']);
});

test('the line says where, how long, and whether someone took it, without naming a person', () => {
  assert.equal(stuckLine(pkg()), 'Acme: waiting with Operations for 2 days, not taken yet.');
  assert.match(stuckLine(pkg({ stage: 1, taken: true, overdue: true })), /at Operations, step 2 of 2.*taken by someone.*overdue/);
});

test('the reminder is built from the package fields only', () => {
  const text = reminderText(pkg({ due: '2026-10-30' }));
  assert.match(text, /Hello Operations team/);
  assert.match(text, /"Acme" from Sales on 2026-10-26/);
  assert.match(text, /answer needed by 2026-10-30/);
  assert.doesNotMatch(reminderText(pkg()), /answer needed/);
});
