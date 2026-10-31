// Owner flow: survey -> org chart -> edit and accept -> assistants -> invite links.
import { photoPicker } from '/static/photo.js';
import { timeTile } from '/static/tile.js';
import { api, badge, clear, demoNote, el, Expired, statusBadge, streamEvents } from '/static/ui.js';

const app = document.getElementById('app');
const FIELDS = [
  ['company_name', 'Company name'], ['industry', 'Industry (logistics, retail, services, clinic or software)'],
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

const FOUNDER_STORY = 'https://github.com/hoachauphuoc/MetaAIHackathon#founders-story-why-role-assistants';
// Said where a demo starts, not only on /trust: a stranger should not build on a sandbox that a restart can wipe.
const SANDBOX_NOTE = 'This is a demo sandbox: it is kept for 24 hours and is lost if the server restarts.';

function startAgain(message) {
  localStorage.removeItem('sandbox');
  sandbox = null;
  state = { answers: null, chart: null, accepted: false };
  clear(app, el('section', {},
    el('div', { class: 'hero' },
      el('p', { class: 'eyebrow' }, 'Meta Global AI Developer Hackathon · Indie · Build for Your World'),
      el('h2', {}, 'A staff of assistants for a team too small to hire.'),
      el('p', { class: 'lede' }, 'Answer ten questions. Code checks the org. Each role gets its own assistant, ' +
        'and every handoff waits for a person.'),
      el('div', { class: 'row' }, el('button', { class: 'primary', onclick: tryDemo }, 'Try the demo company'),
        el('button', { onclick: () => tryDemo('clinic') }, 'Try the clinic demo'),
        el('button', { onclick: () => tryDemo('software') }, 'Try the software studio demo')),
      el('ul', { class: 'trust-row', 'aria-label': 'How it is built' },
        ['Muse Wonder drafts the org', 'Muse Spark writes the briefs', 'Glimmer Private option', 'No silent fallback']
          .map((t) => el('li', {}, badge(t, 'info'))))),
    message ? el('p', { class: 'errors', role: 'alert' }, message) : null,
    el('p', { class: 'why' }, el('strong', {}, 'The problem: '), 'staff who fear AI the company can watch paste ' +
      'client work into outside chatbots, and a company can neither ban that nor force its own tool. Here the company ' +
      'sets the roles, skills and limits, each employee’s chat stays in their own browser, and a person approves every handoff. ',
      el('a', { href: FOUNDER_STORY, target: '_blank', rel: 'noopener' }, 'Why I built this')),
    el('p', {}, 'Answer ten questions and get an org chart with an AI assistant for every role. ' +
      'You decide at every step. Nothing you chat is stored.'),
    el('ol', { class: 'how' },
      el('li', {}, 'Muse Wonder designs your org chart from the ten answers.'),
      el('li', {}, 'Code checks it against the rules before you can accept it.'),
      el('li', {}, 'Muse Spark writes one assistant per role; work moves between roles only when a person approves.')),
    el('p', { class: 'muted' }, 'The clinic demo runs the same engine in a second industry: its own "Treatment plan quote" ' +
      'form, checked by the same code rules (fee not below cost, margin floor), passed on only when a person approves.'),
    el('p', { class: 'muted', id: 'sandbox-note' }, SANDBOX_NOTE)));
  recordedDemo().then((demo) => { const hero = app.querySelector('.hero'); if (demo && hero) hero.after(demo); });
  timeTile().then((tile) => { if (tile && app.querySelector('.hero')) app.append(tile); });
}

// The recording is a file the owner adds after filming with the Private endpoint warm. Until it exists the page shows
// nothing, never a broken player. Its date is the file's own Last-Modified, so the label cannot drift from the file.
const DEMO_VIDEO = '/static/video/welcome.mp4';
async function recordedDemo() {
  const head = await fetch(DEMO_VIDEO, { method: 'HEAD' }).catch(() => null);
  if (!head || !head.ok || !(head.headers.get('Content-Type') || '').startsWith('video/')) return null;
  const when = new Date(head.headers.get('Last-Modified') || Date.now()).toISOString().slice(0, 10);
  return el('section', { class: 'recording' }, el('h2', {}, 'Watch the recorded demo'),
    el('video', { src: DEMO_VIDEO, controls: true, preload: 'none', playsinline: true,
      'aria-label': 'Recorded demo of the order workflow, with captions burned in' }),
    el('p', { class: 'muted' }, `A recording from ${when}, filmed while the Private endpoint was warm. A live Private step ` +
      'that starts cold can take a few minutes, and the live app is the one to trust.'));
}

async function tryDemo(industry) {
  const made = await api('/api/sandbox', { method: 'POST' });
  sandbox = made.data.sandbox;
  localStorage.setItem('sandbox', sandbox);
  // The demo reaches the Private-mode Finance step a few minutes from now; wake the endpoint while the owner reads.
  api('/api/private/prewarm', { method: 'POST', sandbox });
  state.answers = (await api(`/api/survey/demo${industry === 'clinic' || industry === 'software' ? `?industry=${industry}` : ''}`)).data.answers;
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
    el('p', { class: 'muted' }, 'Prefilled with a demo company. Change anything. ', SANDBOX_NOTE));
  for (const [key, label] of FIELDS) {
    inputs[key] = el('input', { id: key, value: state.answers[key] ?? '' });
    form.append(el('label', { for: key }, label), inputs[key]);
  }
  // Counts what is really typed: the ten answers are the whole input, so the bar is the share filled in.
  const filled = () => FIELDS.filter(([key]) => inputs[key].value.trim()).length;
  const meter = el('div', { class: 'meter', role: 'status' }, el('span', {}), el('div', { class: 'bar' }, el('i', {})));
  const drawMeter = () => {
    const n = filled();
    meter.firstChild.textContent = `Company answers: ${n} of ${FIELDS.length} filled in`;
    meter.querySelector('i').style.width = `${(100 * n) / FIELDS.length}%`;
  };
  form.insertBefore(meter, form.children[1]);
  Object.values(inputs).forEach((i) => i.addEventListener('input', drawMeter));
  drawMeter();
  const status = el('p', { class: 'progress', role: 'status' });
  // Made once by Muse Image when the app was built and served as a file: an image call during the wait would only
  // add to the wait. The caption says it is not the company's chart; the step line above it is the real progress.
  const art = el('figure', { class: 'wait-art', hidden: true },
    el('img', { src: '/static/img/chart-wait.webp', alt: 'A pencil drawing the lines of an org chart', width: '240', height: '240' }),
    el('figcaption', { class: 'muted' }, 'Illustration made once by Muse Image (muse-image-1.0), not a picture of your chart.'));
  const button = el('button', { class: 'primary', onclick: guard(async () => {
    for (const key in inputs) state.answers[key] = inputs[key].value;
    button.disabled = true;
    art.hidden = false;
    // Each line is a step the server really reached; the seconds are the real time since the step began.
    let step = 0, began = Date.now(), line = '';
    const draw = () => { status.textContent = `${line} (${Math.round((Date.now() - began) / 1000)} s)`; };
    const ticker = setInterval(draw, 1000);
    let result;
    try {
      result = await streamEvents('/api/chart?stream=1', { sandbox, body: { answers: state.answers },
        onEvent: (name, data) => {
          if (name !== 'stage') return;
          step += 1; began = Date.now(); line = `Step ${step} of 3: ${data.text}`; draw();
        } });
    } finally { clearInterval(ticker); }
    if (!result || result.error) {
      button.disabled = false;
      art.hidden = true;
      status.textContent = result?.error || 'Something went wrong.';
      return;
    }
    state.chart = result;
    state.accepted = false;
    showChart();
  }) }, 'Design my org chart');
  form.append(el('div', { class: 'row sticky-actions' }, button), status, art);
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
      body: { company: chart.company, size: chart.size, roles: chart.roles, industry: state.answers?.industry } });
    if (res.ok) { state.accepted = true; showAssistants(); } else await revalidate();
  }));

  clear(app, el('section', {}, el('h2', {}, `2. Org chart: ${chart.company || 'your company'}`),
    chart.demo_mode ? demoNote(chart.demo_reason) : el('p', {}, badge('Designed by Muse Wonder', 'ok'),
      ` The rules checked it: ${chart.roles.filter((r) => !r.reports_to).length} top role, no circles, ` +
      `${chart.roles.reduce((n, r) => n + r.headcount, 0)} of ${chart.size} people placed.`),
    chart.source === 'template' ? el('p', { class: 'muted' }, 'This is a standard chart (Template).') : null,
    list, errorBox, el('div', { class: 'row sticky-actions' }, accept)));
  draw();
  revalidate();
}

