/* Shared job-card/row rendering helpers used by Dashboard, Find Jobs, Job Details, Applications, Saved Jobs. */

const SOURCE_META = {
  linkedin: { label: 'LinkedIn', icon: 'fa-brands fa-linkedin', color: '#0a66c2', logo: 'https://unavatar.io/linkedin.com' },
  indeed: { label: 'Indeed', icon: 'fa-brands fa-google', color: '#2557a7', logo: 'https://unavatar.io/indeed.com' },
  glassdoor: { label: 'Glassdoor', icon: 'fa-solid fa-door-open', color: '#0caa41', logo: 'https://unavatar.io/glassdoor.com' },
  ziprecruiter: { label: 'ZipRecruiter', icon: 'fa-solid fa-bolt', color: '#4f46e5', logo: 'https://unavatar.io/ziprecruiter.com' },
  crawler: { label: 'RoleRadar', icon: 'fa-solid fa-satellite-dish', color: '#22c55e', logo: null }
};

/* Best-effort real company domain lookup, so job cards can show the company's actual logo
   (via unavatar.io, a live public favicon/logo aggregator) instead of a generic icon.
   Populated once per page from GET /api/companies and merged onto job objects — see attachCompanyLogos(). */
const COMPANY_DOMAIN_OVERRIDES = {
  'AT&T': 'att.com', 'Toyota': 'toyota.com', 'Southwest Airlines': 'southwest.com',
  'Infosys': 'infosys.com', 'Accenture': 'accenture.com', 'TCS': 'tcs.com',
  'Cognizant': 'cognizant.com', 'Wipro': 'wipro.com', 'DocuSign': 'docusign.com', 'Comcast': 'comcast.com'
};

function domainFromUrl(url) {
  if (!url) return null;
  try { return new URL(url.startsWith('http') ? url : 'https://' + url).hostname.replace(/^www\./, ''); }
  catch (e) { return null; }
}

async function attachCompanyLogos(jobs) {
  try {
    const companies = await RoleRadarAPI.companies({ per_page: 100 });
    const byId = {};
    companies.forEach(c => byId[c.id] = domainFromUrl(c.website) || COMPANY_DOMAIN_OVERRIDES[c.name]);
    jobs.forEach(j => { j._companyDomain = byId[j.company_id] || COMPANY_DOMAIN_OVERRIDES[j.company_name] || null; });
  } catch (e) { /* logos just fall back to colored initials */ }
  return jobs;
}

const AVATAR_PALETTE = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#4338ca'];

function sourceMeta(job) {
  const key = (job.source || 'crawler').toLowerCase();
  if (SOURCE_META[key]) return SOURCE_META[key];
  // Real publisher name we don't have bespoke styling for (Dice, Monster, AT&T Careers, etc.)
  // — show it as-is rather than mislabeling third-party data as our own "RoleRadar" crawler.
  if (job.source) return { label: job.source, icon: 'fa-solid fa-briefcase', color: '#64748b', logo: null };
  return SOURCE_META.crawler;
}

function isKnownJobBoard(job) {
  const key = (job.source || '').toLowerCase();
  return key !== '' && key !== 'crawler' && !!SOURCE_META[key];
}

