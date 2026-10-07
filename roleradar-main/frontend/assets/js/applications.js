(function () {
  const STATUSES = ['Applied', 'Interviewing', 'Offer', 'Rejected'];
  let activeFilter = 'All';

  const pillsEl = document.getElementById('status-pills');
  const listEl = document.getElementById('applications-list');

  function badgeClass(status) {
    return { Applied: 'badge-applied', Interviewing: 'badge-interviewing', Offer: 'badge-offer', Rejected: 'badge-rejected' }[status] || 'badge-applied';
  }

  function renderPills() {
    const apps = Store.getApplications();
    const counts = { All: apps.length };
    STATUSES.forEach(s => counts[s] = apps.filter(a => a.status === s).length);
    pillsEl.innerHTML = ['All', ...STATUSES].map(s =>
      `<button class="pill ${activeFilter === s ? 'active' : ''}" data-status="${s}">${s} (${counts[s]})</button>`
    ).join('');
    pillsEl.querySelectorAll('.pill').forEach(p => p.addEventListener('click', () => {
      activeFilter = p.dataset.status;
      render();
    }));
  }

  function render() {
    renderPills();
    const apps = Store.getApplications().filter(a => activeFilter === 'All' || a.status === activeFilter);

    if (!apps.length) {
      listEl.innerHTML = `<div class="empty-state"><i class="fas fa-paper-plane"></i><p>No applications yet. Apply to a job from Find Jobs or Job Details to see it tracked here.</p></div>`;
      return;
    }

    listEl.innerHTML = apps.map(a => {
      const job = a.job;
      const meta = sourceMeta(job);
      return `
      <div class="app-row" data-app-id="${a.id}">
        ${jobLogoHtml(job)}
        <div class="job-info">
          <p class="job-title">${job.title}</p>
          <div class="job-meta"><span style="color:${meta.color};font-weight:600;">${job.company_name || ''}</span> ${jobMetaLine(job)}</div>
        </div>
        <div class="applied-date">Applied ${new Date(a.appliedDate).toLocaleDateString()}</div>
        <span class="badge ${badgeClass(a.status)}">${a.status}</span>
        <div style="position:relative;">
          <button class="overflow-btn" data-action="menu"><i class="fas fa-ellipsis-vertical"></i></button>
          <div class="overflow-menu">
            ${STATUSES.map(s => `<button data-action="status" data-status="${s}">Mark as ${s}</button>`).join('')}
            <button data-action="view">View Job</button>
            <button data-action="remove" style="color:var(--app-danger);">Remove</button>
          </div>
        </div>
      </div>`;
    }).join('');
  }

  listEl.addEventListener('click', (e) => {
    const row = e.target.closest('.app-row');
    if (!row) return;
    const appId = row.dataset.appId;
    const app = Store.getApplications().find(a => a.id === appId);

    if (e.target.closest('[data-action="menu"]')) {
      document.querySelectorAll('.overflow-menu.open').forEach(m => { if (m !== row.querySelector('.overflow-menu')) m.classList.remove('open'); });
      row.querySelector('.overflow-menu').classList.toggle('open');
      return;
    }
    if (e.target.closest('[data-action="status"]')) {
      Store.updateApplicationStatus(appId, e.target.dataset.status);
      render();
      showToast(`Marked as ${e.target.dataset.status}`);
      return;
    }
    if (e.target.closest('[data-action="view"]')) {
      Store.setSelectedJob(app.job);
      window.location.href = 'job-details.html?id=' + encodeURIComponent(app.job.id);
      return;
    }
    if (e.target.closest('[data-action="remove"]')) {
      Store.removeApplication(appId);
      render();
      showToast('Application removed');
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.overflow-btn')) {
      document.querySelectorAll('.overflow-menu.open').forEach(m => m.classList.remove('open'));
    }
  });

  render();
})();
