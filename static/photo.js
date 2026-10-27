// Paper to form: the photo stays in the browser until the person presses the button that sends it.
import { clear, el } from '/static/ui.js';

const TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_BYTES = 4 * 1024 * 1024;

export function photoPicker(id, label, buttonText, onImage) {
  const box = el('div');
  const input = el('input', { id, type: 'file', accept: TYPES.join(','), onchange: () => {
    const file = input.files[0];
    if (!file) { clear(box); return; }
    if (!TYPES.includes(file.type)) { clear(box, el('p', { class: 'errors', role: 'alert' }, 'Choose a png, jpeg or webp photo.')); return; }
    if (file.size > MAX_BYTES) { clear(box, el('p', { class: 'errors', role: 'alert' }, 'The photo is larger than 4 MB.')); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const send = el('button', { class: 'primary', onclick: async () => {
        send.disabled = true;
        try { await onImage(reader.result); } finally { send.disabled = false; }
      } }, buttonText);
      clear(box, el('img', { src: reader.result, alt: 'The photo you chose', class: 'photo' }),
        el('p', { class: 'muted' }, "This photo is sent to Meta's model once and not stored. " +
          'Personal data in it is not masked, so cover names and phone numbers first.'),
        el('div', { class: 'row' }, send));
    };
    reader.readAsDataURL(file);
  } });
  return el('div', {}, el('label', { for: id }, label), input, box);
}
