(async function () {
  const root = document.getElementById('job-details-root');
  const urlId = new URLSearchParams(window.location.search).get('id');
  const cached = Store.getSelectedJob();

  // Fast path: came from a row click, sessionStorage already has this exact job.
  // Otherwise (page refresh, deep link, bookmark) fall back to the real API by id.
  let job = (cached && (!urlId || String(cached.id) === urlId)) ? cached : null;
  if (!job && urlId) {
    try {
      job = await RoleRadarAPI.jobById(urlId);
      Store.setSelectedJob(job);
    } catch (e) { job = null; }
  }

  if (!job) {
    root.innerHTML = `<div class="empty-state"><i class="fas fa-triangle-exclamation"></i><p>No job selected.</p><a href="find-jobs.html" class="btn btn-primary" style="margin-top:12px;">Return to Find Jobs</a></div>`;
    return;
  }

  // extractSkills() and SKILL_KEYWORDS are shared from jobs-ui.js (loaded before this file).

  function fallbackDescription(job) {
    return `We are looking for a skilled ${job.title} to join ${job.company_name || 'our team'}` +
      `${job.location_city ? ' in ' + job.location_city + (job.location_state ? ', ' + job.location_state : '') : ''}. ` +
      `This is an opportunity to work on impactful projects, collaborate with a strong engineering team, and grow your career.`;
  }

  const meta = sourceMeta(job);
  const skills = extractSkills(job);
  const requirementsSection = extractRequirementsSection(job.description);

  root.innerHTML = `
    <div class="card detail-header">
      <div class="flex items-center gap-4">
        ${jobLogoHtml(job)}
        <div>
          <h1 class="detail-title">${job.title}</h1>
          <div class="job-meta flex items-center gap-3">
            <span style="color:${meta.color};font-weight:700;"><i class="${meta.icon}"></i> ${job.company_name || ''}</span>
            <span style="display:flex;gap:10px;align-items:center;">${jobMetaLine(job)}</span>
          </div>
        </div>
      </div>
      <div class="flex flex-col gap-2" style="align-items:flex-end;">
        <span class="salary" style="font-size:var(--fs-lg);">${formatSalary(job)}</span>
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" id="save-btn"><i class="${Store.isJobSaved(job.id) ? 'fas' : 'far'} fa-bookmark"></i> Save Job</button>
          <button class="btn btn-sm" id="apply-btn" style="background:${meta.color};color:#fff;"><i class="fas fa-arrow-up-right-from-square"></i> Apply on ${meta.label}</button>
        </div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" data-tab="overview">Overview</button>
      <button class="tab-btn" data-tab="requirements">Requirements</button>
      <button class="tab-btn" data-tab="company">Company</button>
      <button class="tab-btn" data-tab="similar">Similar Jobs</button>
    </div>

    <div class="card" style="padding:var(--space-5);">
      <div class="tab-panel active" data-panel="overview">
        <h4>Job Description</h4>
        ${job.description
          ? `<div class="job-text">${formatJobText(job.description)}</div>`
          : `<p class="text-muted">${escapeHtml(fallbackDescription(job))}</p>
             <h4>Key Responsibilities</h4>
             <ul class="text-muted">
               <li>Develop and maintain high-quality solutions for ${escapeHtml(job.title)} initiatives.</li>
               <li>Collaborate cross-functionally to solve complex technical problems.</li>
               <li>Contribute to architectural decisions and engineering best practices.</li>
               <li>Communicate findings and progress clearly to stakeholders.</li>
             </ul>`}
      </div>
      <div class="tab-panel" data-panel="requirements">
        ${requirementsSection
          ? `<div class="job-text">${formatJobText(requirementsSection)}</div>`
          : `<p class="text-muted">No explicit requirements section was found in this posting's description — here's what RoleRadar detected from the listing instead:</p>`}
        <h4>Key Skills Detected</h4>
        ${skills.length
          ? `<div class="skill-chip-row">${skills.map(s => `<span class="chip">${escapeHtml(s)}</span>`).join('')}</div>`
          : `<p class="text-muted">No specific skill keywords detected in this listing.</p>`}
      </div>
      <div class="tab-panel" data-panel="company">
        <div id="company-panel"><p class="text-muted">Loading company info…</p></div>
      </div>
      <div class="tab-panel" data-panel="similar">
        <div id="similar-jobs"><p class="text-muted">Loading similar jobs…</p></div>
      </div>
    </div>
  `;

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).classList.add('active');
    });
  });

  function requireLogin() {
    if (Store.isLoggedIn()) return true;
    window.location.href = 'login.html?next=' + encodeURIComponent(location.pathname + location.search);
    return false;
  }

  document.getElementById('save-btn').addEventListener('click', (e) => {
    if (!requireLogin()) return;
    const nowSaved = Store.toggleSavedJob(job);
    e.currentTarget.innerHTML = `<i class="${nowSaved ? 'fas' : 'far'} fa-bookmark"></i> Save Job`;
    showToast(nowSaved ? 'Job saved' : 'Removed from saved jobs');
  });

  document.getElementById('apply-btn').addEventListener('click', () => {
    if (!requireLogin()) return;
    Store.addApplication(job, 'Applied');
    if (job.source_url) window.open(job.source_url, '_blank');
    else showToast('No original posting link on this job — application logged anyway.');
    showToast('Added to My Applications');
  });

  // Company panel — real logo + whatever profile fields the DB actually has for this company.
  (async () => {
    const panel = document.getElementById('company-panel');
    if (job.company_id) {
      try {
        const company = await RoleRadarAPI.companyById(job.company_id);
        const domain = domainFromUrl(company.website) || COMPANY_DOMAIN_OVERRIDES[company.name];
        const logoSrc = company.logo_url || (domain ? `https://unavatar.io/${domain}?fallback=false` : null);
        const initial = (company.name || '?').trim().charAt(0).toUpperCase() || '?';
        const logoHtml = logoSrc
          ? `<div class="job-logo" style="background:#fff;border:1px solid var(--app-border);padding:8px;width:64px;height:64px;"><img id="company-logo-img" src="${logoSrc}" alt="${escapeHtml(company.name)}" style="width:100%;height:100%;object-fit:contain;"></div>`
          : `<div class="job-logo" style="background:${companyAvatarColor(company.name)};width:64px;height:64px;font-size:1.4rem;">${initial}</div>`;

        const rows = [
          company.industry ? ['fa-industry', company.industry] : null,
          (company.location_city || company.location_state) ? ['fa-location-dot', [company.location_city, company.location_state].filter(Boolean).join(', ')] : null,
          company.size ? ['fa-users', company.size + ' employees'] : null,
          company.phone ? ['fa-phone', company.phone] : null,
          company.hr_email ? ['fa-envelope', company.hr_email] : null,
        ].filter(Boolean);

        panel.innerHTML = `
          <div class="company-info-header">
            ${logoHtml}
            <div>
              <h4 style="margin:0;">${escapeHtml(company.name)}</h4>
              ${company.website ? `<a href="${company.website}" target="_blank" style="font-size:var(--fs-sm);">${escapeHtml(company.website)}</a>` : ''}
            </div>
          </div>
          ${rows.map(([icon, text]) => `<div class="company-info-row"><i class="fas ${icon}"></i> ${escapeHtml(text)}</div>`).join('')}
          ${company.linkedin_url ? `<div class="company-info-row"><i class="fab fa-linkedin"></i> <a href="${company.linkedin_url}" target="_blank">LinkedIn</a></div>` : ''}
          ${company.description ? `<p class="text-muted" style="margin-top:var(--space-3);">${escapeHtml(company.description)}</p>` : ''}
          ${company.website ? `<a class="btn btn-outline btn-sm" href="${company.website}" target="_blank" style="margin-top:var(--space-3);">Visit Website</a>` : ''}
        `;

        const logoImg = document.getElementById('company-logo-img');
        if (logoImg) {
          logoImg.addEventListener('error', () => {
            const fallback = document.createElement('div');
            fallback.className = 'job-logo';
            fallback.style.cssText = `background:${companyAvatarColor(company.name)};width:64px;height:64px;font-size:1.4rem;`;
            fallback.textContent = initial;
            logoImg.parentElement.replaceWith(fallback);
          }, { once: true });
        }
        return;
      } catch (e) { /* fall through to generic blurb */ }
    }
    panel.innerHTML = `<p class="text-muted">${escapeHtml(job.company_name || 'This company')} is hiring for multiple roles in the DFW tech market. Full company profile data isn't linked to this listing yet.</p>`;
  })();

  // Similar jobs panel — API stub always returns [], so fall back to client-side keyword match
  (async () => {
    const panel = document.getElementById('similar-jobs');
    let similar = [];
    try { similar = await RoleRadarAPI.similarJobs(job.id); } catch (e) { similar = []; }

    if (!similar.length) {
      try {
        const all = await RoleRadarAPI.jobs({ per_page: 100 });
        const firstWord = (job.title || '').split(' ')[0].toLowerCase();
        similar = all.filter(j => j.id !== job.id && (j.title || '').toLowerCase().includes(firstWord)).slice(0, 5);
      } catch (e) { similar = []; }
    }

    if (!similar.length) {
      panel.innerHTML = `<div class="empty-state"><i class="fas fa-briefcase"></i><p>No similar jobs found right now.</p></div>`;
      return;
    }
    await attachCompanyLogos(similar);
    const byId = {};
    similar.forEach(j => byId[j.id] = j);
    panel.innerHTML = similar.map(j => renderJobRow(j)).join('');
    wireJobRowActions(panel, byId);
  })();
})();
