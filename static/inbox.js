// Inbox and Today: documents waiting between roles. Everything shown is about packages, never people.
import { confirmMask } from '/static/mask.js';
import { photoPicker } from '/static/photo.js';
import { api, badge, clear, demoNote, el, statusBadge } from '/static/ui.js';

const today = () => new Date().toISOString().slice(0, 10);
const inDays = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);

function stateLabel(p) {
  if (p.state === 'sent') return `Waiting for ${p.to_title}`;
  if (p.state === 'accepted') return 'Accepted';
  return 'Returned to the sender';
}

export function findingsBlock(findings) {
  const group = (source, title) => {
    const rows = findings.filter((f) => f.source === source);
    return rows.length ? [el('p', { class: 'muted' }, title),
      el('ul', { class: 'plain' }, rows.map((f) => el('li', {}, f.message)))] : [];
  };
  return [...group('rules', 'Checked by the rules'), ...group('model', "Assistant's notes")];
}

// One set of fields for sending and for fixing a returned package, drawn from the company's form.
const DEMO_DEFAULTS = { customer: 'Acme Foods', pallets: 10, price: 1800, cost: 1500 };

export function inputFor(prefix, field, value) {
  const id = `${prefix}-${field.key}`;
  if (field.type === 'longtext') return el('textarea', { id, maxlength: '2000' }, value ?? '');
  if (field.type === 'choice') {
    return el('select', { id }, field.options.map((o) => el('option', { value: o, selected: o === value }, o)));
  }
  const kind = { text: 'text', date: 'date', integer: 'number', number: 'number', money: 'number' }[field.type];
  const extra = field.type === 'integer' ? { step: '1', min: '0' } : kind === 'number' ? { step: 'any', min: '0' } : {};
  return el('input', { id, type: kind, value: value ?? '', ...extra });
}

function valueFields(prefix, schema, v = {}, due = '', demo = false) {
  const first = (key, fallback) => (v[key] ?? (demo ? fallback : ''));
  const inputs = Object.fromEntries(schema.fields.map((field) => [field.key, inputFor(prefix, field,
    field.type === 'date' ? first(field.key, inDays(14)) : first(field.key, DEMO_DEFAULTS[field.key]))]));
  // Once the person types in a flagged field it is theirs; the warning goes away.
  for (const input of Object.values(inputs)) input.addEventListener('input', () => input.removeAttribute('aria-invalid'));
  const dueInput = el('input', { id: `${prefix}-due`, type: 'date', min: today(), value: due || '' });
  const notes = el('textarea', { id: `${prefix}-notes` }, v.notes ?? '');
  const labelled = (label, node) => [el('label', { for: node.id }, label), node];
  const rows = [
    ...schema.fields.flatMap((field) => labelled(field.required ? field.label : `${field.label} (optional)`, inputs[field.key])),
    ...labelled('Answer needed by (optional)', dueInput), ...labelled('Notes (untrusted text)', notes)];
  const read = async (maskBox) => {
    const values = Object.fromEntries(schema.fields.map((field) => [field.key, inputs[field.key].value]));
    const masked = await confirmMask(notes.value, maskBox);
    return masked === null ? null : { values: { ...values, notes: masked }, due: dueInput.value || null };
  };
  const fill = (values, unreadable = []) => {
    for (const field of schema.fields) {
      inputs[field.key].value = values[field.key] ?? '';
      if (unreadable.includes(field.key)) inputs[field.key].setAttribute('aria-invalid', 'true');
      else inputs[field.key].removeAttribute('aria-invalid');
    }
  };
  return { rows, read, fill };
}

// "Label: value" for every short field except the one used as the title; long text gets its own block.
function detailLine(schema, v) {
  return schema.fields.filter((f) => f.key !== schema.title_field && f.type !== 'longtext')
    .map((f) => `${f.label}: ${v[f.key] ?? '-'}`).join(' · ');
}
function longBlocks(schema, v) {
  return schema.fields.filter((f) => f.type === 'longtext' && v[f.key])
    .map((f) => el('div', {}, el('strong', {}, f.label), el('p', { class: 'long' }, v[f.key])));
}

