(async function () {
  const session = Store.getSession();
  const profile = Store.getProfile();
  const firstName = ((profile.fullName || session.name || 'there').split(' ')[0]);
  document.getElementById('welcome-heading').textContent = `Welcome back, ${firstName}! 👋`;

  // Stat tiles
  document.getElementById('stat-applications').textContent = Store.getApplications().length;
  document.getElementById('stat-interview-qs').textContent = Store.getProgress().questionsPracticed;

  const resumeResult = Store.getResumeResult();
  document.getElementById('stat-resume-match').textContent = resumeResult ? Math.round(resumeResult.overallScore) + '%' : '--';

  try {
    const stats = await RoleRadarAPI.stats();
    document.getElementById('stat-jobs').textContent = stats.total_jobs ?? '--';
  } catch (e) {
    document.getElementById('stat-jobs').textContent = '--';
  }

  // Recommended jobs
  const recEl = document.getElementById('recommended-jobs');
  try {
    const jobs = await RoleRadarAPI.jobs({ per_page: 20 });
    const picks = jobs.slice(0, 6);
    if (!picks.length) {
      recEl.innerHTML = `<div class="empty-state"><i class="fas fa-briefcase"></i><p>No jobs found yet — try running the crawler.</p></div>`;
    } else {
      await attachCompanyLogos(picks);
      const byId = {};
      picks.forEach(j => byId[j.id] = j);
      recEl.innerHTML = picks.map(j => renderJobRow(j)).join('');
      wireJobRowActions(recEl, byId);
    }
  } catch (e) {
    recEl.innerHTML = `<div class="empty-state"><i class="fas fa-triangle-exclamation"></i><p>Error loading jobs. Is the backend running?</p></div>`;
  }

  // Progress ring + checklist — each item is tied to a real, checkable signal (not static filler numbers).
  const progress = Store.getProgress();
  const hasResume = progress.resumeCompleteness > 0;
  const hasPracticed = progress.questionsPracticed >= 3;
  const hasAbout = (profile.about || '').trim().length > 20;
  const hasCertMention = /certif/i.test(profile.about || '');
  const hasTargetRoleMatch = !!(profile.targetRole || '').trim() && hasResume;

  const checklistItems = [
    { label: 'Resume Completeness', done: hasResume, hint: 'Run the Resume Checker' },
    { label: 'Technical Skills', done: hasPracticed, hint: 'Practice 3+ interview questions' },
    { label: 'Projects & Experience', done: hasAbout, hint: 'Fill out your About section in Profile' },
    { label: 'Certifications', done: hasCertMention, hint: 'Mention certifications in your Profile' },
    { label: 'Target Role Match', done: hasTargetRoleMatch, hint: 'Set a Target Role and run Resume Checker' }
  ];

  const doneCount = checklistItems.filter(i => i.done).length;
  const overallPct = Math.round((doneCount / checklistItems.length) * 100);
  const circumference = 2 * Math.PI * 45;
  document.getElementById('progress-ring-fg').style.strokeDasharray = circumference;
  document.getElementById('progress-ring-fg').style.strokeDashoffset = circumference - (circumference * overallPct / 100);
  document.getElementById('progress-ring-value').textContent = overallPct + '%';

  document.getElementById('progress-checklist').innerHTML = checklistItems.map(i =>
    `<li title="${i.done ? '' : i.hint}"><i class="fas ${i.done ? 'fa-circle-check done' : 'fa-circle-xmark pending'}"></i> ${i.label}</li>`
  ).join('');
})();