function companyAvatarColor(name) {
  const str = name || '?';
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function jobLogoHtml(job) {
  const initial = (job.company_name || '?').trim().charAt(0).toUpperCase() || '?';
  const fallback = `this.outerHTML='<div class=\\'job-logo\\' style=\\'background:${companyAvatarColor(job.company_name)}\\'>${initial}</div>'`;
  // Real company logo (via unavatar.io, keyed off the company's actual website domain) beats everything else.
  if (job._companyDomain) {
    return `<div class="job-logo" style="background:#fff;border:1px solid var(--app-border);padding:6px;"><img src="https://unavatar.io/${job._companyDomain}?fallback=false" alt="${job.company_name || ''}" style="width:100%;height:100%;object-fit:contain;" onerror="${fallback}"></div>`;
  }
  // Known job board with no direct company logo -> real board logo image.
  if (isKnownJobBoard(job) && sourceMeta(job).logo) {
    const meta = sourceMeta(job);
    return `<div class="job-logo" style="background:#fff;border:1px solid var(--app-border);padding:8px;"><img src="${meta.logo}" alt="${meta.label}" style="width:100%;height:100%;object-fit:contain;" onerror="${fallback}"></div>`;
  }
  return `<div class="job-logo" style="background:${companyAvatarColor(job.company_name)}">${initial}</div>`;
}

function sourceBadgeHtml(job) {
  const meta = sourceMeta(job);
  return `<span class="source-badge" style="color:${meta.color}"><i class="${meta.icon}"></i> ${meta.label}</span>`;
}

function formatSalary(job) {
  if (job.salary_range) return job.salary_range;
  if (job.salary_min && job.salary_max) return `$${Math.round(job.salary_min / 1000)}K - $${Math.round(job.salary_max / 1000)}K`;
  return 'Salary not listed';
}

function isRemote(job) {
  return job.location_remote === true || job.location_remote === 1 || (job.job_type || '').toLowerCase().includes('remote');
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// A short line ending in ":" or written in Title Case ("What We Are Looking For",
// "Key Responsibilities") with no punctuation reads as a section header in job postings.
function isLikelyHeader(line) {
  if (!line || line.length >= 60) return false;
  if (/:$/.test(line)) return true;
  const words = line.split(/\s+/);
  if (words.length < 2 || words.length > 8) return false;
  const STOPWORDS = new Set(['a', 'an', 'the', 'of', 'for', 'and', 'or', 'to', 'in', 'is', 'we', 'you', 'are']);
  return !/[.!?;,]$/.test(line) && words.every(w => STOPWORDS.has(w.toLowerCase()) || /^[A-Z0-9]/.test(w));
}

/* Real job descriptions from JSearch come as plain text with \n\n paragraph breaks and
   "• "-prefixed bullet lines — HTML collapses all of that by default, so it has to be
   turned into real <p>/<ul><li> markup instead of being dumped into one flat block. */
function formatJobText(text) {
  if (!text) return '';
  const blocks = text.split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);
  return blocks.map(block => {
    const lines = block.split('\n').map(l => l.trim()).filter(Boolean);
    const bulletLines = lines.filter(l => /^[•\-*]\s+/.test(l));
    if (bulletLines.length && bulletLines.length === lines.length) {
      return `<ul class="job-text-list">${lines.map(l => `<li>${escapeHtml(l.replace(/^[•\-*]\s+/, ''))}</li>`).join('')}</ul>`;
    }
    if (lines.length === 1 && isLikelyHeader(lines[0])) {
      return `<h4 class="job-text-heading">${escapeHtml(lines[0])}</h4>`;
    }
    return `<p>${escapeHtml(lines.join(' '))}</p>`;
  }).join('');
}

/* Best-effort extraction of a real "Requirements/Qualifications" section out of the
   free-text description, instead of only showing keyword-matched skill chips. */
const REQUIREMENTS_HEADERS = /(requirements?|qualifications?|minimum qualifications?|preferred qualifications?|required skills?|what you.?ll need|what you need|what we.?re looking for|what we are looking for|who you are|about you|ideal candidate|skills (needed|required)|you (have|bring))\s*:?\s*$/i;
const NEXT_SECTION_HEADERS = /(responsibilities|benefits|compensation|about (the|us)|who we are|why join|equal opportunity|how to apply|perks|what we offer)\s*:?\s*$/i;

function extractRequirementsSection(description) {
  if (!description) return null;
  const blocks = description.split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);
  const isHeaderLine = isLikelyHeader;

  for (let i = 0; i < blocks.length; i++) {
    const firstLine = blocks[i].split('\n')[0].trim();
    if (!(isHeaderLine(firstLine) && REQUIREMENTS_HEADERS.test(firstLine))) continue;

    const collected = [blocks[i]];
    for (let j = i + 1; j < blocks.length; j++) {
      const nextFirstLine = blocks[j].split('\n')[0].trim();
      // Stop at the next differently-labeled section (Responsibilities, Benefits, etc.);
      // keep going through further requirements-style headers (e.g. "Preferred Qualifications").
      if (isHeaderLine(nextFirstLine) && NEXT_SECTION_HEADERS.test(nextFirstLine)) break;
      collected.push(blocks[j]);
    }
    return collected.join('\n\n');
  }
  return null;
}