export function inboxPanel(info, token) {
  const list = el('div');
  const todayBox = el('div', { class: 'row' });
  const msg = el('p', { role: 'status', class: 'muted' });
  const titles = info.role_titles || {};

  async function call(path, body) {
    const res = await api(path, { method: 'POST', body: { token, ...body } });
    clear(msg, res.ok ? null : res.data.message);
    await refresh();
  }

  function card(p) {
    const v = p.values;
    const reason = el('input', { 'aria-label': 'Reason for returning', placeholder: 'Reason (needed to return)' });
    const actions = [];
    if (p.can_claim) actions.push(el('button', { onclick: () => call(`/api/handoffs/${p.id}/claim`, {}) }, 'Take it'));
    if (p.i_hold_it && p.state === 'sent') {
      actions.push(el('button', { onclick: () => call(`/api/handoffs/${p.id}/unclaim`, {}) }, 'Put back in the queue'));
    }
    if (p.can_decide) {
      actions.push(
        el('button', { class: 'primary', disabled: p.check_status === 'blocked',
          onclick: () => call(`/api/handoffs/${p.id}/decision`, { decision: 'accept' }) }, 'Accept'),
        reason,
        el('button', { onclick: () => call(`/api/handoffs/${p.id}/decision`, { decision: 'return', reason: reason.value }) }, 'Return'));
    }
    const why = p.can_decide && p.check_status === 'blocked'
      ? (p.findings.find((f) => f.status === 'blocked')?.message || 'The check found a problem.') : null;

    let fix = null;
    if (p.can_resend) {
      const fields = valueFields(`fix-${p.id}`, p.schema, v, p.due);
      const maskBox = el('div');
      const suggestion = el('div', { role: 'status' });
      const suggest = el('button', { onclick: async () => {
        suggest.disabled = true;
        clear(suggestion, el('p', { class: 'progress' }, 'The assistant is reading the reason...'));
        const res = await api(`/api/handoffs/${p.id}/suggest`, { method: 'POST', body: { token } });
        suggest.disabled = false;
        if (!res.ok) { clear(suggestion, el('p', { class: 'errors' }, res.data.message)); return; }
        const s = res.data;
        if (s.demo_mode) {
          clear(suggestion, demoNote(s.demo_reason));
          return;
        }
        fields.fill(s.values);
        clear(suggestion, el('p', {}, el('strong', {}, 'Suggested by the assistant. You decide. '), s.explanation),
          s.rate_card ? el('p', { class: 'muted' },
            `Rate card for ${s.rate_card.pallets} pallets: price USD ${s.rate_card.price}, cost USD ${s.rate_card.cost}.`) : null,
          el('p', {}, 'The rules would say: ', statusBadge(s.predicted_status)));
      } }, 'Suggest a fix');
      // A handover is the sender's own words; there is no rule-based fix to suggest.
      const canSuggest = p.schema.id !== 'handover';
      fix = el('details', { open: true }, el('summary', {}, 'Fix and resend'),
        canSuggest ? el('div', { class: 'row' }, suggest) : null, suggestion, ...fields.rows, maskBox,
        el('div', { class: 'row' }, el('button', { class: 'primary', onclick: async () => {
          const got = await fields.read(maskBox);
          if (got) await call(`/api/handoffs/${p.id}/resend`, got);
        } }, 'Check again and resend')));
    }

    return el('div', { class: 'card' },
      el('p', {}, el('strong', {}, v[p.schema.title_field] || p.schema.title), ` ${detailLine(p.schema, v)}`),
      ...longBlocks(p.schema, v),
      el('p', {}, statusBadge(p.check_status), ' ', badge(stateLabel(p), 'info'), ' ',
        p.overdue ? badge('Overdue', 'bad') : null),
      el('p', { class: 'muted' },
        `From ${p.from_title}. ${p.due ? `Answer needed by ${p.due}` : 'No deadline'}. ` +
        `Approval path: ${p.chain_titles.join(', then ')}.`),
      p.summary ? el('p', {}, el('strong', {}, 'In short: '), p.summary) : null,
      p.held_by_teammate ? el('p', { class: 'muted' }, 'A teammate in your team is handling this.') : null,
      p.return_reason ? el('p', { class: 'errors' }, `Returned: ${p.return_reason}`) : null,
      p.history.map((h) => el('p', { class: 'muted' },
        `Returned before: ${h.reason}. ` + (h.changes.length ? `Then changed ${h.changes.join('; ')}.` : 'Sent again unchanged.'))),
      ...findingsBlock(p.findings),
      why ? el('p', { class: 'errors', role: 'status' }, `You cannot accept this: ${why} Return it with a reason.`) : null,
      el('div', { class: 'row' }, actions), fix);
  }

  async function refresh() {
    const res = await api(`/api/inbox?token=${encodeURIComponent(token)}`);
    const t = res.data.today;
    clear(todayBox,
      badge(`${t.waiting_for_me} waiting for you`, 'info'),
      badge(`${t.returned_to_me} returned to you`, t.returned_to_me ? 'warn' : 'info'),
      badge(`${t.in_team_queue} in your team queue`, 'info'),
      badge(`${t.handled_by_teammates} being handled by teammates`, 'info'),
      badge(`${t.overdue_for_my_role} overdue`, t.overdue_for_my_role ? 'bad' : 'info'));
    clear(list, res.data.packages.length ? res.data.packages.map(card) : el('p', { class: 'muted' }, 'Nothing here yet.'));
  }

  const toRole = el('select', { id: 'to-role' }, (info.assistant?.handoffs || []).map((h) =>
    el('option', { value: h.to_role }, `${titles[h.to_role] || h.to_role}: ${h.what}`)));
  const schema = info.handoff_schema;
  const fields = valueFields('send', schema, {}, '', schema.id === 'logistics');
  const maskBox = el('div');
  const result = el('div');
  const photoResult = el('div', { role: 'status' });

  const photo = photoPicker('send-photo', 'Fill from a photo of the paper (optional)', 'Read the photo', async (image) => {
    clear(photoResult, el('p', { class: 'progress' }, 'The assistant is reading the photo...'));
    const res = await api('/api/handoffs/from-photo', { method: 'POST', body: { token, image } });
    if (!res.ok) { clear(photoResult, el('p', { class: 'errors', role: 'alert' }, res.data.message)); return; }
    if (res.data.demo_mode) { clear(photoResult, demoNote(res.data.demo_reason)); return; }
    fields.fill(res.data.values, res.data.unreadable);
    const unclear = schema.fields.filter((f) => res.data.unreadable.includes(f.key)).map((f) => f.label);
    clear(photoResult, el('p', {}, el('strong', {}, 'Read by the assistant. Check every field. '),
      'The rules would say: ', statusBadge(res.data.predicted_status)),
      unclear.length ? el('p', { class: 'errors', role: 'status' },
        `A person must check this: ${unclear.join(', ')}. The photo was not clear there, so the field is empty.`) : null,
      ...findingsBlock(res.data.findings));
  });

  const check = el('button', { onclick: async () => {
    const got = await fields.read(maskBox);
    if (!got) return;
    const res = await api('/api/precheck', { method: 'POST', body: { token, ...got } });
    clear(result, el('p', {}, statusBadge(res.data.status), ' Nothing was sent or stored.'),
      ...findingsBlock(res.data.findings));
  } }, 'Check first');

  const sendBtn = el('button', { class: 'primary', onclick: async () => {
    const got = await fields.read(maskBox);
    if (!got) return;
    const res = await api('/api/handoffs', { method: 'POST', body: { token, to_role: toRole.value, ...got } });
    if (!res.ok) { clear(result, el('p', { class: 'errors', role: 'alert' }, res.data.message)); return; }
    const p = res.data;
    const later = p.chain_titles.slice(1);
    clear(result, el('p', { role: 'status' }, statusBadge(p.check_status), ' ',
      `Sent to the ${p.to_title} team. It waits in their queue until someone takes it.`,
      later.length ? ` After that ${later.join(', then ')} must approve.` : '',
      p.check_status === 'blocked' ? ' They cannot accept it until you fix it and send it again.' : ''));
    refresh();
  } }, 'Send handoff');

  refresh();
  return el('section', {}, el('h2', {}, 'Inbox'), todayBox, msg, list,
    el('h3', {}, 'Send a handoff'),
    el('p', { class: 'muted' }, 'It goes to the whole receiving team. Someone there takes it and decides. Nobody can decide on their own package.'),
    el('label', { for: 'to-role' }, 'To'), toRole, photo, photoResult, ...fields.rows, maskBox,
    el('div', { class: 'row' }, check, sendBtn), result);
}
