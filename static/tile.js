// The "timed by hand" tile on the landing page: numbers come from data/timed_runs.json through /api/timed-runs.
import { api, el } from '/static/ui.js';

export function duration(seconds) {
  if (seconds < 90) return `${Math.round(seconds * 10) / 10} s`;
  return `${Math.round(seconds / 6) / 10} min`;
}

export function row(run) {
  const saving = run.saved_seconds == null
    ? 'by hand: not timed yet'
    : `by hand ${duration(run.hand_seconds)}, saved ${duration(run.saved_seconds)} (${run.saved_percent}%), timed by ${run.timed_by}`;
  return el('li', {}, el('strong', {}, `${run.task}: `), `app ${duration(run.app_seconds)}; ${saving}`,
    el('span', { class: 'muted' }, ` (${run.source}, ${run.date})`));
}

export async function timeTile() {
  const { data } = await api('/api/timed-runs');
  const runs = data.runs || [];
  if (!runs.length) return null;
  return el('section', { class: 'card' }, el('h3', {}, 'Timed runs'),
    el('p', { class: 'muted' }, 'Real stopwatch runs, same job. One person, small sample; a row without a by-hand time was not compared.'),
    el('ul', {}, runs.map(row)));
}
