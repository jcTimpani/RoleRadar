(async function () {
  const resultsList = document.getElementById('results-list');
  const resultsCount = document.getElementById('results-count');
  const searchBtn = document.querySelector('#search-form button[type="submit"]');
  let allJobs = [];
  const jobsById = {}; // mutated in place (never reassigned) so wireJobRowActions' one-time listener stays valid across re-renders

  const params = new URLSearchParams(window.location.search);
  document.getElementById('search-q').value = params.get('q') || '';
  document.getElementById('search-loc').value = params.get('loc') || '';

  // Keyword groups used to bucket whatever's in the DB into role categories for browsing —
  // purely a client-side title match, no schema change needed.
  const CATEGORIES = {
    software: ['software engineer', 'full stack', 'full-stack', 'backend', 'back-end', 'back end', '.net', 'java developer', 'python developer'],
    frontend: ['frontend', 'front-end', 'front end', 'react developer', 'ui developer', 'web developer'],
    data: ['data scientist', 'data analyst', 'machine learning', 'ml engineer', 'ai engineer', 'data engineer'],
    qa: ['qa ', 'qa engineer', 'quality assurance', 'test automation', 'sdet', 'test engineer'],
    devops: ['devops', 'cloud architect', 'cloud engineer', 'site reliability', 'infrastructure', 'platform engineer'],
    security: ['security', 'cybersecurity', 'infosec', 'soc analyst'],
  };

  function jobCategories(job) {
    const t = (job.title || '').toLowerCase();
    return Object.keys(CATEGORIES).filter(cat => CATEGORIES[cat].some(kw => t.includes(kw)));
  }

  const CRAWL_SOURCES = ['LinkedIn', 'Indeed', 'ZipRecruiter', 'Glassdoor', 'Dice', 'Monster'];

  function showCrawlingState() {
    resultsCount.textContent = 'Searching live sources…';
    resultsList.innerHTML = `
      <div class="empty-state" id="crawl-status">
        <i class="fas fa-satellite-dish fa-spin"></i>
        <p id="crawl-status-text">Connecting to job sources…</p>
      </div>`;
    let i = 0;
    const el = document.getElementById('crawl-status-text');
    const timer = setInterval(() => {
      if (!el || !document.body.contains(el)) { clearInterval(timer); return; }
      el.textContent = `Checking ${CRAWL_SOURCES[i % CRAWL_SOURCES.length]}…`;
      i++;
    }, 700);
    return () => clearInterval(timer);
  }

  function mergeJobs(found) {
    // Dedup by id — the backend already dedupes by source_url on insert (existing
    // source_url returns the existing row's id instead of inserting a duplicate),
    // so a job that was already in the DB just comes back with the same id here.
    const byId = new Map(allJobs.map(j => [j.id, j]));
    found.forEach(j => byId.set(j.id, j));
    allJobs = [...byId.values()];
  }

  async function runLiveSearch() {
    const q = document.getElementById('search-q').value.trim();
    const loc = document.getElementById('search-loc').value.trim();
    if (!q) { showToast('Enter a role or keyword to search live sources.'); return; }

    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching…';
    const stopAnim = showCrawlingState();

    try {
      const found = await RoleRadarAPI.searchJobsLive(q, loc || 'Dallas, TX');
      stopAnim();
      mergeJobs(found);
      await attachCompanyLogos(allJobs);
      showToast(`Found ${found.length} live job${found.length === 1 ? '' : 's'} for "${q}" — saved to your job list`);
      render();
    } catch (e) {
      stopAnim();
      resultsList.innerHTML = `<div class="empty-state"><i class="fas fa-triangle-exclamation"></i><p>Live search failed. The server may be waking up. Please try again in a moment.</p></div>`;
      resultsCount.textContent = '0 jobs found';
    } finally {
      searchBtn.disabled = false;
      searchBtn.textContent = 'Search';
    }
  }

  function salaryValue(job) {
    if (job.salary_min) return job.salary_min;
    if (job.salary_range) {
      const m = String(job.salary_range).match(/(\d+)/);
      return m ? parseInt(m[1], 10) * 1000 : 0;
    }
    return 0;
  }

  function matchesFilters(job) {
    const q = document.getElementById('search-q').value.trim().toLowerCase();
    const loc = document.getElementById('search-loc').value.trim().toLowerCase();
    // Every word of the search must appear in the title or company ("python developer" also finds "Sr Python Developer (W2)"
    // and "Developer - Python"), instead of requiring the exact phrase.
    if (q) {
      const haystack = `${job.title || ''} ${job.company_name || ''}`.toLowerCase();
      if (!q.split(/\s+/).every(word => haystack.includes(word))) return false;
    }
    // Locations are typed (or picked from suggestions) as "City, ST", so compare against the combined city + state text too.
    if (loc) {
      const place = [job.location_city, job.location_state].filter(Boolean).join(', ').toLowerCase();
      if (!place.includes(loc) && !(job.location_city || '').toLowerCase().includes(loc) && !(job.location_state || '').toLowerCase().includes(loc)) return false;
    }

    const activeCategory = document.querySelector('input[name="category"]:checked')?.value || 'all';
    if (activeCategory !== 'all' && !jobCategories(job).includes(activeCategory)) return false;

    const activePill = document.querySelector('#pill-filters .pill.active')?.dataset.filter || 'all';
    const jt = (job.job_type || '').toLowerCase();
    if (activePill === 'remote' && !isRemote(job)) return false;
    if (activePill === 'onsite' && (isRemote(job) || jt.includes('hybrid'))) return false;
    if (activePill === 'hybrid' && !jt.includes('hybrid')) return false;
    if (activePill === 'full-time' && !jt.includes('full')) return false;
    if (activePill === 'part-time' && !jt.includes('part')) return false;

    const checkedTypes = [...document.querySelectorAll('input[name="jobtype"]:checked')].map(i => i.value);
    if (checkedTypes.length && !checkedTypes.some(t => jt.includes(t.split('-')[0]))) return false;

    const checkedExp = [...document.querySelectorAll('input[name="exp"]:checked')].map(i => i.value);
    if (checkedExp.length && !checkedExp.includes((job.experience_level || '').toLowerCase())) return false;

    const salary = document.querySelector('input[name="salary"]:checked')?.value || '';
    if (salary) {
      const [min, max] = salary.split('-').map(Number);
      const v = salaryValue(job) / 1000;
      if (v < min || v > max) return false;
    }
    return true;
  }

  function render() {
    let filtered = allJobs.filter(matchesFilters);

    const sort = document.getElementById('sort-select').value;
    if (sort === 'salary-high') filtered = filtered.slice().sort((a, b) => salaryValue(b) - salaryValue(a));
    if (sort === 'newest') filtered = filtered.slice().sort((a, b) => new Date(b.posted_date || 0) - new Date(a.posted_date || 0));

    resultsCount.textContent = `${filtered.length} job${filtered.length === 1 ? '' : 's'} found`;
    if (!filtered.length) {
      resultsList.innerHTML = `<div class="empty-state"><i class="fas fa-magnifying-glass"></i><p>No jobs match your filters. Try widening your search, or use the search bar to pull live listings.</p></div>`;
      return;
    }
    Object.keys(jobsById).forEach(k => delete jobsById[k]);
    filtered.forEach(j => jobsById[j.id] = j);
    resultsList.innerHTML = filtered.map(j => renderJobRow(j)).join('');
    wireJobRowActions(resultsList, jobsById);
  }

  // Autocomplete: common roles/places plus whatever titles and locations are actually in the loaded jobs.
  const COMMON_ROLES = ['Software Engineer', 'Frontend Developer', 'Backend Developer', 'Full Stack Developer', 'Data Scientist', 'Data Analyst',
    'Data Engineer', 'Machine Learning Engineer', 'DevOps Engineer', 'Cloud Engineer', 'QA Engineer', 'Test Automation Engineer',
    'Cybersecurity Analyst', 'Security Engineer', 'Product Manager', 'Project Manager', 'UX Designer', 'UI Designer', 'Business Analyst',
    'Mobile Developer', 'iOS Developer', 'Android Developer', 'React Developer', 'Python Developer', 'Java Developer', 'Node.js Developer',
    'Site Reliability Engineer', 'Database Administrator', 'Systems Administrator', 'Technical Support Engineer', 'Solutions Architect'];
  const COMMON_PLACES = ['Dallas, TX', 'Austin, TX', 'Houston, TX', 'Plano, TX', 'Irving, TX', 'Fort Worth, TX', 'San Francisco, CA', 'New York, NY',
    'Seattle, WA', 'Chicago, IL', 'Boston, MA', 'Atlanta, GA', 'Denver, CO', 'Los Angeles, CA', 'Remote'];

  function uniqueMatches(pool, query) {
    const q = query.toLowerCase();
    const seen = new Set();
    const hits = pool.filter(t => {
      const k = t.toLowerCase();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return !q || k.includes(q);
    });
    // prefix matches first, then the rest
    return hits.sort((a, b) => Number(b.toLowerCase().startsWith(q)) - Number(a.toLowerCase().startsWith(q)));
  }

  attachSuggest(document.getElementById('search-q'), (query) =>
    uniqueMatches([...COMMON_ROLES, ...allJobs.map(j => j.title || '')], query));
  attachSuggest(document.getElementById('search-loc'), (query) =>
    uniqueMatches([...COMMON_PLACES, ...allJobs.map(j => [j.location_city, j.location_state].filter(Boolean).join(', '))], query));

  // Small screens: filters fold away behind a button
  const filtersToggle = document.getElementById('filters-toggle');
  const filterPanel = document.getElementById('filter-panel');
  if (filtersToggle && filterPanel) {
    filtersToggle.addEventListener('click', () => {
      const open = filterPanel.classList.toggle('open');
      filtersToggle.setAttribute('aria-expanded', String(open));
      filtersToggle.innerHTML = open ? '<i class="fas fa-xmark"></i> Hide filters' : '<i class="fas fa-sliders"></i> Filters';
    });
  }

  document.getElementById('search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (Store.isLoggedIn()) runLiveSearch();
    else { render(); showToast('Log in to pull fresh live listings — showing matches from our database.'); }
  });
  document.getElementById('sort-select').addEventListener('change', render);
  document.querySelectorAll('input[name="jobtype"], input[name="exp"], input[name="salary"], input[name="category"]').forEach(el => el.addEventListener('change', render));
  document.querySelectorAll('#pill-filters .pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#pill-filters .pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      render();
    });
  });

  // Browse whatever's already in the DB (from prior live searches / seed crawls) on load,
  // grouped/filterable by category. Live search (the form above) is additive on top of this:
  // it pulls fresh real results and merges them in, deduped by the backend on source_url.
  try {
    allJobs = await RoleRadarAPI.jobs({ per_page: 100 });
    await attachCompanyLogos(allJobs);
  } catch (e) {
    resultsList.innerHTML = `<div class="empty-state"><i class="fas fa-triangle-exclamation"></i><p>Error loading jobs. The server may be waking up. Please try again in a moment.</p></div>`;
    resultsCount.textContent = '0 jobs found';
    return;
  }

  // Arriving with ?q= (e.g. from the landing page's hero search) triggers a live
  // search immediately, on top of the DB jobs already loaded above.
  if (document.getElementById('search-q').value.trim() && Store.isLoggedIn()) {
    runLiveSearch();
  } else {
    render();
  }
})();
