(function () {
  const listEl = document.getElementById('saved-jobs-list');
  const byId = {}; // mutated in place, never reassigned, so wireJobRowActions' one-time listener stays valid

  function render() {
    const jobs = Store.getSavedJobs();
    if (!jobs.length) {
      listEl.innerHTML = `<div class="empty-state"><i class="fas fa-bookmark"></i><p>No saved jobs yet. Tap the bookmark icon on any job to save it here.</p></div>`;
      return;
    }
    Object.keys(byId).forEach(k => delete byId[k]);
    jobs.forEach(j => byId[j.id] = j);
    listEl.innerHTML = jobs.map(j => renderJobRow(j)).join('');
    wireJobRowActions(listEl, byId);
  }

  listEl.addEventListener('click', (e) => {
    if (e.target.closest('[data-action="save"]')) setTimeout(render, 0); // re-render after unsave removes it from the list
  });

  render();
})();
