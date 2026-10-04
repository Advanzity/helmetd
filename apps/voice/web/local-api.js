// Recover the same-origin control token after the local service restarts.
let token = document.querySelector('meta[name="helmetd-token"]').content;
let refreshing;
export async function localFetch(path, options = {}) {
  if (!path.startsWith('/api/')) throw new Error('Local API path required');
  const attempted = token;
  const send = () => fetch(path, {...options,
    headers: {...options.headers, 'X-Helmetd': token}});
  let response = await send();
  if (response.status !== 403) return response;
  if (token === attempted) {
    refreshing ??= (async () => {
      const page = await fetch('/', {cache: 'no-store', signal: AbortSignal.timeout(5000)});
      if (!page.ok) throw new Error('Helmet service unavailable');
      const html = new DOMParser().parseFromString(await page.text(), 'text/html');
      const next = html.querySelector('meta[name="helmetd-token"]')?.content;
      if (!next) throw new Error('Reload the helmet console to reconnect');
      token = next;
    })().finally(() => { refreshing = null; });
    await refreshing;
  }
  // Authorization rejected the first request before any action executed.
  return send();
}
