// Employee page: chat with the role's assistant, and run a team workflow with a person approving
// every handoff. Chat history and workflow results live only in this browser (IndexedDB).
import { findingsBlock, inboxPanel, inputFor } from '/static/inbox.js';
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
async function streamChat(message, history, onDelta, onRead) {
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
      if (eventLine === 'event: read') onRead(data.looked);
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
      // What the assistant read is shown with the answer and is not part of the saved history.
      const done = await streamChat(text, history, (chunk) => {
        reply.content += chunk; bubble.textContent = reply.content; log.scrollTop = log.scrollHeight; },
      (looked) => bubble.after(el('p', { class: 'muted looked' }, `Looked at: ${looked.join(', ')}. Read only.`)));
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
  const asks = ['What is waiting for me?', 'Which of my documents were returned, and why?'];
  const jobs = el('div', { class: 'row' }, [...asks, ...(info.assistant?.jobs || [])].map((job) =>
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

// --- leaving ---------------------------------------------------------------------------
// The draft lives on this page only. Sending makes it a company document for the person's own team.
function handoverPanel(form) {
  const notes = el('textarea', { id: 'handover-notes', maxlength: '2000',
    placeholder: 'What is half done, where things are, what you wish you had known' });
  const inputs = Object.fromEntries(form.fields.map((f) => [f.key, inputFor('handover', f, '')]));
  const maskBox = el('div');
  const status = el('div', { role: 'status' });
  const draft = el('button', { onclick: async () => {
    const typed = await confirmMask(notes.value, maskBox);
    if (typed === null) return;
    draft.disabled = true;
    clear(status, el('p', { class: 'progress' }, 'Drafting from your open documents and your notes...'));
    const res = await api('/api/handover/draft', { method: 'POST', body: { token, notes: typed } });
    draft.disabled = false;
    if (!res.ok) { clear(status, el('p', { class: 'errors', role: 'alert' }, res.data.message)); return; }
    for (const f of form.fields) inputs[f.key].value = res.data.values[f.key] ?? '';
    clear(status, res.data.demo_mode ? demoNote(res.data.demo_reason) : badge('Drafted by Muse Spark', 'ok'),
      el('p', { class: 'muted' }, `From ${res.data.documents} open document${res.data.documents === 1 ? '' : 's'} and your notes. Edit anything before sending.`));
  } }, 'Draft my handover');
  const send = el('button', { class: 'primary', onclick: async () => {
    const values = {};
    for (const f of form.fields) {
      const masked = await confirmMask(inputs[f.key].value, maskBox);
      if (masked === null) return;
      values[f.key] = masked;
    }
    const res = await api('/api/handover', { method: 'POST', body: { token, values } });
    clear(status, res.ok ? el('p', {}, badge('Sent', 'ok'), ` To the ${res.data.to_title} team. Someone there takes it; you cannot accept it yourself.`)
      : el('p', { class: 'errors', role: 'alert' }, res.data.message));
  } }, 'Send handover');
  return el('details', { class: 'section' }, el('summary', {}, el('h2', {}, "I'm leaving: prepare my handover")),
    el('p', { class: 'muted' }, 'Only you see the draft. Nothing is sent until you press Send handover. ' +
      'It goes to your own team, or to the top role if nobody shares your role. Nothing about you is scored.'),
    el('label', { for: notes.id }, 'Your notes (optional)'), notes, el('div', { class: 'row' }, draft),
    form.fields.map((f) => [el('label', { for: inputs[f.key].id }, f.required ? f.label : `${f.label} (optional)`), inputs[f.key]]).flat(),
    maskBox, el('div', { class: 'row' }, send), status);
}

// --- workflow --------------------------------------------------------------------------
// Before Finance runs on the open-weights model, say honestly whether it is likely awake. The server only reports when
// the endpoint last answered; it does not probe, so reading this never wakes or bills the endpoint.
const WARM_S = 600;
async function privateReadiness() {
  const res = await api('/api/private/status');
  if (!res.ok) return null;
  const s = res.data;
  if (!s.configured) return 'Private mode is not set up on this server: the Finance step will be marked for a person to check.';
  if (s.answered_s_ago !== null && s.answered_s_ago < WARM_S)
    return [badge('Private mode: probably warm', 'ok'), ` ${s.model} answered ${Math.max(1, Math.round(s.answered_s_ago / 60))} min ago.`];
  return [badge('Private mode: may be asleep', 'warn'), ` ${s.model} has not answered in the last 10 minutes. ` +
    'It sleeps when idle, so the Finance step may say it is starting and retry on its own (about 3 minutes).'];
}

function workflowPanel(routes) {
  const box = el('section', { id: 'order' }, el('h2', {}, 'New order: Sales, Operations, Finance'));
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
  const ready = el('p', { class: 'muted', role: 'status' });
  privateReadiness().then((line) => clear(ready, line));
  box.append(ready, el('p', { class: 'muted' }, 'Unlike a chat, each step is one assistant making a tool call; code ' +
    'computes the numbers, and the next role starts only with your signed approval. ' +
    'A blocked step can never be approved.'),
  el('label', { for: 'customer' }, 'Customer'), f.customer,
  el('label', { for: 'route' }, 'Shipping route'), f.route,
  el('label', { for: 'pallets' }, 'Pallets'), f.pallets,
  el('label', { for: 'date' }, 'Delivery date'), f.delivery_date,
  el('label', { for: 'notes' }, 'Notes from the customer (untrusted text)'), f.notes,
  maskBox, el('div', { class: 'row' }, start), out);
  return box;
}

const WAKE_TRIES = 5;  // about 5 x (35 s wait + 25 s pause): longer than the 166 s cold start measured
const WAKE_WAIT_S = 25;

function runner({ plan, signature, roles }, out) {
  const receipts = {};
  const items = plan.steps.map((step) => ({ step, node: el('li', { class: 'step waiting' },
    el('strong', {}, `${step.title} `), el('span', { class: 'muted' }, roles[step.role_id] || step.role_id,
      step.private ? ' (Private mode)' : ''))}));
  clear(out, el('ol', { class: 'steps' }, items.map((i) => i.node)));
  runStep(0);

  async function runStep(index, attempt = 0) {
    if (index >= items.length) return;
    const { step, node } = items[index];
    node.className = 'step current';
    const progress = el('p', { class: 'progress', role: 'status' },
      step.private ? 'Working in Private mode... (up to 40 seconds)' : 'Working... (about 10 seconds)');
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
      // The server signs what the person approved; the next step runs only with that receipt.
      node.append(el('p', {}, badge('Approved: signed receipt', 'ok'),
        index + 1 < items.length ? ' The next step can start only with it.' : ' The order is complete.'));
      runStep(index + 1);
    });
    stop.addEventListener('click', () => { approve.disabled = stop.disabled = true;
      node.append(el('p', {}, badge('Stopped by you', 'warn'))); });
    // A cold Private endpoint answers "starting" and wakes in about 3 minutes: the step retries on its own
    // a few times, with a visible countdown, and a person can still retry at once. It never switches models.
    let timer = null;
    const rerun = () => {
      clearInterval(timer);
      node.replaceChildren(...[...node.children].slice(0, 2));  // keep the title and the role
      runStep(index, attempt + 1);
    };
    const again = result.private && result.demo_mode ? el('button', { onclick: rerun }, 'Run this step again') : null;
    const waking = result.demo_reason === 'Private mode starting' && attempt < WAKE_TRIES;
    const countdown = waking ? el('p', { class: 'progress', role: 'status' }) : null;
    node.append(...describe(result), ...(countdown ? [countdown] : []), el('div', { class: 'row' }, approve, again, stop));
    if (waking) {
      let left = WAKE_WAIT_S;
      const tick = () => {
        countdown.textContent = `Private mode is waking up (about 3 minutes). Trying again in ${left} s ` +
          `(try ${attempt + 2} of ${WAKE_TRIES + 1}).`;
        if (left-- <= 0) rerun();
      };
      tick();
      timer = setInterval(tick, 1000);
      [approve, stop].forEach((b) => b.addEventListener('click', () => { clearInterval(timer); countdown.remove(); }));
    }
  }
}

function describe(result) {
  const t = result.tool_result;
  const lines = [];
  // The id comes from the provider's own response; a step no model answered shows none, only the demo note.
  const answered = result.trace.find((x) => x.answered_by && !x.demo_mode);
  lines.push(el('p', {}, statusBadge(result.status), ' ',
    result.private ? badge('Private mode', 'info') : null, ' ',
    answered ? badge(`Answered by ${answered.answered_by}`, 'ok') : null));
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

// --- my private rules ------------------------------------------------------------------
// Tighten-only: the server refuses a number looser than the company's and the form says which one.
// What is saved here is read back only with this invite link; the owner has no route to it.
const RULE_LABELS = {
  margin_floor_pct: ['Margin floor (%)', 'At least', 'The company allows nothing below'],
  escalation_usd: ['Approval limit (USD)', 'At most', 'The company escalates above'],
};
function personalRulesPanel() {
  const out = el('div');
  const status = el('p', { class: 'progress', role: 'status' });
  const errors = el('div', { role: 'alert' });
  const inputs = {};
  const body = el('details', { class: 'section' }, el('summary', {}, el('h2', {}, 'My private rules')),
    el('p', { class: 'muted' }, 'Stricter limits for your own assistant only. Only you can read them: ' +
      'not the owner, not your unit. They can never be looser than the company limits.'), out);
  const load = async () => {
    const res = await api(`/api/personal-rules?token=${encodeURIComponent(token)}`);
    const above = res.data.company || {}, mine = res.data.rules || {};
    clear(out);
    for (const rule of Object.keys(RULE_LABELS)) {
      const [label, direction, note] = RULE_LABELS[rule];
      inputs[rule] = el('input', { id: `pr-${rule}`, type: 'number', inputmode: 'decimal', value: mine[rule] ?? above[rule] ?? '' });
      out.append(el('label', { for: `pr-${rule}` }, label),
        el('p', { class: 'muted' }, `${direction} ${above[rule]} for you. ${note} ${above[rule]}.`), inputs[rule]);
    }
    out.append(el('div', { class: 'row' }, el('button', { class: 'primary', onclick: save }, 'Save my rules')), errors, status);
  };
  const save = async () => {
    const values = {};
    for (const rule in inputs) values[rule] = inputs[rule].value === '' ? null : Number(inputs[rule].value);
    const res = await api('/api/personal-rules?soft=1', { method: 'PUT', body: { token, ...values } });
    clear(errors);
    if (res.ok && res.data.saved !== false) { status.textContent = 'Saved. Only your assistant uses these.'; return; }
    status.textContent = '';
    errors.append(el('div', { class: 'errors' }, el('ul', {}, (res.data.errors || [{ message: res.data.message || 'Could not save.' }])
      .map((e) => el('li', {}, e.message)))));
  };
  load();
  return body;
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
    const ordering = info.handoff_schema.id === 'logistics';
    // The order flow is the page's main job but sits below the inbox and chat: one primary step reaches it.
    const toOrder = ordering ? el('div', { class: 'row' }, el('button', { class: 'primary', onclick: () => {
      document.getElementById('order').scrollIntoView({ behavior: 'smooth' });
      document.getElementById('customer').focus({ preventScroll: true });
    } }, 'Start a new order')) : null;
    clear(app, el('section', {}, el('h2', {}, 'Your assistant'), el('p', {}, info.assistant.goal),
      info.assistant.demo_mode ? demoNote(info.assistant.demo_reason) : null, toOrder,
      el('h3', {}, 'Limits'), el('ul', { class: 'plain' }, info.assistant.limits.map((l) => el('li', {}, l)))),
      firstDaysPanel(), inboxPanel(info, token), chatPanel(info), personalRulesPanel(),
      // The fixed Sales, Operations, Finance order runs on the pallet rate card, so only that form has it.
      ...(ordering
        ? [workflowPanel(info.handoff_schema.fields.find((f) => f.key === 'route').options)] : []),
      handoverPanel(info.handover_form));
  } catch (e) {
    clear(app, el('section', {}, el('p', { class: 'errors', role: 'alert' },
      'This link has ended or was never valid. Ask the owner for a new one.')));
  }
})();
