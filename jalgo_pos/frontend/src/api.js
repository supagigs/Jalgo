// Thin wrapper over Frappe's /api/method. Errors come back as readable messages.
export async function call(method, args = {}, { post = false, ns = 'api' } = {}) {
  const url = `/api/method/jalgo_pos.${ns}.${method}`
  const opts = { headers: { Accept: 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token || '' }, credentials: 'same-origin' }
  let res
  try {
  if (post) {
    res = await fetch(url, { ...opts, method: 'POST', headers: { ...opts.headers, 'Content-Type': 'application/json' }, body: JSON.stringify(args) })
  } else {
    const q = new URLSearchParams(Object.entries(args).map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : v]))
    res = await fetch(`${url}?${q}`, opts)
  }
  } catch (e) { const err = new Error('No connection to ERPNext'); err.offline = true; throw err }
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.exc_type) {
    let msg = data._server_messages ? JSON.parse(JSON.parse(data._server_messages)[0]).message : (data.message || data.exc_type || res.statusText)
    const err = new Error(String(msg).replace(/<[^>]+>/g, ''))
    err.status = res.status
    throw err
  }
  return data.message
}
