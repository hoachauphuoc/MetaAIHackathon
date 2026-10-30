import assert from 'node:assert/strict';
import { test } from 'node:test';
import { approvedMailDraft, readRecord, toCsv, toApprovedCsv, toApprovedJson } from '../../static/exchange.js';

const schema = { fields: [{ key: 'customer' }, { key: 'pallets' }, { key: 'price' }] };

test('a CSV row with a quoted comma fills only the fields the form has', () => {
  const got = readRecord('customer,pallets,evil\r\n"Acme, Inc",12,x', schema);
  assert.deepEqual(got, { customer: 'Acme, Inc', pallets: '12' });
});

test('a JSON file may wrap its record in values and unknown keys are dropped', () => {
  assert.deepEqual(readRecord('{"values":{"customer":"Z","junk":1}}', schema), { customer: 'Z' });
});

test('notes are never imported, so free text always passes the masking step', () => {
  assert.deepEqual(readRecord('{"customer":"Z","notes":"call 0912345678"}', schema), { customer: 'Z' });
});

test('a file with no matching field is refused and names the fields expected', () => {
  assert.throws(() => readRecord('{"a":1}', schema), /Expected: customer, pallets, price/);
});

test('an oversized file is refused', () => {
  assert.throws(() => readRecord('{"customer":"' + 'x'.repeat(100001) + '"}', schema), /too large/);
});

test('an exported cell that starts like a formula gets a leading quote mark', () => {
  const csv = toCsv([{ values: { customer: '=cmd', pallets: 3, price: '1"2' }, check_status: 'clear', state: 'sent', due: null }], schema);
  assert.match(csv, /"'=cmd","3","1""2"/);
});

const done = (id, state, status, extra = {}) => ({
  id, state, check_status: status, sent_on: '2026-10-29', chain_titles: ['Operations', 'Finance'],
  values: { customer: id, pallets: 3, price: 10 }, ...extra });

test('the approved export keeps only accepted packages that were not blocked', () => {
  const csv = toApprovedCsv([done('a', 'accepted', 'clear'), done('b', 'sent', 'clear'),
    done('c', 'returned', 'clear'), done('d', 'accepted', 'blocked')], schema);
  assert.equal(csv.split('\r\n').length, 2);
  assert.match(csv, /^"handoff_id","customer","pallets","price","approved_by","sent_on"/);
  assert.match(csv, /"a","a","3","10","Operations > Finance","2026-10-29"/);
});

test('the approved export never carries free-text notes and keeps the form column order', () => {
  const p = done('a', 'accepted', 'clear');
  p.values.notes = 'call 0912345678';
  assert.ok(!toApprovedCsv([p], schema).includes('0912345678'));
  assert.deepEqual(Object.keys(JSON.parse(toApprovedJson([p], schema))[0].values), ['customer', 'pallets', 'price']);
});

test('an approved export cell that starts like a formula gets a leading quote mark', () => {
  assert.match(toApprovedCsv([done('=x', 'accepted', 'clear', { values: { customer: '=cmd' } })], schema), /"'=cmd"/);
});

const form = { title: 'Quote', title_field: 'customer', fields: [{ key: 'customer', label: 'Customer' }, { key: 'pallets', label: 'Pallets' }] };

test('only an accepted, unblocked handoff gets an email draft, built from the form fields and the approval chain', () => {
  assert.equal(approvedMailDraft(done('a', 'sent', 'clear'), form), null);
  assert.equal(approvedMailDraft(done('b', 'accepted', 'blocked'), form), null);
  const draft = approvedMailDraft(done('Acme', 'accepted', 'clear', { values: { customer: 'Acme', pallets: 3, notes: 'call 0912345678' } }), form);
  assert.match(decodeURIComponent(draft.href), /^mailto:\?subject=Approved: Acme&body=Approved: Acme/);
  assert.ok(draft.text.includes('Pallets: 3') && draft.text.includes('Approved by: Operations, then Finance'));
  assert.equal(draft.text.includes('0912345678'), false);
});

test('a draft too long for a mail link has the text to copy and no link', () => {
  const draft = approvedMailDraft(done('x', 'accepted', 'clear', { values: { customer: 'x'.repeat(2000), pallets: 1 } }), form);
  assert.equal(draft.href, null);
  assert.ok(draft.text.length > 1800);
});

test('an approved order draft carries only code-computed numbers and the approvals, plus the calendar file', async () => {
  const { approvedOrderDraft } = await import('../../static/exchange.js');
  const step = (title, role, tool_result) => ({ title, role, result: { tool_result, summary: 'model words 0912345678' } });
  const draft = approvedOrderDraft([step('Quote the order', 'Sales', { price: 2160, cost: 1800 }),
    step('Schedule the delivery', 'Operations', { title: 'Delivery: Acme', date: '2026-11-13', ics: 'BEGIN:VCALENDAR' }),
    step('Check the margin', 'Finance', { margin_pct: 16.7 })]);
  assert.match(decodeURIComponent(draft.href), /^mailto:\?subject=Approved order: Delivery: Acme&body=/);
  assert.ok(draft.text.includes('Price: USD 2160') && draft.text.includes('Margin: 16.7%') && draft.text.includes('Delivery: 2026-11-13'));
  assert.ok(draft.text.includes('Approved steps: Quote the order (Sales), then Schedule the delivery (Operations), then Check the margin (Finance)'));
  assert.equal(draft.text.includes('0912345678'), false);  // nothing a model wrote
  assert.equal(draft.ics, 'BEGIN:VCALENDAR');
});
