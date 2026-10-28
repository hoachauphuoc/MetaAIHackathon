// "What is stuck and where": the documents I sent that still wait for another team, and a reminder
// draft for each. Words come from the package's own fields, so nothing is invented and nothing is sent.
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

export function stuckRows(packages) {
  return packages.filter((p) => p.i_sent_it && p.state === 'sent')
    .sort((a, b) => Number(b.overdue) - Number(a.overdue) || (b.age_days ?? 0) - (a.age_days ?? 0));
}

export function stuckLine(p) {
  const title = p.values[p.schema.title_field] || p.schema.title;
  const where = p.stage > 0 ? `at ${p.to_title}, step ${p.stage + 1} of ${p.chain.length}` : `with ${p.to_title}`;
  const age = p.age_days == null ? '' : p.age_days === 0 ? ' since today' : ` for ${plural(p.age_days, 'day')}`;
  return `${title}: waiting ${where}${age}${p.taken ? ', taken by someone' : ', not taken yet'}${p.overdue ? ', overdue' : ''}.`;
}

// A draft only: the person reads it and sends it from their own mail or chat.
export function reminderText(p) {
  const title = p.values[p.schema.title_field] || p.schema.title;
  const sent = p.sent_on ? ` on ${p.sent_on}` : '';
  const due = p.due ? `, answer needed by ${p.due}` : '';
  return `Hello ${p.to_title} team,\n\nA small reminder: "${title}" from ${p.from_title}${sent} is still waiting for a decision${due}. ` +
    `${p.check_status === 'blocked' ? 'It was blocked by the rules, so it needs a return rather than an accept. ' : ''}` +
    'Could someone take it today?\n\nThank you.';
}
