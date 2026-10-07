/* RoleRadar API layer — one thin wrapper per backend endpoint. */
// Hosted: the API serves this frontend, so requests are same-origin (empty base).
// Local dev servers on other ports (5500, 8080) talk to the API on localhost:8000.
const API_BASE = (['localhost', '127.0.0.1'].includes(location.hostname) && location.port && location.port !== '8000')
  ? 'http://localhost:8000' : '';

// A 401 from a protected endpoint means the session cookie is missing or expired.
function handleUnauthorized() {
  if (typeof Store !== 'undefined') Store.clearSession();
  if (!/login\.html$/.test(window.location.pathname)) window.location.replace('login.html?expired=1');
  throw new Error('Session expired');
}

async function apiGet(path) {
  const res = await fetch(API_BASE + path, { credentials: 'include' });
  if (res.status === 401) handleUnauthorized();
  if (!res.ok) throw new Error('GET ' + path + ' failed: ' + res.status);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body || {})
  });
  if (res.status === 401) handleUnauthorized();
  if (!res.ok) throw new Error('POST ' + path + ' failed: ' + res.status);
  return res.json();
}

async function apiPostForm(path, formData) {
  const res = await fetch(API_BASE + path, { method: 'POST', body: formData, credentials: 'include' });
  if (res.status === 401) handleUnauthorized();
  if (!res.ok) throw new Error('POST ' + path + ' failed: ' + res.status);
  return res.json();
}

// Account calls return {ok, status, code, message, data} instead of throwing, so the
// login pages can show the server's own message (wrong password, unverified email, ...).
async function apiAuth(path, body) {
  const res = await fetch(API_BASE + '/api/auth' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  let data = {};
  try { data = await res.json(); } catch (e) { /* empty body */ }
  const d = data.detail;
  const message = typeof d === 'string' ? d
    : (d && d.message) || (Array.isArray(d) && d[0] && d[0].msg) || data.message
    || 'Something went wrong. Please try again.';
  return { ok: res.ok, status: res.status, code: d && d.code, message, data };
}

const RoleRadarAPI = {
  auth: {
    signup: (full_name, email, password) => apiAuth('/signup', { full_name, email, password }),
    login: (email, password) => apiAuth('/login', { email, password }),
    logout: () => apiAuth('/logout', {}),
    me: () => apiAuth('/me'),
    verify: (token) => apiAuth('/verify', { token }),
    resend: (email) => apiAuth('/resend', { email }),
    forgot: (email) => apiAuth('/forgot', { email }),
    reset: (token, password) => apiAuth('/reset', { token, password }),
    changePassword: (current_password, new_password) => apiAuth('/change-password', { current_password, new_password }),
    deleteAccount: () => apiAuth('/delete-account', {})
  },
  health: () => apiGet('/health'),
  stats: () => apiGet('/api/stats'),

  companies: (params) => apiGet('/api/companies' + (params ? '?' + new URLSearchParams(params) : '')),
  companyById: (id) => apiGet('/api/companies/' + id),

  jobs: (params) => apiGet('/api/jobs' + (params ? '?' + new URLSearchParams(params) : '')),
  jobsSimple: () => apiGet('/api/jobs/simple'),
  jobById: (jobId) => apiGet('/api/jobs/' + jobId),
  similarJobs: (jobId) => apiGet('/api/jobs/' + jobId + '/similar').catch(() => []),
  searchJobsLive: (query, location) => apiPost('/api/jobs/search-live', { query, location }),

  interviewStart: (payload) => apiPost('/api/interview/start', payload),
  interviewRespond: (sessionId, payload) => apiPost('/api/interview/' + sessionId + '/respond', payload),
  interviewEnd: (sessionId) => apiPost('/api/interview/' + sessionId + '/end', {}),

  skillsAnalyze: (payload) => apiPost('/api/skills/analyze', payload),
  // mode: {jobId} for a specific job listing, {role} for a general role category, or {} for a general check.
  skillsAnalyzeFile: (file, { jobId, role } = {}) => {
    const fd = new FormData();
    fd.append('file', file);
    if (jobId) fd.append('job_id', jobId);
    if (role) fd.append('role', role);
    return apiPostForm('/api/skills/analyze-file', fd);
  },
  resumeParse: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return apiPostForm('/api/resume/parse', fd);
  }
};

function showToast(message) {
  let root = document.getElementById('toast-root');
  if (!root) {
    root = document.createElement('div');
    root.id = 'toast-root';
    document.body.appendChild(root);
  }
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

const RR_LOGO_SVG = `<svg viewBox="0 0 40 40" width="28" height="28" fill="none" aria-hidden="true">
  <circle cx="20" cy="20" r="17" stroke="currentColor" stroke-width="2.5" opacity="0.35"/>
  <circle cx="20" cy="20" r="11" stroke="currentColor" stroke-width="2" opacity="0.5"/>
  <line x1="20" y1="20" x2="34" y2="8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="20" cy="20" r="3" fill="currentColor"/>
  <circle cx="30" cy="12" r="2.5" fill="currentColor"/>
</svg>`;
