(function () {
  const profile = Store.getProfile();
  const session = Store.getSession();
  if (!profile.email) profile.email = session.email || '';

  const fields = ['fullName', 'email', 'location', 'targetRole', 'about'];
  fields.forEach(f => { document.getElementById('p-' + f).value = profile[f] || ''; });
  document.getElementById('profile-name-display').textContent = profile.fullName;
  document.getElementById('profile-email-display').textContent = profile.email;
  document.getElementById('profile-avatar').textContent = profile.avatarInitials || 'RS';

  let editing = false;
  document.getElementById('edit-profile-btn').addEventListener('click', () => {
    editing = !editing;
    fields.forEach(f => document.getElementById('p-' + f).disabled = !editing);
    document.getElementById('save-profile-btn').style.display = editing ? 'inline-flex' : 'none';
    document.getElementById('edit-profile-btn').textContent = editing ? 'Cancel' : 'Edit Profile';
  });

  document.getElementById('profile-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const updated = {};
    fields.forEach(f => updated[f] = document.getElementById('p-' + f).value.trim());
    updated.avatarInitials = updated.fullName.split(' ').filter(Boolean).map(p => p[0]).slice(0, 2).join('').toUpperCase() || 'JS';
    Store.setProfile(updated);

    const s = Store.getSession();
    if (s) { s.name = updated.fullName; Store.setSession(s); }

    document.getElementById('profile-name-display').textContent = updated.fullName;
    document.getElementById('profile-email-display').textContent = updated.email;
    document.getElementById('profile-avatar').textContent = updated.avatarInitials;

    fields.forEach(f => document.getElementById('p-' + f).disabled = true);
    document.getElementById('save-profile-btn').style.display = 'none';
    document.getElementById('edit-profile-btn').textContent = 'Edit Profile';
    editing = false;
    showToast('Profile updated');
  });

  // Theme toggle
  const themeButtons = document.querySelectorAll('#theme-toggle button');
  function syncThemeButtons() {
    const current = Store.getTheme();
    themeButtons.forEach(b => b.classList.toggle('active', b.dataset.theme === current));
  }
  themeButtons.forEach(b => b.addEventListener('click', () => {
    Store.setTheme(b.dataset.theme);
    syncThemeButtons();
    showToast('Theme set to ' + b.dataset.theme);
  }));
  syncThemeButtons();

  document.getElementById('password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = document.getElementById('password-msg');
    const btn = document.getElementById('password-btn');
    const current = document.getElementById('p-current-password');
    const next = document.getElementById('p-new-password');
    msg.className = 'auth-msg';
    btn.disabled = true; btn.textContent = 'Updating…';
    const res = await RoleRadarAPI.auth.changePassword(current.value, next.value);
    btn.disabled = false; btn.textContent = 'Update Password';
    msg.textContent = res.ok ? 'Password updated.' : res.message;
    msg.className = 'auth-msg show ' + (res.ok ? 'ok' : 'error');
    if (res.ok) { current.value = ''; next.value = ''; }
  });

  document.getElementById('delete-account-btn').addEventListener('click', async () => {
    if (!confirm('This permanently deletes your RoleRadar account and clears your profile, saved jobs, and applications from this browser. This cannot be undone. Continue?')) return;
    const res = await RoleRadarAPI.auth.deleteAccount();
    if (!res.ok) { showToast(res.message); return; }
    Store.clearAll();
    localStorage.removeItem('roleradar_owner');
    window.location.href = 'index.html';
  });

  if (window.location.hash === '#settings') {
    document.getElementById('settings').scrollIntoView({ behavior: 'smooth' });
  }
})();
