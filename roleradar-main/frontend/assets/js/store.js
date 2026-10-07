/*
 * RoleRadar localStorage store — single source of truth for every mock/client-only
 * concept the backend has no table for (auth, saved jobs, applications, progress,
 * profile, theme). Every key is namespaced "roleradar_*".
 *
 * NOTE: this is not real security or real persistence across devices — it's a
 * browser-local mock standing in for backend features (users, saved_jobs,
 * applications tables) that don't exist in the database yet.
 */
const Store = {
  KEYS: {
    session: 'roleradar_session',
    profile: 'roleradar_profile',
    savedJobs: 'roleradar_saved_jobs',
    applications: 'roleradar_applications',
    progress: 'roleradar_progress',
    resumeResult: 'roleradar_resume_result',
    theme: 'roleradar_theme'
  },

  _get(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  },
  _set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* ignore */ }
  },

  // Session
  getSession() { return this._get(this.KEYS.session, null); },
  setSession(session) { this._set(this.KEYS.session, session); },
  clearSession() { localStorage.removeItem(this.KEYS.session); },
  isLoggedIn() { const s = this.getSession(); return !!(s && s.loggedIn); },

  // Profile
  getProfile() {
    return this._get(this.KEYS.profile, {
      fullName: '',
      email: '',
      location: '',
      targetRole: '',
      about: '',
      avatarInitials: '?'
    });
  },
  setProfile(profile) { this._set(this.KEYS.profile, profile); },

  // Saved jobs
  getSavedJobs() { return this._get(this.KEYS.savedJobs, []); },
  isJobSaved(jobId) { return this.getSavedJobs().some(j => String(j.id) === String(jobId)); },
  toggleSavedJob(job) {
    const list = this.getSavedJobs();
    const idx = list.findIndex(j => String(j.id) === String(job.id));
    if (idx >= 0) { list.splice(idx, 1); this._set(this.KEYS.savedJobs, list); return false; }
    list.unshift(job);
    this._set(this.KEYS.savedJobs, list);
    return true;
  },

  // Applications
  getApplications() { return this._get(this.KEYS.applications, []); },
  addApplication(job, status) {
    const list = this.getApplications();
    const existing = list.find(a => String(a.job.id) === String(job.id));
    if (existing) { existing.appliedDate = new Date().toISOString(); this._set(this.KEYS.applications, list); return; }
    list.unshift({
      id: 'app_' + job.id + '_' + Date.now(),
      job,
      status: status || 'Applied',
      appliedDate: new Date().toISOString()
    });
    this._set(this.KEYS.applications, list);
  },
  updateApplicationStatus(appId, status) {
    const list = this.getApplications();
    const entry = list.find(a => a.id === appId);
    if (entry) { entry.status = status; this._set(this.KEYS.applications, list); }
  },
  removeApplication(appId) {
    const list = this.getApplications().filter(a => a.id !== appId);
    this._set(this.KEYS.applications, list);
  },

  // Progress (dashboard tiles / ring). The checklist itself is derived from real
  // signals (resume result, questions practiced, profile fields) — see dashboard.js —
  // this only tracks the two raw counters nothing else can be computed from.
  getProgress() {
    return this._get(this.KEYS.progress, {
      questionsPracticed: 0,
      resumeCompleteness: 0
    });
  },
  setProgress(p) { this._set(this.KEYS.progress, p); },
  incrementQuestionsPracticed(n) {
    const p = this.getProgress();
    p.questionsPracticed += (n || 1);
    this.setProgress(p);
  },

  // Resume checker result (feeds Dashboard "Resume Match %")
  getResumeResult() { return this._get(this.KEYS.resumeResult, null); },
  setResumeResult(result) {
    this._set(this.KEYS.resumeResult, result);
    const p = this.getProgress();
    p.resumeCompleteness = Math.round(result.overallScore || 0);
    this.setProgress(p);
  },

  // Theme
  getTheme() { return this._get(this.KEYS.theme, 'light'); },
  setTheme(theme) {
    this._set(this.KEYS.theme, theme);
    applyTheme(theme);
  },

  // Selected job handoff (sessionStorage, not localStorage — per-tab, short-lived)
  setSelectedJob(job) { sessionStorage.setItem('roleradar_selected_job', JSON.stringify(job)); },
  getSelectedJob() {
    try {
      const raw = sessionStorage.getItem('roleradar_selected_job');
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  },

  // Saved jobs, applications and profile live in this browser, so they must never carry over
  // from one account to another. Called right after a successful login.
  adoptAccount(user) {
    const owner = localStorage.getItem('roleradar_owner');
    if (owner !== user.email) {
      const theme = this.getTheme();
      this.clearAll();
      this._set(this.KEYS.theme, theme);
    }
    localStorage.setItem('roleradar_owner', user.email);
    const profile = this.getProfile();
    if (profile.email !== user.email) {
      profile.fullName = user.full_name || '';
      profile.email = user.email;
      profile.avatarInitials = (user.full_name || '').split(' ').filter(Boolean).map(p => p[0]).slice(0, 2).join('').toUpperCase() || '?';
      this.setProfile(profile);
    }
    this.setSession({ loggedIn: true, email: user.email, name: user.full_name, loginAt: new Date().toISOString() });
  },

  // Full wipe (Delete Account)
  clearAll() {
    Object.values(this.KEYS).forEach(k => localStorage.removeItem(k));
    sessionStorage.removeItem('roleradar_selected_job');
  }
};

// Dark theme was removed; "system" and "light" both render the same light theme. The
// function and the data-theme attribute stay so a saved 'system'/'dark' preference from
// before the removal doesn't break anything — it just displays as light like everything else.
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', 'light');
}

// Apply saved theme immediately (pre-paint, called inline before other scripts on app pages)
applyTheme(Store.getTheme());
