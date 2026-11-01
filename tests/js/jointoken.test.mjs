import assert from 'node:assert/strict';
import test from 'node:test';
import { readJoinToken } from '../../static/jointoken.js';

test('reads the token from the fragment', () => {
  const calls = [];
  const history = { replaceState: (...a) => calls.push(a) };
  assert.equal(readJoinToken({ hash: '#abc123', pathname: '/join' }, history), 'abc123');
  assert.equal(calls.length, 0);
});

test('rewrites the old path form into the fragment form', () => {
  const calls = [];
  const history = { replaceState: (...a) => calls.push(a) };
  assert.equal(readJoinToken({ hash: '', pathname: '/join/abc123' }, history), 'abc123');
  assert.deepEqual(calls, [[null, '', '/join#abc123']]);
});

test('a bare /join without a token gives an empty token and rewrites nothing', () => {
  const calls = [];
  assert.equal(readJoinToken({ hash: '', pathname: '/join' }, { replaceState: (...a) => calls.push(a) }), '');
  assert.equal(calls.length, 0);
});
