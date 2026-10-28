// Paper to form: the photo stays in the browser until the person presses the button that sends it.
// A phone photo is 3 to 6 MB and slow to read, so it is scaled to a 1600 px long edge first; the
// preview shows exactly what is sent.
import { fitWithin } from '/static/fit.js';
import { clear, demoNote, el } from '/static/ui.js';

const TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_SOURCE_BYTES = 25 * 1024 * 1024;
const LONG_EDGE = 1600;

function decode(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('The photo could not be read.'));
    img.src = dataUrl;
  });
}

async function scaled(dataUrl) {
  const img = await decode(dataUrl);
  const size = fitWithin(img.naturalWidth, img.naturalHeight, LONG_EDGE);
  if (!size.scaled) return dataUrl;
  const canvas = document.createElement('canvas');
  canvas.width = size.width;
  canvas.height = size.height;
  canvas.getContext('2d').drawImage(img, 0, 0, size.width, size.height);
  return canvas.toDataURL('image/jpeg', 0.85);
}

// Paint boxes (source pixels of the photo that was sent) black on a copy of the photo.
async function covered(dataUrl, regions) {
  const img = await decode(dataUrl);
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  ctx.fillStyle = '#000';
  const pad = 3;
  regions.forEach((r) => {
    const sx = img.naturalWidth / r.w, sy = img.naturalHeight / r.h;
    ctx.fillRect(r.x1 * sx - pad, r.y1 * sy - pad, (r.x2 - r.x1 + 1) * sx + 2 * pad, (r.y2 - r.y1 + 1) * sy + 2 * pad);
  });
  return canvas.toDataURL('image/jpeg', 0.85);
}

// cover(phrase, image) is optional: when given, the person can name what to hide and SAM finds it before the photo is read.
export function photoPicker(id, label, buttonText, onImage, cover = null) {
  const box = el('div');
  const problem = (text) => clear(box, el('p', { class: 'errors', role: 'alert' }, text));
  const input = el('input', { id, type: 'file', accept: TYPES.join(','), onchange: () => {
    const file = input.files[0];
    if (!file) { clear(box); return; }
    if (!TYPES.includes(file.type)) { problem('Choose a png, jpeg or webp photo.'); return; }
    if (file.size > MAX_SOURCE_BYTES) { problem('The photo is larger than 25 MB.'); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      let image;
      try { image = await scaled(reader.result); } catch (e) { problem(e.message); return; }
      let current = image;
      const preview = el('img', { src: image, alt: 'The photo you chose', class: 'photo' });
      const send = el('button', { class: 'primary', onclick: async () => {
        send.disabled = true;
        try { await onImage(current); } finally { send.disabled = false; }
      } }, buttonText);
      const coverNote = el('p', { role: 'status', class: 'muted' });
      const phrase = el('input', { type: 'text', maxlength: '40', value: 'signature', 'aria-label': 'What to cover in the photo' });
      const find = el('button', { onclick: async () => {
        clear(coverNote, 'Looking for it...');
        const res = await cover(phrase.value, image);
        if (!res.ok) { clear(coverNote, el('span', { class: 'errors', role: 'alert' }, res.data.message)); return; }
        if (res.data.demo_mode) { clear(coverNote, demoNote(res.data.demo_reason)); return; }
        current = res.data.regions.length ? await covered(image, res.data.regions) : image;
        preview.src = current;
        clear(coverNote, res.data.regions.length
          ? `Covered ${res.data.regions.length} region(s) in black. Look at the photo: anything not covered is still sent.`
          : 'Nothing like that was found. It can miss things, so cover anything private yourself before sending.');
      } }, 'Find and cover');
      clear(box, preview,
        el('p', { class: 'muted' }, "This photo is sent to Meta's model once and not stored. " +
          'Personal data in it is not masked, so cover names and phone numbers first.'),
        cover ? el('div', { class: 'row' }, el('label', {}, 'Cover in the photo: '), phrase, find) : null,
        cover ? coverNote : null,
        el('div', { class: 'row' }, send));
    };
    reader.readAsDataURL(file);
  } });
  return el('div', {}, el('label', { for: id }, label), input, box);
}
