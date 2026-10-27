// Inbox and Today: documents waiting between roles. Everything shown is about packages, never people.
import { confirmMask } from '/static/mask.js';
import { api, badge, clear, el, statusBadge } from '/static/ui.js';

export const ROUTES = ['Hanoi-Haiphong', 'Hanoi-Danang', 'Haiphong-Hochiminh', 'Danang-Hochiminh'];

export function inboxPanel(info, token) {
  const list = el('div');
  const todayBox = el('div', { class: 'row' });
  const msg = el('p', { role: 'status', class: 'muted' });

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
    if (p.can_resend) {
      actions.push(el('button', { class: 'primary', onclick: () => call(`/api/handoffs/${p.id}/resend`, { values: v }) },
        'Check again and resend'));
    }
    return el('div', { class: 'card' },
      el('p', {}, el('strong', {}, `${v.customer}: ${v.pallets} pallets ${v.route}`), ' ',
        statusBadge(p.check_status), ' ', p.overdue ? badge('Overdue', 'bad') : null, ' ', badge(p.state, 'info')),
      el('p', { class: 'muted' },
        `From ${p.from_title} to ${p.to_title}. Price USD ${v.price}, cost USD ${v.cost}, due ${p.due || 'not set'}. Route: ${p.chain.join(' then ')}.`),
      p.return_reason ? el('p', { class: 'errors' }, `Returned: ${p.return_reason}`) : null,
      p.findings.length ? el('ul', { class: 'plain' }, p.findings.map((f) => el('li', {}, `${f.message} (${f.source})`))) : null,
      el('div', { class: 'row' }, actions));
  }

  async function refresh() {
    const res = await api(`/api/inbox?token=${encodeURIComponent(token)}`);
    const t = res.data.today;
    clear(todayBox,
      badge(`${t.waiting_for_me} waiting for you`, 'info'),
      badge(`${t.returned_to_me} returned to you`, t.returned_to_me ? 'warn' : 'info'),
      badge(`${t.in_team_queue} in your team queue`, 'info'),
      badge(`${t.overdue_for_my_role} overdue`, t.overdue_for_my_role ? 'bad' : 'info'));
    clear(list, res.data.packages.length ? res.data.packages.map(card) : el('p', { class: 'muted' }, 'Nothing here yet.'));
  }

  const soon = new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);
  const f = {
    to_role: el('select', { id: 'to-role' },
      (info.assistant?.handoffs || []).map((h) => el('option', { value: h.to_role }, `${h.to_role}: ${h.what}`))),
    customer: el('input', { id: 'h-customer', value: 'Acme Foods' }),
    route: el('select', { id: 'h-route' }, ROUTES.map((r) => el('option', { value: r }, r))),
    pallets: el('input', { id: 'h-pallets', type: 'number', min: '1', value: '10' }),
    price: el('input', { id: 'h-price', type: 'number', value: '1800' }),
    cost: el('input', { id: 'h-cost', type: 'number', value: '1500' }),
    delivery_date: el('input', { id: 'h-date', type: 'date', value: soon }),
    due: el('input', { id: 'h-due', type: 'date' }),
    notes: el('textarea', { id: 'h-notes' }),
  };
  const maskBox = el('div');
  const result = el('div');

  async function values() {
    const v = {};
    for (const key of ['customer', 'route', 'pallets', 'price', 'cost', 'delivery_date', 'notes']) v[key] = f[key].value;
    const notes = await confirmMask(v.notes, maskBox);
    return notes === null ? null : { ...v, notes };
  }

  const check = el('button', { onclick: async () => {
    const v = await values();
    if (!v) return;
    const res = await api('/api/precheck', { method: 'POST', body: { token, values: v } });
    clear(result, el('p', {}, statusBadge(res.data.status), ' Nothing was sent or stored.'),
      el('ul', { class: 'plain' }, res.data.findings.map((x) => el('li', {}, `${x.message} (${x.source})`))));
  } }, 'Check first');

  const sendBtn = el('button', { class: 'primary', onclick: async () => {
    const v = await values();
    if (!v) return;
    const res = await api('/api/handoffs', {
      method: 'POST', body: { token, to_role: f.to_role.value, values: v, due: f.due.value || null } });
    clear(result, res.ok ? el('p', {}, 'Sent. ', statusBadge(res.data.check_status))
      : el('p', { class: 'errors', role: 'alert' }, res.data.message));
    refresh();
  } }, 'Send handoff');

  refresh();
  const field = (label, node) => [el('label', { for: node.id }, label), node];
  return el('section', {}, el('h2', {}, 'Inbox'), todayBox, msg, list,
    el('h3', {}, 'Send a handoff'),
    el('p', { class: 'muted' }, 'It goes to the whole receiving team. Someone there takes it and decides. Nobody can decide on their own package.'),
    ...field('To', f.to_role), ...field('Customer', f.customer), ...field('Route', f.route),
    ...field('Pallets', f.pallets), ...field('Price (USD)', f.price), ...field('Cost (USD)', f.cost),
    ...field('Delivery date', f.delivery_date), ...field('Answer needed by (optional)', f.due),
    ...field('Notes (untrusted text)', f.notes), maskBox, el('div', { class: 'row' }, check, sendBtn), result);
}