function jobMetaLine(job) {
  const bits = [];
  if (job.location_city) bits.push(`<i class="fas fa-location-dot"></i> ${job.location_city}${job.location_state ? ', ' + job.location_state : ''}`);
  else bits.push('Remote');
  if (isRemote(job)) bits.push('<i class="fas fa-house"></i> Remote');
  if (job.job_type) bits.push(job.job_type);
  return bits.map(b => `<span>${b}</span>`).join('');
}

const SKILL_KEYWORDS = ['python', 'javascript', 'react', 'node.js', 'sql', 'aws', 'docker', 'kubernetes',
  'java', 'c#', '.net', 'postgresql', 'mongodb', 'git', 'linux', 'api', 'rest', 'graphql', 'microservices',
  'agile', 'scrum', 'machine learning', 'statistics', 'tableau', 'data visualization'];

function extractSkills(job) {
  const text = ((job.description || '') + ' ' + (job.title || '')).toLowerCase();
  const found = SKILL_KEYWORDS.filter(s => text.includes(s));
  if (found.length) return found.slice(0, 4).map(s => s.replace(/\b\w/g, c => c.toUpperCase()));
  const title = (job.title || '').toLowerCase();
  if (title.includes('data')) return ['Python', 'SQL', 'Statistics', 'Machine Learning'];
  if (title.includes('frontend') || title.includes('react')) return ['React', 'JavaScript', 'CSS'];
  if (title.includes('devops') || title.includes('cloud')) return ['AWS', 'Docker', 'CI/CD'];
  if (title.includes('security')) return ['Security', 'Networking', 'Compliance'];
  return ['Python', 'JavaScript', 'SQL'];
}

function renderJobRow(job, opts) {
  opts = opts || {};
  const saved = Store.isJobSaved(job.id);
  const skills = extractSkills(job);
  return `
    <div class="job-row" data-job-id="${job.id}">
      <div class="job-row-top">
        ${jobLogoHtml(job)}
        <div class="job-info">
          <p class="job-title">${job.title}</p>
          <div class="job-meta">
            <span>${job.company_name || ''}</span>
            ${jobMetaLine(job)}
          </div>
        </div>
        <div class="job-actions">
          ${sourceBadgeHtml(job)}
          <span class="salary">${formatSalary(job)}</span>
          ${opts.showBookmark !== false ? `<button class="bookmark-btn ${saved ? 'saved' : ''}" data-action="save" title="Save job"><i class="${saved ? 'fas' : 'far'} fa-bookmark"></i></button>` : ''}
          ${opts.showView !== false ? `<button class="btn btn-primary btn-sm" data-action="view">View Job</button>` : ''}
        </div>
      </div>
      <div class="job-skill-row">${skills.map(s => `<span class="chip">${s}</span>`).join('')}</div>
    </div>`;
}

function wireJobRowActions(container, jobsById) {
  if (container._rrJobsWired) return; // avoid stacking duplicate listeners across repeated re-renders
  container._rrJobsWired = true;
  container.addEventListener('click', (e) => {
    const row = e.target.closest('.job-row');
    if (!row) return;
    const job = jobsById[row.getAttribute('data-job-id')];
    if (!job) return;

    if (e.target.closest('[data-action="save"]')) {
      if (!Store.isLoggedIn()) { window.location.href = 'login.html?next=' + encodeURIComponent(location.pathname + location.search); return; }
      const nowSaved = Store.toggleSavedJob(job);
      e.target.closest('[data-action="save"]').classList.toggle('saved', nowSaved);
      e.target.closest('[data-action="save"]').innerHTML = `<i class="${nowSaved ? 'fas' : 'far'} fa-bookmark"></i>`;
      showToast(nowSaved ? 'Job saved' : 'Removed from saved jobs');
      return;
    }
    if (e.target.closest('[data-action="view"]') || e.target === row || row.contains(e.target)) {
      Store.setSelectedJob(job);
      window.location.href = 'job-details.html?id=' + encodeURIComponent(job.id);
    }
  });
}
