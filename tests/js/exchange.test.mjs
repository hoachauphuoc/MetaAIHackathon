import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readRecord, toCsv } from '../../static/exchange.js';

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
