// The invite token lives in the URL fragment, which browsers never send to the server, so access logs
// never record it. The old path form /join/<token> is rewritten once, client-side, into the fragment form.
export function readJoinToken(location, history) {
  if (location.hash.length > 1) return decodeURIComponent(location.hash.slice(1));
  const legacy = location.pathname.split('/').pop();
  if (legacy === 'join') return '';
  history.replaceState(null, '', `/join#${legacy}`);
  return decodeURIComponent(legacy);
}
