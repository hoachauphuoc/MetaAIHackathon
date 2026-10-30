// Move a handoff in and out as JSON or CSV so another system can feed or read the inbox.
// Import only fills the form: the person checks it, the rules check it again, and a person sends it.
const MAX_BYTES = 100000;

function parseCsv(text) {
  const rows = [[]];
  let cell = '', quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i += 1; } else if (c === '"') quoted = false; else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { rows.at(-1).push(cell); cell = ''; } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i += 1;
      rows.at(-1).push(cell); cell = ''; rows.push([]);
    } else cell += c;
  }
  rows.at(-1).push(cell);
  return rows.filter((r) => r.some((v) => v.trim() !== ''));
}

// Returns the values of the first record, keeping only the fields the company's form has.
export function readRecord(text, schema) {
  if (text.length > MAX_BYTES) throw new Error('That file is too large to read here.');
  let record;
  if (text.trimStart().startsWith('{') || text.trimStart().startsWith('[')) {
    const data = JSON.parse(text);
    record = Array.isArray(data) ? data[0] : data.values || data;
  } else {
    const [head, first] = parseCsv(text);
    if (!first) throw new Error('The CSV needs a header row and one data row.');
    record = Object.fromEntries(head.map((h, i) => [h.trim(), first[i] ?? '']));
  }
  if (!record || typeof record !== 'object') throw new Error('No record found in the file.');
  // Notes are left out on purpose: free text must pass the masking step the person confirms before sending.
  const keys = schema.fields.map((f) => f.key);
  const values = {};
  for (const key of keys) if (record[key] !== undefined && record[key] !== null) values[key] = String(record[key]);
  if (!Object.keys(values).length) throw new Error(`No field matches this form. Expected: ${keys.join(', ')}.`);
  return values;
}

// A spreadsheet runs a cell that starts with = + - or @, so those get a leading quote mark.
const safe = (v) => (/^[=+\-@]/.test(String(v)) ? `'${v}` : String(v));
const cell = (v) => `"${safe(v ?? '').replaceAll('"', '""')}"`;

export function toCsv(packages, schema) {
  const keys = [...schema.fields.map((f) => f.key), 'notes'];
  const lines = [[...keys, 'status', 'state', 'due'].map(cell).join(',')];
  for (const p of packages) {
    lines.push([...keys.map((k) => p.values[k]), p.check_status, p.state, p.due].map(cell).join(','));
  }
  return lines.join('\r\n');
}

export function toJson(packages) {
  return JSON.stringify(packages.map((p) => ({ values: p.values, status: p.check_status, state: p.state, due: p.due })), null, 2);
}

// The connector export: only handoffs every approver accepted and that were not blocked, with the form's fields in
// the form's order and no free-text notes, so a sheet or another system gets a fixed, already-decided record.
export function approvedOnly(packages) {
  return packages.filter((p) => p.state === 'accepted' && p.check_status !== 'blocked');
}

export function toApprovedCsv(packages, schema) {
  const keys = schema.fields.map((f) => f.key);
  const lines = [['handoff_id', ...keys, 'approved_by', 'sent_on'].map(cell).join(',')];
  for (const p of approvedOnly(packages)) {
    lines.push([p.id, ...keys.map((k) => p.values[k]), p.chain_titles.join(' > '), p.sent_on].map(cell).join(','));
  }
  return lines.join('\r\n');
}

export function toApprovedJson(packages, schema) {
  const keys = schema.fields.map((f) => f.key);
  return JSON.stringify(approvedOnly(packages).map((p) => ({
    handoff_id: p.id, values: Object.fromEntries(keys.map((k) => [k, p.values[k] ?? null])),
    approved_by: p.chain_titles, sent_on: p.sent_on })), null, 2);
}

// An email draft for a handoff every approver accepted: the form's own fields and the approval chain, never the
// free-text notes and nothing a model wrote. The person presses Send in their own mail app; nothing is sent from here.
// A long mailto link is cut off by some mail apps, so past the limit there is no link, only the text to copy.
const MAILTO_LIMIT = 1800;

export function approvedMailDraft(p, schema) {
  if (!approvedOnly([p]).length) return null;
  const title = p.values[schema.title_field] || schema.title;
  const text = [`Approved: ${title}`, '',
    ...schema.fields.map((f) => `${f.label}: ${p.values[f.key] ?? ''}`), '',
    `Approved by: ${p.chain_titles.join(', then ')}`, `Sent on: ${p.sent_on}`].join('\r\n');
  const href = `mailto:?subject=${encodeURIComponent(`Approved: ${title}`)}&body=${encodeURIComponent(text)}`;
  return { text, href: href.length <= MAILTO_LIMIT ? href : null };
}

// The same for a finished order: only the numbers code computed and the steps a person approved, never what a model
// wrote, so the email cannot carry a model's guess. The .ics from the schedule step travels as its own file.
export function approvedOrderDraft(steps) {
  const tools = Object.assign({}, ...steps.map((s) => s.result.tool_result));
  const lines = [`Approved order: ${tools.title || 'order'}`, ''];
  if (tools.price !== undefined) lines.push(`Price: USD ${tools.price}`, `Cost: USD ${tools.cost}`);
  if (tools.margin_pct !== undefined) lines.push(`Margin: ${tools.margin_pct}% (computed by code)`);
  if (tools.date) lines.push(`Delivery: ${tools.date}`);
  lines.push('', `Approved steps: ${steps.map((s) => `${s.title} (${s.role})`).join(', then ')}`);
  const text = lines.join('\r\n');
  const href = `mailto:?subject=${encodeURIComponent(lines[0])}&body=${encodeURIComponent(text)}`;
  return { text, href: href.length <= MAILTO_LIMIT ? href : null, ics: tools.ics || null };
}

export function download(name, text, type) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([text], { type }));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}
