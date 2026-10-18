/* Exchange the launcher fragment for an HttpOnly session before loading data. */
window.mnemosLocalAccess = (async () => {
  if (!location.hash.startsWith('#local-access=')) return;
  const values = new URLSearchParams(location.hash.slice(1));
  const key = values.get('local-access');
  const route = values.get('route') || '';
  history.replaceState(null, '', location.pathname + (/^[a-z0-9/_-]*$/.test(route) && route ? '#' + route : ''));
  const response = await fetch('/api/local-login', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key})
  });
  if (!response.ok) throw new Error('Local access expired. Open Mnemos from its launcher again.');
})();
