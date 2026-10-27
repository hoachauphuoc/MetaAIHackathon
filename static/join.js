// Employee page: chat with the role's assistant, and run a team workflow with a person approving
// every handoff. Chat history and workflow results live only in this browser (IndexedDB).
import { findingsBlock, inboxPanel } from '/static/inbox.js';
import { confirmMask } from '/static/mask.js';
import { api, badge, clear, demoNote, el, Expired, statusBadge } from '/static/ui.js';

const token = location.pathname.split('/').pop();
const app = document.getElementById('app');

// --- browser-only storage ----------------------------------------------------------------
function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('role-assistants', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('chat');
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function loadHistory() {
  try {
    const db = await openDb();
    return await new Promise((resolve) => {
      const get = db.transaction('chat').objectStore('chat').get(token);
      get.onsuccess = () => resolve(get.result || []);
      get.onerror = () => resolve([]);
    });
  } catch { return []; }
}
async function saveHistory(history) {
  try {
    const db = await openDb();
    db.transaction('chat', 'readwrite').objectStore('chat').put(history, token);
  } catch { /* storage can be blocked; the chat still works for this visit */ }
}

// --- chat ------------------------------------------------------------------------------
async function streamChat(message, history, onDelta) {
  const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, message, history }) });
  if (res.status === 410) throw new Expired();
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', done = null;
  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const [eventLine, dataLine] = block.split('\n');
      const data = JSON.parse(dataLine.slice(6));
      if (eventLine === 'event: delta') onDelta(data.text);
      if (eventLine === 'event: done') done = data;
    }
  }
  return done;
}

function chatPanel(info) {
  const log = el('div', { class: 'chat-log', role: 'log', 'aria-live': 'polite' });
  const input = el('textarea', { id: 'msg', placeholder: 'Ask your assistant...' });
  const notice = el('div');
  const maskBox = el('div');
  let history = [];
  const draw = (turn) => log.append(el('div', { class: `msg ${turn.role}` }, turn.content));
  loadHistory().then((saved) => { history = saved; history.forEach(draw); });

  const send = el('button', { class: 'primary', onclick: async () => {
    const typed = input.value.trim();
    if (!typed) return;
    send.disabled = true;
    const text = await confirmMask(typed, maskBox);
    if (text === null) { send.disabled = false; return; }
    input.value = '';
    const user = { role: 'user', content: text };
    draw(user);
    const reply = { role: 'assistant', content: '' };
    const bubble = el('div', { class: 'msg assistant' });
    log.append(bubble);
    try {
      const done = await streamChat(text, history, (chunk) => {
        reply.content += chunk; bubble.textContent = reply.content; log.scrollTop = log.scrollHeight; });
      clear(notice, done && done.demo_mode ? demoNote(done.demo_reason) : null);
      history = [...history, user, reply];
      saveHistory(history);
    } catch (e) { bubble.textContent = e instanceof Expired ? 'This link has ended.' : 'Something went wrong.'; }
    send.disabled = false;
  } }, 'Send');

  const compareBox = el('div');
  const compareBtn = el('button', { onclick: async () => {
    const typed = input.value.trim();
    if (!typed) return;
    compareBtn.disabled = true;
    const text = await confirmMask(typed, maskBox);
    if (text === null) { compareBtn.disabled = false; return; }
    clear(compareBox, el('p', { class: 'progress', role: 'status' }, 'Asking both assistants...'));
    const res = await api('/api/compare', { method: 'POST', body: { token, message: text } });
    const side = (title, part) => el('div', { class: 'card' }, el('h3', {}, title),
      part.demo_mode ? demoNote(part.demo_reason) : null, el('div', { class: 'msg assistant' }, part.text));
    clear(compareBox, el('div', { class: 'grid' },
      side(`${info.role?.title || 'Role'} assistant`, res.data.role), side('Generic AI', res.data.generic)));
    compareBtn.disabled = false;
  } }, 'Compare with generic AI');
  const jobs = el('div', { class: 'row' }, (info.assistant?.jobs || []).map((job) =>
    el('button', { onclick: () => { input.value = job; input.focus(); } }, job)));
  const clearBtn = el('button', { onclick: async () => { history = []; clear(log); saveHistory([]); } },
    'Clear my chat on this device');
  return el('section', {}, el('h2', {}, 'Chat'), el('p', { class: 'muted' },
    'Your messages are not stored on the server. They stay in this browser.'), jobs, log, notice, maskBox,
    el('label', { for: 'msg' }, 'Message'), input, el('div', { class: 'row' }, send, compareBtn, clearBtn), compareBox);
}