async function showAssistants() {
  const roles = state.chart.roles;
  const grid = el('div', { class: 'grid' });
  // Cards already written keep their text; this banner is the visible proof that the switch took effect,
  // including when the page runs without a model and every card already says Demo mode.
  const offNote = el('p', { class: 'demo-note', role: 'status', hidden: true },
    'Muse is switched off for this sandbox. From now on every model answer here is labelled Demo mode ' +
    'and a person must write it.');
  const switchBox = el('input', { id: 'muse-off', type: 'checkbox', onchange: guard(async (e) => {
    const res = await api('/api/sandbox/muse', { method: 'POST', sandbox, body: { off: e.target.checked } });
    if (res.ok) offNote.hidden = !e.target.checked;
  }) });
  clear(app, el('section', {}, el('h2', {}, '3. One assistant per role'),
    offNote,
    el('p', { class: 'progress', role: 'status' }, 'Muse Spark is writing every role brief in parallel...'),
    grid,
    el('div', { class: 'row' }, switchBox,
      el('label', { for: 'muse-off', class: 'inline-label' },
        'Switch Muse off for this sandbox (to see the labelled demo mode)'))));
  const cards = Object.fromEntries(roles.map((r) => {
    const card = el('div', { class: 'card' }, el('h3', {}, r.title), el('p', { class: 'progress' }, 'Writing...'));
    grid.append(card);
    return [r.id, card];
  }));
  const peopleList = el('div');
  app.append(el('section', {}, el('h2', {}, 'People'),
    el('p', { class: 'muted' }, 'Only a name, a role and a link. Removing someone revokes their link at once ' +
      'and returns the work they held to the team queue.'), peopleList));
  async function drawPeople() {
    const res = await api('/api/people', { sandbox });
    clear(peopleList, res.data.people.filter((p) => p.status === 'active').map((p) => el('div', { class: 'row' },
      `${p.display_name} (${roles.find((r) => r.id === p.role_id)?.title || p.role_id})`,
      el('button', { onclick: guard(async () => {
        if (!confirm(`Remove ${p.display_name}? Their link stops working now.`)) return;
        await api(`/api/people/${p.id}/offboard`, { method: 'POST', sandbox });
        drawPeople();
      }) }, 'Remove'))));
  }
  app.append(handoffFormSection(), levelsSection(), briefSection());
  // A workflow moves only along handoffs every assistant declared, so a link opened before the last brief
  // is written lands on a page whose order cannot be planned yet: links open once all briefs are done.
  const inviteButtons = [];
  const inviteButton = (b) => { inviteButtons.push(b); return b; };
  await Promise.all(roles.map(guard(async (role) => {
    const res = await api('/api/assistants', { method: 'POST', sandbox, body: { role_id: role.id } });
    if (!res.ok) { clear(cards[role.id], el('h3', {}, role.title), el('p', { class: 'errors' }, res.data.message)); return; }
    const kit = res.data;
    const link = el('p', { class: 'muted', role: 'status' });
    clear(cards[role.id], el('h3', {}, role.title),
      kit.demo_mode ? demoNote(kit.demo_reason) : badge('Written by Muse Spark', 'ok'),
      el('p', {}, kit.goal),
      el('h3', {}, 'Skills'), el('ul', { class: 'plain' }, kit.skills.map((s) => el('li', {}, s.replaceAll('_', ' ')))),
      kit.removed_skills.length ? el('p', { class: 'errors' }, 'Removed by the rules: ', kit.removed_skills.join(', ')) : null,
      el('h3', {}, 'Hands work to'), el('ul', { class: 'plain' }, kit.handoffs.length
        ? kit.handoffs.map((h) => el('li', {}, `${roles.find((r) => r.id === h.to_role)?.title || h.to_role}: ${h.what}`)) : el('li', {}, 'Nobody')),
      el('div', { class: 'row' }, inviteButton(el('button', { disabled: true, onclick: guard(async () => {
        const inv = await api('/api/invites', { method: 'POST', sandbox, body: {
          role_id: role.id, display_name: `${role.title} ${Math.random().toString(36).slice(2, 5)}` } });
        drawPeople();
        clear(link, inv.ok ? [el('a', { href: inv.data.url, target: '_blank', rel: 'noopener' }, 'Open invite link'),
          ' ', el('code', {}, location.origin + inv.data.url)] : inv.data.message);
      }) }, 'Create invite link'))), link);
  })));
  inviteButtons.forEach((b) => { b.disabled = false; });
  app.querySelector('.progress').textContent = 'Each person opens their own link and lands in their role. ' +
    'Open the Sales link to run a new order through Sales, Operations and Finance.';
}

