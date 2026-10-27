// Owner flow: survey -> org chart -> edit and accept -> assistants -> invite links.
import { api, badge, clear, demoNote, el, Expired } from '/static/ui.js';

const app = document.getElementById('app');
const FIELDS = [
  ['company_name', 'Company name'], ['industry', 'Industry (logistics, retail or services)'],
  ['headcount', 'How many people work there?'], ['locations', 'Where do you work?'],
  ['departments', 'Which teams exist?'], ['managers', 'Who manages whom?'],
  ['work_mode', 'On site, remote or mixed?'], ['main_work', 'What is the main work?'],
  ['tools', 'Which tools do you use today?'], ['time_sinks', 'Where does time get wasted?'],
];
const PROVENANCE = {
  answers: ['From your answers', 'ok'], ai: ['AI suggestion', 'info'], template: ['Template', 'warn'],
};

let sandbox = localStorage.getItem('sandbox');
let state = { answers: null, chart: null, accepted: false };

function startAgain(message) {
  localStorage.removeItem('sandbox');
  sandbox = null;
  state = { answers: null, chart: null, accepted: false };
  clear(app, el('section', {},
    el('h2', {}, 'Welcome'),
    message ? el('p', { class: 'errors', role: 'alert' }, message) : null,
    el('p', {}, 'Answer ten questions and get an org chart with an AI assistant for every role. ' +
      'You decide at every step. Nothing you chat is stored.'),
    el('div', { class: 'row' }, el('button', { class: 'primary', onclick: tryDemo }, 'Try the demo company'))));
}

async function tryDemo() {
  const made = await api('/api/sandbox', { method: 'POST' });
  sandbox = made.data.sandbox;
  localStorage.setItem('sandbox', sandbox);
  state.answers = (await api('/api/survey/demo')).data.answers;
  showSurvey();
}

function guard(fn) {
  return async (...args) => {
    try { await fn(...args); } catch (e) {
      if (e instanceof Expired) startAgain('This sandbox has ended. Start again.'); else throw e;
    }
  };
}

function showSurvey() {
  const inputs = {};
  const form = el('section', {}, el('h2', {}, '1. About the company'),
    el('p', { class: 'muted' }, 'Prefilled with a demo company. Change anything.'));
  for (const [key, label] of FIELDS) {
    inputs[key] = el('input', { id: key, value: state.answers[key] ?? '' });
    form.append(el('label', { for: key }, label), inputs[key]);
  }
  const status = el('p', { class: 'progress', role: 'status' });
  const button = el('button', { class: 'primary', onclick: guard(async () => {
    for (const key in inputs) state.answers[key] = inputs[key].value;
    button.disabled = true;
    status.textContent = 'Muse Wonder is designing your chart (about 20 seconds)...';
    const res = await api('/api/chart', { method: 'POST', sandbox, body: { answers: state.answers } });
    if (!res.ok) {
      button.disabled = false;
      status.textContent = res.data.message || 'Something went wrong.';
      return;
    }
    state.chart = res.data;
    state.accepted = false;
    showChart();
  }) }, 'Design my org chart');
  form.append(el('div', { class: 'row' }, button), status);
  clear(app, form);
}

function showChart() {
  const chart = state.chart;
  const list = el('div', { class: 'grid' });
  const errorBox = el('div', { role: 'alert' });
  const accept = el('button', { class: 'primary' }, 'Accept this chart');

  async function revalidate() {
    const res = await api('/api/chart/validate', { method: 'POST', sandbox,
      body: { roles: chart.roles, size: chart.size } });
    clear(errorBox, res.data.errors.length ? el('div', { class: 'errors' },
      'Fix these before you accept:', el('ul', {}, res.data.errors.map((e) => {
        const who = chart.roles.find((r) => r.id === e.role_id);
        return el('li', {}, who ? `${who.title}: ${e.message}` : e.message);
      }))) : null);
    accept.disabled = !res.data.ok;
  }

  function draw() {
    clear(list, chart.roles.map((role) => {
      const [label, kind] = PROVENANCE[role.source] || [role.source, 'info'];
      const title = el('input', { id: `t-${role.id}`, value: role.title,
        onchange: guard(async (e) => { role.title = e.target.value; await revalidate(); }) });
      const boss = el('select', { id: `b-${role.id}`, onchange: guard(async (e) => {
        role.reports_to = e.target.value || null; await revalidate(); }) },
        el('option', { value: '' }, '(top of the company)'),
        chart.roles.filter((r) => r.id !== role.id).map((r) =>
          el('option', { value: r.id, selected: r.id === role.reports_to }, r.title)));
      if (role.reports_to === null) boss.value = '';
      const heads = el('input', { id: `h-${role.id}`, type: 'number', min: '1', value: role.headcount,
        onchange: guard(async (e) => { role.headcount = Number.parseInt(e.target.value, 10);
          await revalidate(); }) });
      return el('div', { class: 'card' }, badge(label, kind),
        el('label', { for: `t-${role.id}` }, 'Title'), title,
        el('label', { for: `b-${role.id}` }, 'Reports to'), boss,
        el('label', { for: `h-${role.id}` }, 'People'), heads,
        role.reason ? el('p', { class: 'muted' }, role.reason) : null);
    }));
  }

  accept.addEventListener('click', guard(async () => {
    accept.disabled = true;
    const res = await api('/api/company', { method: 'POST', sandbox,
      body: { company: chart.company, size: chart.size, roles: chart.roles } });
    if (res.ok) { state.accepted = true; showAssistants(); } else await revalidate();
  }));

  clear(app, el('section', {}, el('h2', {}, `2. Org chart: ${chart.company || 'your company'}`),
    chart.demo_mode ? demoNote(chart.demo_reason) : el('p', {}, badge('Designed by Muse Wonder', 'ok'),
      ' The rules checked it: one top role, no circles, no more people than you have.'),
    chart.source === 'template' ? el('p', { class: 'muted' }, 'This is a standard chart (Template).') : null,
    list, errorBox, el('div', { class: 'row' }, accept)));
  draw();
  revalidate();
}

