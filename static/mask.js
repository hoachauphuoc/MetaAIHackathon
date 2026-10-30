import { maskPii } from '/static/pii.js';
import { clear, el } from '/static/ui.js';

// The client names this person listed in this browser. Stored only here, never sent with a request.
export function clientNames() {
  try { return JSON.parse(localStorage.getItem('clientNames') || '[]'); } catch { return []; }
}

// Resolves to the text to send (masked), or null if the person cancels. Shows what was masked.
export function confirmMask(text, mount) {
  const { text: masked, items } = maskPii(text, clientNames());
  if (!items.length) return Promise.resolve(text);
  return new Promise((resolve) => {
    const done = (value) => { clear(mount); resolve(value); };
    clear(mount, el('div', { class: 'errors', role: 'alert' },
      `${items.length} personal item${items.length > 1 ? 's' : ''} found. Placeholders will be sent instead:`,
      el('ul', {}, items.map((i) => el('li', {}, `${i.original} becomes ${i.placeholder}`))),
      el('p', { class: 'muted' }, 'Names cannot be detected. Remove them yourself if needed.'),
      el('div', { class: 'row' },
        el('button', { class: 'primary', onclick: () => done(masked) }, 'Send masked'),
        el('button', { onclick: () => done(null) }, 'Cancel'))));
  });
}