// Read-only on purpose: signing happens in the top role's inbox, where maker-checker applies.
function briefSection() {
  const out = el('div');
  const headings = { needs_signature: 'Needs the top role to sign', stuck: 'Stuck', today: 'Moving today' };
  const write = el('button', { onclick: guard(async () => {
    write.disabled = true;
    clear(out, el('p', { class: 'progress', role: 'status' }, 'Reading the open documents...'));
    const res = await api('/api/owner/brief', { sandbox });
    write.disabled = false;
    if (!res.ok) { clear(out, el('p', { class: 'errors' }, res.data.message)); return; }
    const b = res.data;
    const c = b.counts;
    const lists = Object.entries(headings).filter(([key]) => b.lists[key].length).map(([key, title]) => [
      el('h3', {}, title),
      el('ul', { class: 'plain' }, b.lists[key].map((i) => el('li', {}, el('strong', {}, `${i.document}: `), i.line, ' ',
        statusBadge(i.status), i.overdue ? [' ', badge('Overdue', 'bad')] : null))),
      b.more[key] ? el('p', { class: 'muted' }, `and ${b.more[key]} more`) : null]);
    clear(out, b.demo_mode ? demoNote(b.demo_reason) : badge('Lines written by Muse Spark, lists sorted by the rules', 'ok'),
      el('div', { class: 'row' }, badge(`${c.open} open`, 'info'), badge(`${c.returned} returned`, c.returned ? 'warn' : 'info'),
        badge(`${c.overdue} overdue`, c.overdue ? 'bad' : 'info'), badge(`${c.accepted} accepted`, 'ok')),
      Object.keys(b.by_role).length ? el('p', { class: 'muted' },
        'Waiting by role: ' + Object.entries(b.by_role).map(([role, n]) => `${role} ${n}`).join(', ') + '.') : null,
      lists.length ? lists.flat() : el('p', {}, 'Nothing is waiting. Enjoy your coffee.'));
  }) }, 'Write my morning brief');
  return el('section', {}, el('h2', {}, 'Morning brief'),
    el('p', { class: 'muted' }, 'Open documents in three short lists. It is about documents and roles, never about people. ' +
      'To sign, use the top role\'s own link.'), el('div', { class: 'row' }, write), out);
}

