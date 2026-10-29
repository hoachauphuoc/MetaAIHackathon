// Tiny DOM helpers. Text always goes in through textContent, never as HTML.
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, '');
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node, ...children) {
  node.replaceChildren(...children.flat().filter((c) => c != null));
  return node;
}

export class Expired extends Error {}

export async function api(path, { method = 'GET', body, sandbox } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (sandbox) headers['X-Sandbox'] = sandbox;
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (res.status === 410) throw new Expired(data.message || 'This sandbox has ended.');
  return { status: res.status, ok: res.ok, data };
}

// POST and read a server-sent-event answer: onEvent(name, data) runs as each event really arrives.
// Returns the data of the "done" event, or { error } for an "error" event.
export async function streamEvents(path, { body, sandbox, onEvent }) {
  const headers = { 'Content-Type': 'application/json' };
  if (sandbox) headers['X-Sandbox'] = sandbox;
  const res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body) });
  if (res.status === 410) throw new Expired('This sandbox has ended.');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', last = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const [eventLine, dataLine] = buffer.slice(0, end).split('\n');
      buffer = buffer.slice(end + 2);
      const name = eventLine.slice(7);
      const data = JSON.parse(dataLine.slice(6));
      onEvent?.(name, data);
      if (name === 'done') last = data;
      if (name === 'error') last = { error: data.message };
    }
  }
  return last;
}

export function badge(text, kind = 'info') {
  return el('span', { class: `badge badge-${kind}` }, text);
}

export const STATUS_LABEL = {
  clear: ['Clear', 'ok'],
  needs_attention: ['Needs attention', 'warn'],
  needs_human_check: ['A person must check this', 'warn'],
  blocked: ['Blocked', 'bad'],
};

export function statusBadge(status) {
  const [text, kind] = STATUS_LABEL[status] || [status, 'info'];
  return badge(text, kind);
}

export function demoNote(reason) {
  return el('p', { class: 'demo-note', role: 'status' },
    'Demo mode', reason ? `: ${reason}` : '', '. Muse did not write this part.');
}
