// Masks personal data in the browser before text is sent to a model. Pattern-based only: it cannot
// recognise names, and /trust says so. Order matters: longer, more specific patterns first.
const LABELS = { client: 'CLIENT', secret: 'SECRET', iban: 'IBAN', email: 'EMAIL', card: 'CARD', ssn: 'SSN', id: 'ID_NUMBER', phone: 'PHONE' };

function luhn(digits) {
  let sum = 0;
  for (let i = 0; i < digits.length; i++) {
    let d = Number(digits[digits.length - 1 - i]);
    if (i % 2 === 1) { d *= 2; if (d > 9) d -= 9; }
    sum += d;
  }
  return sum % 10 === 0;
}

const digitsOf = (s) => s.replace(/\D/g, '');

const RULES = [
  // Credentials pasted with code: a private key block, a cloud key id, a vendor token, or name = value for a secret name.
  ['secret', /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g, () => true],
  ['secret', /\bAKIA[0-9A-Z]{16}\b/g, () => true],
  ['secret', /\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b/g, () => true],
  ['secret', /\b(?:api[_-]?key|secret|token|passw(?:or)?d)\b\s*[:=]\s*["']?[^\s"',;]{6,}/gi, () => true],
  ['iban', /\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b/g, () => true],
  ['email', /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/g, () => true],
  ['card', /\b(?:\d[ -]?){12,18}\d\b/g, (m) => {
    const d = digitsOf(m);
    return d.length >= 13 && d.length <= 19 && luhn(d);
  }],
  ['ssn', /\b\d{3}-\d{2}-\d{4}\b/g, () => true],
  ['id', /\b\d{12}\b/g, () => true],
  ['phone', /(?<![\w.])(?:\+|\(|0)[\d ().-]{7,18}\d/g, (m) => {
    const n = digitsOf(m).length;
    return n >= 9 && n <= 15;
  }],
];

// Client names are the one thing no pattern can find, so the person lists them. They are matched as whole words, in
// any case, and never leave the browser: only their placeholders are sent.
const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function maskPii(text, clientNames = []) {
  const items = [];
  const counts = {};
  let out = String(text);
  const names = clientNames.map((n) => n.trim()).filter((n) => n.length >= 2);
  const clientRules = names.length
    ? [['client', new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.map(escapeRegex).join('|')})(?![\\p{L}\\p{N}])`, 'giu'), () => true]]
    : [];
  for (const [type, pattern, accept] of [...clientRules, ...RULES]) {
    out = out.replace(pattern, (match) => {
      if (!accept(match)) return match;
      counts[type] = (counts[type] || 0) + 1;
      const placeholder = `[${LABELS[type]}_${counts[type]}]`;
      items.push({ type, original: match, placeholder });
      return placeholder;
    });
  }
  return { text: out, items };
}