// The handoff form is data: Muse proposes it, the rules validate it, the owner accepts it.
function handoffFormSection() {
  const body = el('div');
  const status = el('p', { class: 'muted', role: 'status' });
  const preview = el('div');
  const label = (schema, key) => schema.fields.find((f) => f.key === key)?.label || key;

  async function showCurrent() {
    const res = await api('/api/handoff-schema', { sandbox });
    clear(status, `In use: ${res.data.schema.title} (${res.data.schema.fields.map((f) => f.label).join(', ')}).`);
    return res.data.standard;
  }

  function accept(schema) {
    return guard(async () => {
      const res = await api('/api/handoff-schema', { method: 'POST', sandbox, body: { schema } });
      clear(preview, res.ok ? el('p', { role: 'status' }, badge('Saved', 'ok'), ' Everyone now sends this form.')
        : el('div', { class: 'errors', role: 'alert' }, (res.data.errors || [res.data.message]).join(' ')));
      if (res.ok) await showCurrent();
    });
  }

  function show(proposal, standard) {
    const schema = JSON.parse(JSON.stringify(proposal.schema));
    const thresholds = schema.rules.filter((r) => r.kind === 'min_margin' || r.kind === 'escalate_over').map((r) => {
      const input = el('input', { id: `th-${r.kind}`, type: 'number', min: '1', placeholder: r.kind === 'min_margin' ? 'company default 12' : 'company default 50000',
        'aria-label': r.kind === 'min_margin' ? 'Margin floor in percent' : 'Approval limit in USD',
        value: r.percent ?? r.usd ?? '', onchange: (e) => {
          const n = e.target.value === '' ? null : Number(e.target.value);
          if (r.kind === 'min_margin') r.percent = n; else r.usd = n;
        } });
      return el('div', {}, el('label', { for: input.id }, r.kind === 'min_margin' ? 'Margin floor (percent)'
        : `Above this ${label(schema, r.field)}, the top role also approves (USD)`), input);
    });
    const words = schema.rules.filter((r) => r.kind === 'not_below' || r.kind === 'date_not_past').map((r) => el('li', {},
      r.kind === 'not_below' ? `${label(schema, r.field)} must not be below ${label(schema, r.other)}`
        : `${label(schema, r.field)} must not be in the past`));
    clear(preview,
      proposal.demo_mode ? demoNote(proposal.demo_reason) : badge('Designed by Muse Spark', 'ok'),
      proposal.source === 'template' ? el('p', { class: 'muted' }, 'This is a standard form (Template).') : null,
      el('h3', {}, schema.title),
      el('ul', { class: 'plain' }, schema.fields.map((f) => el('li', {},
        `${f.label}: ${f.type}${f.required ? ', required' : ''}${f.options.length ? ` (${f.options.join(', ')})` : ''}`))),
      words.length ? el('ul', { class: 'plain' }, words) : null, ...thresholds,
      el('p', { class: 'muted' }, 'The rules apply these numbers, never the model. Leave a number empty to use the company default.'),
      el('div', { class: 'row' },
        el('button', { class: 'primary', onclick: accept(schema) }, 'Use this form'),
        el('button', { onclick: accept(standard[(state.answers?.industry || '').toLowerCase()] || standard.services) },
          'Use the standard form instead')));
  }

  const design = el('button', { onclick: guard(async () => {
    design.disabled = true;
    clear(preview, el('p', { class: 'progress', role: 'status' }, 'Muse Spark is designing the form (about 10 seconds)...'));
    const standard = await showCurrent();
    const res = await api('/api/handoff-schema/generate', { method: 'POST', sandbox, body: { answers: state.answers || {} } });
    design.disabled = false;
    if (!res.ok) { clear(preview, el('p', { class: 'errors' }, res.data.message)); return; }
    show(res.data, standard);
  }) }, 'Design the form for my company');
  const fromPhoto = photoPicker('form-photo', 'Or start from a photo of the paper form you use today', 'Design from this photo',
    async (image) => {
      clear(preview, el('p', { class: 'progress', role: 'status' }, 'Muse Spark is reading your paper form (about 10 seconds)...'));
      const standard = await showCurrent();
      const res = await api('/api/handoff-schema/from-photo', { method: 'POST', sandbox, body: { image, answers: state.answers || {} } });
      if (!res.ok) { clear(preview, el('p', { class: 'errors', role: 'alert' }, res.data.message)); return; }
      show(res.data, standard);
    });
  showCurrent();
  body.append(el('p', { class: 'muted' }, 'The handoff form is what people fill in when they pass work to another team. ' +
    'Until you choose one, the pallet-quote form is used.'), status, el('div', { class: 'row' }, design), fromPhoto, preview);
  return el('section', {}, el('h2', {}, '4. Handoff form'), body);
}