// --- first three days ------------------------------------------------------------------
// The plan and the ticks stay in this browser; the server and the owner never learn the progress.
const planKey = `first-days:${token}`;
function loadPlan() {
  try { return JSON.parse(localStorage.getItem(planKey)); } catch { return null; }
}
function savePlan(plan) {
  try { localStorage.setItem(planKey, JSON.stringify(plan)); } catch { /* blocked storage: ticks last this visit */ }
}

function firstDaysPanel() {
  const out = el('div');
  let plan = loadPlan();
  const draw = () => {
    if (!plan) { clear(out); return; }
    const done = new Set(plan.done || []);
    clear(out, plan.demo_mode ? demoNote(plan.demo_reason) : badge('Planned by Muse Spark from your role', 'ok'),
      plan.source === 'template' ? el('p', { class: 'muted' }, 'A standard plan for your role (Template).') : null,
      plan.days.map((tasks, d) => [el('h3', {}, `Day ${d + 1}`), el('ul', { class: 'plain' }, tasks.map((t, i) => {
        const id = `day${d}-task${i}`;
        const box = el('input', { id, type: 'checkbox', checked: done.has(id), onchange: () => {
          if (box.checked) done.add(id); else done.delete(id);
          plan.done = [...done];
          savePlan(plan);
        } });
        return el('li', { class: 'task' }, box, el('label', { for: id }, el('strong', {}, t.title), ' ', t.why,
          t.skill ? [' ', badge(`assistant: ${t.skill.replaceAll('_', ' ')}`, 'info')] : null));
      }))]).flat());
  };
  const make = el('button', { onclick: async () => {
    make.disabled = true;
    clear(out, el('p', { class: 'progress', role: 'status' }, 'Planning your first three days...'));
    const res = await api('/api/onboarding', { method: 'POST', body: { token } });
    make.disabled = false;
    if (!res.ok) { clear(out, el('p', { class: 'errors', role: 'alert' }, res.data.message)); return; }
    plan = { ...res.data, done: [] };
    savePlan(plan);
    draw();
    make.textContent = 'Make a new plan';
  } }, plan ? 'Make a new plan' : 'Plan my first three days');
  draw();
  return el('details', { class: 'section', open: !plan || (plan.done || []).length < plan.days.flat().length },
    el('summary', {}, el('h2', {}, 'Your first three days')),
    el('p', { class: 'muted' }, 'Ticks stay on this device. Nobody else sees how far you are.'),
    el('div', { class: 'row' }, make), out);
}

// --- workflow --------------------------------------------------------------------------
function workflowPanel(routes) {
  const box = el('section', {}, el('h2', {}, 'New order: Sales, Operations, Finance'));
  const f = {
    customer: el('input', { id: 'customer', value: 'Acme Foods' }),
    route: el('select', { id: 'route' }, routes.map((r) => el('option', { value: r }, r))),
    pallets: el('input', { id: 'pallets', type: 'number', min: '1', value: '12' }),
    delivery_date: el('input', { id: 'date', type: 'date',
      value: new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10) }),
    notes: el('textarea', { id: 'notes' }, ''),
  };
  const out = el('div');
  const maskBox = el('div');
  const start = el('button', { class: 'primary', onclick: async () => {
    const task = Object.fromEntries(Object.entries(f).map(([k, n]) => [k, n.value]));
    const notes = await confirmMask(task.notes, maskBox);
    if (notes === null) return;
    task.notes = notes;
    const res = await api('/api/workflow/plan', { method: 'POST', body: { token, task } });
    if (!res.ok) {
      clear(out, el('div', { class: 'errors', role: 'alert' }, res.data.message || res.data.errors?.join(' ')));
      return;
    }
    runner(res.data, out);
  } }, 'Plan this order');
  box.append(el('p', { class: 'muted' }, 'Each step runs one assistant. You approve every handoff; ' +
    'a blocked step can never be approved.'),
  el('label', { for: 'customer' }, 'Customer'), f.customer,
  el('label', { for: 'route' }, 'Shipping route'), f.route,
  el('label', { for: 'pallets' }, 'Pallets'), f.pallets,
  el('label', { for: 'date' }, 'Delivery date'), f.delivery_date,
  el('label', { for: 'notes' }, 'Notes from the customer (untrusted text)'), f.notes,
  maskBox, el('div', { class: 'row' }, start), out);
  return box;
}