async function showAssistants() {
  const roles = state.chart.roles;
  const grid = el('div', { class: 'grid' });
  const switchBox = el('input', { id: 'muse-off', type: 'checkbox', onchange: guard(async (e) => {
    await api('/api/sandbox/muse', { method: 'POST', sandbox, body: { off: e.target.checked } });
  }) });
  clear(app, el('section', {}, el('h2', {}, '3. One assistant per role'),
    el('p', { class: 'progress', role: 'status' }, 'Muse Spark is writing every role brief in parallel...'),
    grid,
    el('div', { class: 'row' }, switchBox,
      el('label', { for: 'muse-off', style: 'margin:0;font-weight:400' },
        'Switch Muse off for this sandbox (to see the labelled demo mode)'))));
  const cards = Object.fromEntries(roles.map((r) => {
    const card = el('div', { class: 'card' }, el('h3', {}, r.title), el('p', { class: 'progress' }, 'Writing...'));
    grid.append(card);
    return [r.id, card];
  }));
  await Promise.all(roles.map(guard(async (role) => {
    const res = await api('/api/assistants', { method: 'POST', sandbox, body: { role_id: role.id } });
    if (!res.ok) { clear(cards[role.id], el('h3', {}, role.title), el('p', { class: 'errors' }, res.data.message)); return; }
    const kit = res.data;
    const link = el('p', { class: 'muted', role: 'status' });
    clear(cards[role.id], el('h3', {}, role.title),
      kit.demo_mode ? demoNote(kit.demo_reason) : badge('Written by Muse Spark', 'ok'),
      el('p', {}, kit.goal),
      el('h3', {}, 'Skills'), el('ul', { class: 'plain' }, kit.skills.map((s) => el('li', {}, s))),
      kit.removed_skills.length ? el('p', { class: 'errors' }, 'Removed by the rules: ', kit.removed_skills.join(', ')) : null,
      el('h3', {}, 'Hands work to'), el('ul', { class: 'plain' }, kit.handoffs.length
        ? kit.handoffs.map((h) => el('li', {}, `${h.to_role}: ${h.what}`)) : el('li', {}, 'Nobody')),
      el('div', { class: 'row' }, el('button', { onclick: guard(async () => {
        const inv = await api('/api/invites', { method: 'POST', sandbox, body: { role_id: role.id, display_name: role.title } });
        clear(link, inv.ok ? [el('a', { href: inv.data.url, target: '_blank', rel: 'noopener' }, 'Open invite link'),
          ' ', el('code', {}, location.origin + inv.data.url)] : inv.data.message);
      }) }, 'Create invite link')), link);
  })));
  app.querySelector('.progress').textContent = 'Each person opens their own link and lands in their role. ' +
    'Open the Sales link to run a new order through Sales, Operations and Finance.';
}

if (sandbox) {
  guard(async () => {
    const res = await api('/api/company', { sandbox });
    if (res.data.company) {
      state.chart = { ...res.data.company, errors: [], demo_mode: false, source: 'saved' };
      state.accepted = true;
      showAssistants();
    } else { state.answers = (await api('/api/survey/demo')).data.answers; showSurvey(); }
  })();
} else startAgain();
