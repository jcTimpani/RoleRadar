(async function () {
  const roleSelect = document.getElementById('role-select');
  const difficultySelect = document.getElementById('difficulty-select');
  const startBtn = document.getElementById('start-practice-btn');
  const qaLayout = document.getElementById('qa-layout');
  const qaEmpty = document.getElementById('qa-empty');
  const questionList = document.getElementById('question-list');
  const answerInput = document.getElementById('answer-input');
  const feedbackBody = document.getElementById('feedback-body');
  const submitBtn = document.getElementById('submit-answer-btn');
  const voiceBtn = document.getElementById('voice-btn');
  const voiceStatus = document.getElementById('voice-status');

  let session = null; // { session_id, questions, current_question_index }
  let questionStartTime = null;

  // Real browser speech-to-text (Web Speech API, built into Chrome) — the mic captures
  // audio client-side and transcribes it locally; the resulting text is submitted through
  // the same /respond endpoint text answers already use, so no backend change is needed.
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let isListening = false;
  let baseAnswerText = '';

  if (SpeechRecognitionImpl) {
    voiceBtn.style.display = 'inline-flex';
    recognizer = new SpeechRecognitionImpl();
    recognizer.continuous = true;
    recognizer.interimResults = true;
    recognizer.lang = 'en-US';

    recognizer.addEventListener('result', (e) => {
      let finalText = '';
      let interimText = '';
      for (let i = 0; i < e.results.length; i++) {
        const chunk = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += chunk + ' ';
        else interimText += chunk;
      }
      answerInput.value = (baseAnswerText + finalText).trim() + (interimText ? ' ' + interimText : '');
    });

    recognizer.addEventListener('end', () => {
      isListening = false;
      baseAnswerText = answerInput.value.trim() ? answerInput.value.trim() + ' ' : '';
      voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> Speak Answer';
      voiceBtn.classList.remove('btn-danger');
      voiceStatus.style.display = 'none';
    });

    recognizer.addEventListener('error', (e) => {
      voiceStatus.textContent = e.error === 'not-allowed'
        ? 'Microphone access denied — allow mic permission to use voice input.'
        : `Voice input error: ${e.error}. You can keep typing instead.`;
      voiceStatus.style.display = 'block';
    });

    voiceBtn.addEventListener('click', () => {
      if (isListening) {
        recognizer.stop();
        return;
      }
      baseAnswerText = answerInput.value.trim() ? answerInput.value.trim() + ' ' : '';
      isListening = true;
      voiceBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
      voiceBtn.classList.add('btn-danger');
      voiceStatus.textContent = 'Listening… speak your answer, then click Stop.';
      voiceStatus.style.display = 'block';
      recognizer.start();
    });
  }

  function resetVoiceUI() {
    if (isListening && recognizer) recognizer.stop();
    baseAnswerText = '';
    voiceStatus.style.display = 'none';
  }

  try {
    const jobs = await RoleRadarAPI.jobs({ per_page: 100 });
    roleSelect.innerHTML = '<option value="">General practice (no specific job)</option>' +
      jobs.map(j => `<option value="${j.id}" data-title="${j.title}">${j.title} — ${j.company_name || ''}</option>`).join('');
  } catch (e) {
    roleSelect.innerHTML = '<option value="">General practice (no specific job)</option>';
  }

  function renderQuestionList() {
    questionList.innerHTML = session.questions.map((q, i) => `
      <li class="${i === session.current_question_index ? 'active' : ''} ${i < session.current_question_index ? 'done' : ''}" data-idx="${i}">
        ${q.text || q.question_text}
      </li>`).join('');
  }

  function renderFeedback(feedback) {
    const accuracy = (feedback.technical_accuracy ?? 0);
    feedbackBody.innerHTML = `
      ${(feedback.strengths || []).map(s => `<div class="feedback-item"><i class="fas fa-circle-check"></i> ${s}</div>`).join('')}
      ${(feedback.improvements || []).map(s => `<div class="feedback-item"><i class="fas fa-lightbulb"></i> ${s}</div>`).join('')}
      <div class="feedback-score">${(accuracy / 10).toFixed(1)}/10</div>
      <p class="text-muted" style="font-size:var(--fs-xs);margin:0 0 8px;">Technical Accuracy</p>
      <div class="progress-bar"><span style="width:${accuracy}%;"></span></div>
      ${feedback.communication_score !== undefined ? `<p class="text-muted" style="margin-top:12px;font-size:var(--fs-xs);">Overall: ${Math.round(feedback.overall_score || 0)}% · Communication: ${Math.round(feedback.communication_score || 0)}%</p>` : ''}
    `;
  }

  function showSummary(summary) {
    feedbackBody.innerHTML = `
      <div class="feedback-score">${Math.round(summary.average_score || 0)}%</div>
      <p class="text-muted" style="font-size:var(--fs-xs);">Session Average</p>
      <p style="margin-top:12px;">You answered ${summary.total_questions || session.questions.length} question(s). Nice work!</p>
      <button class="btn btn-primary btn-block" id="restart-btn" style="margin-top:14px;">Practice Again</button>
    `;
    document.getElementById('restart-btn').addEventListener('click', () => window.location.reload());
    submitBtn.disabled = true;
    answerInput.disabled = true;
    voiceBtn.disabled = true;
    resetVoiceUI();
  }

  startBtn.addEventListener('click', async () => {
    const jobId = roleSelect.value ? parseInt(roleSelect.value, 10) : 0;
    const roleText = roleSelect.selectedOptions[0] ? (roleSelect.selectedOptions[0].dataset.title || roleSelect.selectedOptions[0].text) : 'Software Engineer';
    const session_local = Store.getSession();

    startBtn.disabled = true;
    startBtn.textContent = 'Starting…';
    try {
      session = await RoleRadarAPI.interviewStart({
        job_id: jobId,
        user_id: (session_local && session_local.email) || 'demo-user',
        role: roleText,
        difficulty: difficultySelect.value
      });
      qaLayout.style.display = 'grid';
      qaEmpty.style.display = 'none';
      renderQuestionList();
      answerInput.value = '';
      resetVoiceUI();
      answerInput.disabled = false;
      submitBtn.disabled = false;
      feedbackBody.innerHTML = `<p class="text-muted">Answer the highlighted question, then submit.</p>`;
      questionStartTime = Date.now();
    } catch (e) {
      showToast('Could not start interview session — is the backend running?');
    } finally {
      startBtn.disabled = false;
      startBtn.textContent = 'Start Practice';
    }
  });

  questionList.addEventListener('click', (e) => {
    const li = e.target.closest('li');
    if (!li) return;
    const idx = parseInt(li.dataset.idx, 10);
    if (idx !== session.current_question_index) return; // backend only accepts the current question in order
  });

  submitBtn.addEventListener('click', async () => {
    if (!session) return;
    const transcript = answerInput.value.trim();
    if (!transcript) { showToast('Type an answer first.'); return; }

    const duration = questionStartTime ? Math.max(5, (Date.now() - questionStartTime) / 1000) : 15;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting…';
    try {
      const res = await RoleRadarAPI.interviewRespond(session.session_id, { transcript, duration });
      renderFeedback(res.feedback);
      Store.incrementQuestionsPracticed(1);
      session.current_question_index += 1;
      answerInput.value = '';
      resetVoiceUI();
      questionStartTime = Date.now();

      if (session.current_question_index >= session.questions.length) {
        const summary = await RoleRadarAPI.interviewEnd(session.session_id);
        showSummary(summary.summary || {});
      } else {
        renderQuestionList();
      }
    } catch (e) {
      showToast('Error submitting answer.');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit Answer';
    }
  });
})();