function runner({ plan, signature, roles }, out) {
  const receipts = {};
  const items = plan.steps.map((step) => ({ step, node: el('li', { class: 'step waiting' },
    el('strong', {}, `${step.title} `), el('span', { class: 'muted' }, roles[step.role_id] || step.role_id,
      step.private ? ' (Private mode)' : ''))}));
  clear(out, el('ol', { class: 'steps' }, items.map((i) => i.node)));
  runStep(0);

  async function runStep(index) {
    if (index >= items.length) return;
    const { step, node } = items[index];
    node.className = 'step current';
    const progress = el('p', { class: 'progress', role: 'status' }, 'Working... (about 10 seconds)');
    node.append(progress);
    const base = { token, plan, signature, step_id: step.id };
    const res = await api('/api/workflow/step', { method: 'POST', body: { ...base, receipts } });
    progress.remove();
    if (!res.ok) { node.append(el('p', { class: 'errors', role: 'alert' }, res.data.message)); return; }
    const { result, ticket } = res.data;
    const approve = el('button', { class: 'primary', disabled: result.status === 'blocked' }, 'Approve and hand over');
    const stop = el('button', {}, 'Stop here');
    approve.addEventListener('click', async () => {
      approve.disabled = stop.disabled = true;
      const ok = await api('/api/workflow/approve', { method: 'POST', body: { ...base, result, ticket } });
      if (!ok.ok) { node.append(el('p', { class: 'errors' }, ok.data.message)); return; }
      receipts[step.id] = { result, receipt: ok.data.receipt };
      node.className = 'step';
      runStep(index + 1);
    });
    stop.addEventListener('click', () => { approve.disabled = stop.disabled = true;
      node.append(el('p', {}, badge('Stopped by you', 'warn'))); });
    node.append(...describe(result), el('div', { class: 'row' }, approve, stop));
  }
}

function describe(result) {
  const t = result.tool_result;
  const lines = [];
  lines.push(el('p', {}, statusBadge(result.status), ' ',
    result.private ? badge('Private mode', 'info') : null));
  if (result.demo_mode) lines.push(demoNote(result.demo_reason));
  if (t.price !== undefined && t.margin_pct !== undefined)
    lines.push(el('p', {}, `Price USD ${t.price.toLocaleString()}, cost USD ${t.cost.toLocaleString()}, margin ${t.margin_pct}% (computed by code).`));
  else if (t.ics) lines.push(el('p', {}, `Calendar event: ${t.title} on ${t.date}. `,
    el('a', { href: URL.createObjectURL(new Blob([t.ics], { type: 'text/calendar' })), download: 'delivery.ics' }, 'Download .ics')));
  if (result.summary) lines.push(el('p', {}, result.summary));
  lines.push(...findingsBlock(result.findings));
  lines.push(el('details', {}, el('summary', {}, 'Agent activity'), el('ul', { class: 'plain' },
    result.trace.map((x) => el('li', {}, `${x.tool}: ${x.model}, ${x.ms} ms${x.demo_mode ? ', demo' : ''}`)))));
  return lines;
}

// --- page ------------------------------------------------------------------------------
(async () => {
  try {
    const res = await api(`/api/invite/${encodeURIComponent(token)}`);
    const info = res.data;
    document.getElementById('title').textContent = `${info.role?.title || 'Your role'} at ${info.company || 'your company'}`;
    if (!info.assistant) {
      clear(app, el('section', {}, el('p', {}, 'Your assistant is not ready yet. Ask the owner to build the assistants first.')));
      return;
    }
    clear(app, el('section', {}, el('h2', {}, 'Your assistant'), el('p', {}, info.assistant.goal),
      info.assistant.demo_mode ? demoNote(info.assistant.demo_reason) : null,
      el('h3', {}, 'Limits'), el('ul', { class: 'plain' }, info.assistant.limits.map((l) => el('li', {}, l)))),
      firstDaysPanel(), inboxPanel(info, token), chatPanel(info),
      // The fixed Sales, Operations, Finance order runs on the pallet rate card, so only that form has it.
      ...(info.handoff_schema.id === 'logistics'
        ? [workflowPanel(info.handoff_schema.fields.find((f) => f.key === 'route').options)] : []));
  } catch (e) {
    clear(app, el('section', {}, el('p', { class: 'errors', role: 'alert' },
      'This link has ended or was never valid. Ask the owner for a new one.')));
  }
})();
