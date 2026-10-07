/*
 * Auth gate. Two layers:
 *  1. Instant: no local login flag -> straight to the login page before anything paints.
 *  2. Real: ask the server whether the session cookie is still valid; if not, clear the
 *     local flag and go to login. (The API endpoints enforce login themselves too.)
 * Must load AFTER store.js and BEFORE any other page script, synchronously (no defer).
 */
(function () {
  if (!Store.isLoggedIn()) {
    window.location.replace('login.html');
    return;
  }
  var isDevPort = ['localhost', '127.0.0.1'].indexOf(location.hostname) >= 0 && location.port && location.port !== '8000';
  var base = isDevPort ? 'http://localhost:8000' : '';
  fetch(base + '/api/auth/me', { credentials: 'include' }).then(function (r) {
    if (r.status === 401) { Store.clearSession(); window.location.replace('login.html?expired=1'); return null; }
    return r.ok ? r.json() : null;
  }).then(function (u) {
    if (!u) return;
    var s = Store.getSession() || {};
    s.loggedIn = true; s.email = u.email; s.name = u.full_name;
    Store.setSession(s);
  }).catch(function () { /* server waking up or offline: keep the page usable */ });
})();
