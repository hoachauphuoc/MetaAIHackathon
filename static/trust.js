// Rendered from /api/trust, which is built from the running configuration.
import { api, badge, clear, el } from '/static/ui.js';

(async () => {
  const t = (await api('/api/trust')).data;
  const list = (items) => el('ul', { class: 'plain' }, items.map((i) => el('li', {}, i)));
  clear(document.getElementById('app'),
    el('section', {}, el('h2', {}, 'What the server stores'),
      el('p', { class: 'muted' }, `Everything is deleted after ${t.retention}.`),
      el('ul', { class: 'plain' }, t.stored.map((s) => el('li', {}, el('strong', {}, `${s.table}: `), s.what)))),
    el('section', {}, el('h2', {}, 'What is never stored'), list(t.never_stored)),
    el('section', {}, el('h2', {}, 'Models'),
      el('ul', { class: 'plain' }, t.models.map((m) => el('li', {}, el('code', {}, m.id), `: ${m.use}`))),
      el('p', {}, t.private.available ? badge('Private mode on', 'ok') : badge('Private mode unavailable', 'warn'),
        ' ', t.private.label), el('p', { class: 'muted' }, t.private_note),
      el('p', {}, t.private.attribution)),
    t.meta_statements.length ? el('section', {}, el('h2', {}, "Meta's own statement"),
      el('p', { class: 'muted' }, 'We use Standard mode only. Check Meta\'s wording yourself:'),
      el('ul', { class: 'plain' }, t.meta_statements.map((s) => el('li', {},
        el('a', { href: s.url, target: '_blank', rel: 'noopener' }, s.label))))) : null,
    el('section', {}, el('h2', {}, 'What an assistant may do'),
      el('p', {}, 'Allowed skills: ', t.skills.allowed.join(', ')),
      el('p', {}, 'Never available to any assistant: ', t.skills.forbidden.join(', '))),
    el('section', {}, el('h2', {}, 'Honest limits'), list(t.limits)));
})();
