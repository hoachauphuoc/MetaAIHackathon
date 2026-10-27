// Inbox and Today: documents waiting between roles. Everything shown is about packages, never people.
import { confirmMask } from '/static/mask.js';
import { api, badge, clear, el, statusBadge } from '/static/ui.js';

export const ROUTES = ['Hanoi-Haiphong', 'Hanoi-Danang', 'Haiphong-Hochiminh', 'Danang-Hochiminh'];

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

// One set of fields for sending and for fixing a returned package.
function valueFields(prefix, v = {}, due = '') {
  const f = {
    customer: el('input', { id: `${prefix}-customer`, value: v.customer ?? 'Acme Foods' }),
    route: el('select', { id: `${prefix}-route` },
      ROUTES.map((r) => el('option', { value: r, selected: r === v.route }, r))),
    pallets: el('input', { id: `${prefix}-pallets`, type: 'number', min: '1', value: v.pallets ?? 10 }),
    price: el('input', { id: `${prefix}-price`, type: 'number', value: v.price ?? 1800 }),
    cost: el('input', { id: `${prefix}-cost`, type: 'number', value: v.cost ?? 1500 }),
    delivery_date: el('input', { id: `${prefix}-date`, type: 'date', value: v.delivery_date ?? inDays(14) }),
    due: el('input', { id: `${prefix}-due`, type: 'date', min: today(), value: due || '' }),
    notes: el('textarea', { id: `${prefix}-notes` }, v.notes ?? ''),
  };
  const labelled = (label, node) => [el('label', { for: node.id }, label), node];
  const rows = [
    ...labelled('Customer', f.customer), ...labelled('Shipping route', f.route),
    ...labelled('Pallets', f.pallets), ...labelled('Price (USD)', f.price), ...labelled('Cost (USD)', f.cost),
    ...labelled('Delivery date', f.delivery_date), ...labelled('Answer needed by (optional)', f.due),
    ...labelled('Notes (untrusted text)', f.notes)];
  const read = async (maskBox) => {
    const values = {};
    for (const key of ['customer', 'route', 'pallets', 'price', 'cost', 'delivery_date', 'notes']) values[key] = f[key].value;
    const notes = await confirmMask(values.notes, maskBox);
    return notes === null ? null : { values: { ...values, notes }, due: f.due.value || null };
  };
  return { rows, read };
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
      const fields = valueFields(`fix-${p.id}`, v, p.due);
      const maskBox = el('div');
      fix = el('details', { open: true }, el('summary', {}, 'Fix and resend'), ...fields.rows, maskBox,
        el('div', { class: 'row' }, el('button', { class: 'primary', onclick: async () => {
          const got = await fields.read(maskBox);
          if (got) await call(`/api/handoffs/${p.id}/resend`, got);
        } }, 'Check again and resend')));
    }

    return el('div', { class: 'card' },
      el('p', {}, el('strong', {}, `${v.customer}: ${v.pallets} pallets, shipping route ${v.route}`)),
      el('p', {}, statusBadge(p.check_status), ' ', badge(stateLabel(p), 'info'), ' ',
        p.overdue ? badge('Overdue', 'bad') : null),
      el('p', { class: 'muted' },
        `From ${p.from_title}. Price USD ${v.price}, cost USD ${v.cost}, ${p.due ? `answer needed by ${p.due}` : 'no deadline'}. ` +
        `Approval path: ${p.chain_titles.join(', then ')}.`),
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
  const fields = valueFields('send');
  const maskBox = el('div');
  const result = el('div');

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
    el('label', { for: 'to-role' }, 'To'), toRole, ...fields.rows, maskBox,
    el('div', { class: 'row' }, check, sendBtn), result);
}
