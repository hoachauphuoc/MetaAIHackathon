// A spoken job note: record in the browser, turn it into a 16 kHz mono 16-bit WAV (what the speech model accepts)
// and hand the bytes to the caller. The recording lives only in memory; nothing is saved or uploaded but the one request.
export const RATE = 16000;
export const MAX_SECONDS = 60;

function ascii(view, offset, text) {
  for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
}

// samples: Float32Array in [-1, 1] already at `rate`.
export function encodeWav(samples, rate = RATE) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  ascii(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  ascii(view, 8, 'WAVEfmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => {
    const clipped = Math.max(-1, Math.min(1, s));
    view.setInt16(44 + i * 2, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
  });
  return new Uint8Array(view.buffer);
}

export function toDataUrl(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return `data:audio/wav;base64,${btoa(binary)}`;
}

// Decode whatever the browser recorded and resample it to 16 kHz mono.
export async function recordingToWav(blob) {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer());
    const length = Math.ceil(decoded.duration * RATE);
    const offline = new OfflineAudioContext(1, length, RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return encodeWav(rendered.getChannelData(0), RATE);
  } finally {
    context.close();
  }
}
