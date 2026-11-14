// Small fetch wrapper: JSON in/out, CSRF header, typed errors.

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data || {};
  }
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const options = {
    method,
    headers: {
      'X-CSRFToken': csrfToken(),
      'Accept': 'application/json',
    },
    credentials: 'same-origin',
    signal,
  };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch { /* non-JSON */ }
  if (!response.ok) {
    throw new ApiError(data.error || response.statusText, response.status, data);
  }
  return data;
}
