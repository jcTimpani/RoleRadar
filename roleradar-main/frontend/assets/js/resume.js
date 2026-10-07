(async function () {
  let selectedFile = null;
  let jobsCache = [];

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const fileNameEl = document.getElementById('file-name');
  const roleSelect = document.getElementById('target-role-select');

  document.getElementById('choose-file-btn').addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('click', (e) => { if (e.target.id !== 'choose-file-btn') fileInput.click(); });
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('drag-over'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { if (fileInput.files.length) handleFile(fileInput.files[0]); });

  function handleFile(file) {
    const allowedExt = ['.pdf', '.docx', '.txt'];
    if (!allowedExt.some(ext => file.name.toLowerCase().endsWith(ext))) {
      showToast('Unsupported file type. Use PDF, DOCX, or TXT.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showToast('File too large — max 10MB.');
      return;
    }
    selectedFile = file;
    fileNameEl.textContent = `Selected: ${file.name}`;
    setStep(2);
  }

  function setStep(n) {
    [1, 2, 3].forEach(i => {
      const el = document.getElementById('step-' + i);
      el.classList.toggle('active', i === n);
      el.classList.toggle('done', i < n);
    });
  }

  const jobOptgroup = document.getElementById('job-optgroup');
  try {
    jobsCache = await RoleRadarAPI.jobs({ per_page: 100 });
    jobsCache.forEach(j => {
      const opt = document.createElement('option');
      opt.value = j.id;
      opt.textContent = `${j.title} — ${j.company_name || ''}`;
      jobOptgroup.appendChild(opt);
    });
  } catch (e) { /* job optgroup stays empty if backend is unreachable; role/general modes still work */ }

  function localHeuristicAnalysis(text) {
    const lower = (text || '').toLowerCase();
    const sections = [
      { key: 'experience', label: 'Work Experience', re: /experience|employment|work history/ },
      { key: 'education', label: 'Education', re: /education|university|degree|bachelor|master/ },
      { key: 'skills', label: 'Technical Skills', re: /skills|python|sql|javascript|java|aws/ },
      { key: 'projects', label: 'Projects', re: /project/ },
      { key: 'certifications', label: 'Certifications', re: /certificat/ },
      { key: 'summary', label: 'Summary / Objective', re: /summary|objective|profile/ },
      { key: 'contact', label: 'Contact Information', re: /@|email|phone|\d{3}[-.\s]?\d{3}[-.\s]?\d{4}/ }
    ];
    const present = sections.filter(s => s.re.test(lower));
    const missing = sections.filter(s => !s.re.test(lower));
    const score = Math.round((present.length / sections.length) * 100);
    return {
      overallScore: score,
      missingSections: missing.map(s => s.label + ' section not clearly detected'),
      strengths: present.map(s => s.label + ' section is present'),
      improvements: missing.slice(0, 4).map(s => `Add a clear ${s.label.toLowerCase()} section with specific, quantified details.`),
      isMock: true
    };
  }

  function mapRealAnalysis(result) {
    return {
      overallScore: result.match_percentage ?? 0,
      missingSections: (result.missing_skills || []).map(s => `Missing/weak: ${s}`),
      strengths: (result.matched_skills || []).map(s => `Demonstrates ${s} experience`),
      improvements: (result.recommendations || []).map(r => `${r.skill ? r.skill + ': ' : ''}${r.reason || ''}`),
      overallSummary: result.overall_summary || '',
      isMock: false
    };
  }

  function renderResult(result) {
    document.getElementById('results-empty').style.display = 'none';
    document.getElementById('results-content').style.display = 'block';
    const circumference = 2 * Math.PI * 45;
    const pct = Math.max(0, Math.min(100, Math.round(result.overallScore)));
    document.getElementById('score-ring-fg').style.strokeDasharray = circumference;
    document.getElementById('score-ring-fg').style.strokeDashoffset = circumference - (circumference * pct / 100);
    document.getElementById('score-ring-value').textContent = pct + '%';

    document.getElementById('missing-sections').innerHTML = (result.missingSections.length ? result.missingSections : ['Nothing major missing — nice work!'])
      .map(m => `<div class="result-row missing"><i class="fas fa-circle-exclamation"></i> ${m}</div>`).join('');
    document.getElementById('strengths-list').innerHTML = (result.strengths.length ? result.strengths : ['Resume uploaded and parsed successfully.'])
      .map(s => `<div class="result-row strength"><i class="fas fa-circle-check"></i> ${s}</div>`).join('');
    document.getElementById('improvements-list').innerHTML = (result.improvements.length ? result.improvements : ['Keep refining bullet points with measurable impact.'])
      .map(i => `<div class="result-row improve"><i class="fas fa-lightbulb"></i> ${i}</div>`).join('');

    setStep(3);
    Store.setResumeResult({ overallScore: pct, ...result });
    window._lastResumeResult = result;
  }

  document.getElementById('analyze-btn').addEventListener('click', async () => {
    if (!selectedFile) { showToast('Please upload a resume file first.'); return; }
    const btn = document.getElementById('analyze-btn');
    btn.textContent = 'Analyzing…';
    btn.disabled = true;

    const selected = roleSelect.value;
    const mode = selected.startsWith('role:')
      ? { kind: 'role', role: selected.slice(5), label: selected.slice(5).replace(/-/g, ' ') }
      : selected
        ? { kind: 'job', jobId: selected, label: roleSelect.options[roleSelect.selectedIndex].textContent }
        : { kind: 'general' };

    try {
      const apiMode = mode.kind === 'job' ? { jobId: mode.jobId } : mode.kind === 'role' ? { role: mode.role } : {};
      const result = await RoleRadarAPI.skillsAnalyzeFile(selectedFile, apiMode);
      renderResult(mapRealAnalysis(result));
      showToast(
        mode.kind === 'job' ? `Analysis complete — compared against ${mode.label}` :
        mode.kind === 'role' ? `Analysis complete — compared against general ${mode.label} requirements` :
        'Analysis complete — general resume completeness check'
      );
    } catch (e) {
      try {
        const parsed = await RoleRadarAPI.resumeParse(selectedFile);
        renderResult(localHeuristicAnalysis(parsed.text));
        showToast('AI analysis unavailable — showing local estimate');
      } catch (err) {
        renderResult(localHeuristicAnalysis(''));
        showToast('Could not read file — showing placeholder result');
      }
    } finally {
      btn.textContent = 'Analyze Resume';
      btn.disabled = false;
    }
  });

  document.getElementById('download-report-btn').addEventListener('click', () => {
    const result = window._lastResumeResult;
    if (!result) return;
    const lines = [
      'RoleRadar — Resume Completeness Report', '',
      `Overall Score: ${Math.round(result.overallScore)}%`, '',
      'Missing / Incomplete Sections:', ...result.missingSections.map(s => ' - ' + s), '',
      'Strengths:', ...result.strengths.map(s => ' - ' + s), '',
      'Recommended Improvements:', ...result.improvements.map(s => ' - ' + s)
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'roleradar-resume-report.txt';
    a.click();
  });

  // Restore the last analysis on revisit, instead of always starting from a blank slate.
  const savedResult = Store.getResumeResult();
  if (savedResult) {
    renderResult(savedResult);
    fileNameEl.textContent = 'Showing your most recent analysis — upload a new file to re-run it.';
  }
})();
