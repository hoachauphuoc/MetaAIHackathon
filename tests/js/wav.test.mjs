import test from 'node:test';
import assert from 'node:assert/strict';
import { encodeWav, toDataUrl } from '../../static/wav.js';

test('a WAV header says mono 16-bit PCM at the given rate and holds every sample', () => {
  const wav = encodeWav(new Float32Array([0, 0.5, -0.5, 1, -1]), 16000);
  const view = new DataView(wav.buffer);
  const text = (o, n) => String.fromCharCode(...wav.subarray(o, o + n));
  assert.equal(text(0, 4), 'RIFF');
  assert.equal(text(8, 8), 'WAVEfmt ');
  assert.equal(view.getUint16(20, true), 1);
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getUint16(34, true), 16);
  assert.equal(view.getUint32(40, true), 10);
  assert.equal(wav.length, 44 + 10);
  assert.equal(view.getInt16(44 + 6, true), 0x7fff);
  assert.equal(view.getInt16(44 + 8, true), -0x8000);
});

test('samples beyond full scale are clipped, not wrapped', () => {
  const view = new DataView(encodeWav(new Float32Array([3, -3])).buffer);
  assert.equal(view.getInt16(44, true), 0x7fff);
  assert.equal(view.getInt16(46, true), -0x8000);
});

test('a long recording turns into a data URL without overflowing the call stack', () => {
  const url = toDataUrl(encodeWav(new Float32Array(16000 * 60)));
  assert.ok(url.startsWith('data:audio/wav;base64,'));
});