// Units of one company: a unit may only tighten its parent; the server refuses anything looser.
function levelsSection() {
  const body = el('div');
  const names = { margin_floor_pct: 'Margin floor (percent)', escalation_usd: 'Approval limit (USD)' };

  async function load() {
    const res = await api('/api/levels', { sandbox });
    if (!res.data.levels) {
      clear(body, el('p', { class: 'muted' }, 'This company has one level. Add a Group and a Subsidiary to set rules ' +
        'that a unit below can only tighten.'), el('button', { onclick: guard(async () => {
        await api('/api/levels/enable', { method: 'POST', sandbox });
        await load();
      }) }, 'Split into Group and Subsidiary'));
      return;
    }
    const message = el('div', { role: 'alert' });
    const rows = res.data.levels.map((unit) => {
      const inputs = Object.keys(names).map((rule) => el('input', { id: `lv-${unit.id}-${rule}`, type: 'number',
        value: unit[rule], 'aria-label': `${unit.name}: ${names[rule]}` }));
      const bans = Object.entries(res.data.skills).map(([id, label]) => el('input', { type: 'checkbox', id: `lv-${unit.id}-ban-${id}`,
        checked: (unit.banned_skills || []).includes(id), 'aria-label': `${unit.name}: ban ${label}` }));
      const save = guard(async () => {
        const values = Object.fromEntries(Object.keys(names).map((rule, i) => [rule, Number(inputs[i].value)]));
        values.banned_skills = Object.keys(res.data.skills).filter((id, i) => bans[i].checked);
        const put = await api(`/api/levels/${unit.id}?soft=1`, { method: 'PUT', sandbox, body: values });
        if (put.ok && put.data.saved !== false) { await load(); return; }
        clear(message, el('div', { class: 'errors' }, put.data.errors.map((e) => e.message).join(' ')));
      });
      const banList = el('details', {}, el('summary', {}, `${unit.name}: skills banned (${(unit.banned_skills || []).length})`),
        ...Object.entries(res.data.skills).map(([id, label], i) => el('label', { for: bans[i].id, class: 'check' }, bans[i], ` ${label}`)));
      return el('div', { class: 'row' }, el('strong', {}, unit.name),
        ...Object.keys(names).flatMap((rule, i) => [el('label', { for: inputs[i].id }, names[rule]), inputs[i]]),
        el('button', { onclick: save }, 'Save'), banList);
    });
    const eff = res.data.effective;
    // The refusal is the point of Levels, so a judge can see it in one click: the lowest unit asks for a margin floor
    // below the one in force, and code (not a model) refuses it and names the unit that set the rule.
    const child = res.data.levels[res.data.levels.length - 1];
    const tryLoosen = el('button', { onclick: guard(async () => {
      const put = await api(`/api/levels/${child.id}?soft=1`, { method: 'PUT', sandbox, body: {
        margin_floor_pct: eff.margin_floor_pct.value - 5, escalation_usd: child.escalation_usd, banned_skills: child.banned_skills || [] } });
      clear(message, put.data.saved === false
        ? el('div', { class: 'errors' }, el('strong', {}, 'Refused by code, no model asked: '), put.data.errors.map((e) => e.message).join(' '))
        : el('p', { class: 'muted' }, 'Saved: no rule above it was loosened.'));
    }) }, `Try: ${child.name} lowers the margin floor`);
    clear(body, el('p', { class: 'muted' }, 'A unit below may only tighten the rules above it. ', tryLoosen), ...rows, message, el('h3', {}, 'Rules in force'),
      el('ul', { class: 'plain' }, Object.keys(names).map((rule) => el('li', {},
        `${names[rule]}: ${eff[rule].value.toLocaleString('en-US')}, set by ${eff[rule].set_by}`)),
        ...Object.entries(res.data.bans).map(([id, by]) => el('li', {}, `Skill banned: ${res.data.skills[id]}, set by ${by}`))));
  }
  guard(load)();
  return el('section', {}, el('h2', {}, '5. Levels'), body);
}

if (sandbox) {
  guard(async () => {
    const res = await api('/api/company', { sandbox });
    if (res.data.expired) { startAgain(); return; }
    if (res.data.company) {
      state.chart = { ...res.data.company, errors: [], demo_mode: false, source: 'saved' };
      state.accepted = true;
      showAssistants();
    } else { state.answers = (await api('/api/survey/demo')).data.answers; showSurvey(); }
  })();
} else startAgain();
