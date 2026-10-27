// Paper to form: the photo stays in the browser until the person presses the button that sends it.
// A phone photo is 3 to 6 MB and slow to read, so it is scaled to a 1600 px long edge first; the
// preview shows exactly what is sent.
import { fitWithin } from '/static/fit.js';
import { clear, el } from '/static/ui.js';

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

export function photoPicker(id, label, buttonText, onImage) {
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
      const send = el('button', { class: 'primary', onclick: async () => {
        send.disabled = true;
        try { await onImage(image); } finally { send.disabled = false; }
      } }, buttonText);
      clear(box, el('img', { src: image, alt: 'The photo you chose', class: 'photo' }),
        el('p', { class: 'muted' }, "This photo is sent to Meta's model once and not stored. " +
          'Personal data in it is not masked, so cover names and phone numbers first.'),
        el('div', { class: 'row' }, send));
    };
    reader.readAsDataURL(file);
  } });
  return el('div', {}, el('label', { for: id }, label), input, box);
}
