/*
 * Injects the shared sidebar + topbar partials into every post-login page's
 * #sidebar-root / #topbar-root, highlights the active nav link, and wires
 * logout + topbar search + user identity display.
 *
 * Requires being served over http(s) (fetch of a relative partial fails under
 * bare file://) — see verification notes: run `python -m http.server` from frontend/.
 */
(async function initShell() {
  const sidebarRoot = document.getElementById('sidebar-root');
  const topbarRoot = document.getElementById('topbar-root');
  if (!sidebarRoot || !topbarRoot) return;

  // no-store: these partials get edited during active development and the dev
  // server (python -m http.server) sends no cache-control headers, so browsers
  // were serving a stale cached copy of the nav even after the file changed.
  const [sidebarHtml, topbarHtml] = await Promise.all([
    fetch('assets/partials/sidebar.html', { cache: 'no-store' }).then(r => r.text()),
    fetch('assets/partials/topbar.html', { cache: 'no-store' }).then(r => r.text())
  ]);

  sidebarRoot.innerHTML = sidebarHtml.replace('__RR_LOGO_SVG__', RR_LOGO_SVG);
  topbarRoot.innerHTML = topbarHtml;

  // Mobile navigation drawer (the sidebar slides in below 900px)
  const menuBtn = document.getElementById('menu-toggle');
  const overlay = document.createElement('div');
  overlay.className = 'nav-overlay';
  document.body.appendChild(overlay);
  const setNav = (open) => {
    document.body.classList.toggle('nav-open', open);
    if (menuBtn) {
      menuBtn.setAttribute('aria-expanded', String(open));
      menuBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    }
  };
  if (menuBtn) menuBtn.addEventListener('click', () => setNav(!document.body.classList.contains('nav-open')));
  overlay.addEventListener('click', () => setNav(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setNav(false); });
  window.matchMedia('(min-width: 901px)').addEventListener('change', (e) => { if (e.matches) setNav(false); });

  // Active link highlight
  const current = document.body.getAttribute('data-page');
  document.querySelectorAll('#sidebar-nav a').forEach(a => {
    if (a.getAttribute('data-page') === current) a.classList.add('active');
  });

  document.querySelectorAll('#sidebar-nav a').forEach(a => a.addEventListener('click', () => setNav(false)));

  // Logout
  document.getElementById('logout-link').addEventListener('click', async (e) => {
    e.preventDefault();
    try { await RoleRadarAPI.auth.logout(); } catch (err) { /* cookie expires on its own */ }
    Store.clearSession();
    window.location.href = 'index.html';
  });

  // Identity
  const session = Store.getSession();
  const profile = Store.getProfile();
  const name = (profile && profile.fullName) || (session && session.name) || 'Job Seeker';
  const initials = name.split(' ').filter(Boolean).map(p => p[0]).slice(0, 2).join('').toUpperCase() || 'JS';
  const nameEl = document.getElementById('topbar-name');
  const avatarEl = document.getElementById('topbar-avatar');
  if (nameEl) nameEl.textContent = name;
  if (avatarEl) avatarEl.textContent = initials;

  // Topbar search -> Find Jobs
  const searchInput = document.getElementById('topbar-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        window.location.href = 'find-jobs.html?q=' + encodeURIComponent(searchInput.value.trim());
      }
    });
  }

  document.dispatchEvent(new CustomEvent('shell:ready'));
})();
