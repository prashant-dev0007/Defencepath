/**
 * DEFENCE PATH - Computer Based Test (CBT) Examination Engine
 * Realistic NTA/UPSC style CBT Simulator
 */

let examData = {
  paperId: 0,
  title: "",
  durationMinutes: 60,
  marksPerCorrect: 1,
  negativeMarks: 0.25,
  questions: []
};

let currentQuestionIndex = 0;
let userResponses = {}; // questionId -> { selectedOption: 'A', status: 'answered'|'marked'|'not_answered'|'marked_answered', timeSpent: 0 }
let questionVisitStatus = {}; // questionId -> boolean
let timerInterval = null;
let remainingSeconds = 0;
let currentLang = 'en'; // 'en' or 'hi'

function initCbtEngine(paper, questions) {
  examData.paperId = paper.id;
  examData.title = paper.title;
  examData.durationMinutes = paper.duration_minutes;
  examData.marksPerCorrect = paper.marks_per_correct;
  examData.negativeMarks = paper.negative_marks;
  examData.questions = questions;

  remainingSeconds = examData.durationMinutes * 60;

  // Initialize responses
  questions.forEach((q, idx) => {
    userResponses[q.id] = {
      selectedOption: null,
      status: 'not_visited',
      timeSpent: 0
    };
  });

  // Try recovering session from localStorage
  const savedSessionKey = `cbt_session_${paper.id}`;
  const savedSession = localStorage.getItem(savedSessionKey);
  if (savedSession) {
    try {
      const parsed = JSON.parse(savedSession);
      if (parsed.paperId === paper.id && parsed.remainingSeconds > 0) {
        userResponses = parsed.userResponses;
        remainingSeconds = parsed.remainingSeconds;
        currentQuestionIndex = parsed.currentQuestionIndex || 0;
      }
    } catch(e) {
      console.warn("Could not restore session", e);
    }
  }

  renderQuestionPalette();
  loadQuestion(currentQuestionIndex);
  startTimer();

  // Attach button listeners
  document.getElementById('btn-save-next')?.addEventListener('click', saveAndNext);
  document.getElementById('btn-mark-review')?.addEventListener('click', markForReviewAndNext);
  document.getElementById('btn-clear-resp')?.addEventListener('click', clearResponse);
  document.getElementById('btn-prev')?.addEventListener('click', previousQuestion);
  document.getElementById('btn-submit-test')?.addEventListener('click', openSubmitModal);
  document.getElementById('btn-confirm-submit')?.addEventListener('click', finalizeSubmission);
  document.getElementById('btn-toggle-lang')?.addEventListener('click', toggleQuestionLanguage);

  // Auto save state every 5 seconds
  setInterval(saveLocalState, 5000);
}

function startTimer() {
  const timerDisplay = document.getElementById('cbt-timer');
  function updateTimer() {
    if (remainingSeconds <= 0) {
      clearInterval(timerInterval);
      alert("Time is up! Your examination will now be submitted automatically.");
      finalizeSubmission();
      return;
    }

    const hours = Math.floor(remainingSeconds / 3600);
    const minutes = Math.floor((remainingSeconds % 3600) / 60);
    const seconds = remainingSeconds % 60;

    const formatted = 
      (hours > 0 ? String(hours).padStart(2, '0') + ':' : '') +
      String(minutes).padStart(2, '0') + ':' +
      String(seconds).padStart(2, '0');

    if (timerDisplay) {
      timerDisplay.textContent = formatted;
      if (remainingSeconds < 300) {
        timerDisplay.classList.add('text-red-500', 'animate-pulse');
      }
    }
    remainingSeconds--;
  }

  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
}

function saveLocalState() {
  const savedSessionKey = `cbt_session_${examData.paperId}`;
  const data = {
    paperId: examData.paperId,
    remainingSeconds: remainingSeconds,
    userResponses: userResponses,
    currentQuestionIndex: currentQuestionIndex
  };
  localStorage.setItem(savedSessionKey, JSON.stringify(data));
}

function loadQuestion(index) {
  if (index < 0 || index >= examData.questions.length) return;
  currentQuestionIndex = index;
  const q = examData.questions[index];

  // Mark as visited if it was not visited
  if (userResponses[q.id].status === 'not_visited') {
    userResponses[q.id].status = 'not_answered';
  }

  // Update Question header & subject
  document.getElementById('cbt-q-number').textContent = `Question ${index + 1} of ${examData.questions.length}`;
  document.getElementById('cbt-q-subject').textContent = `${q.subject} » ${q.topic}`;
  document.getElementById('cbt-q-marks').textContent = `+${examData.marksPerCorrect} / -${examData.negativeMarks}`;

  // Question Text (Bilingual)
  const qText = (currentLang === 'hi' && q.question_text_hi) ? q.question_text_hi : q.question_text_en;
  document.getElementById('cbt-q-text').textContent = qText;

  // Render Options
  const optionsContainer = document.getElementById('cbt-options-container');
  optionsContainer.innerHTML = '';

  const opts = [
    { key: 'A', text_en: q.option_a_en, text_hi: q.option_a_hi },
    { key: 'B', text_en: q.option_b_en, text_hi: q.option_b_hi },
    { key: 'C', text_en: q.option_c_en, text_hi: q.option_c_hi },
    { key: 'D', text_en: q.option_d_en, text_hi: q.option_d_hi },
  ];

  const currentSelection = userResponses[q.id].selectedOption;

  opts.forEach(opt => {
    const optText = (currentLang === 'hi' && opt.text_hi) ? opt.text_hi : opt.text_en;
    const isSelected = (currentSelection === opt.key);

    const div = document.createElement('div');
    div.className = `flex items-center p-3.5 rounded-lg border cursor-pointer transition-all ${
      isSelected 
        ? 'bg-emerald-950/60 border-amber-400 text-white shadow-lg' 
        : 'bg-[#121B15] border-[#24382D] text-gray-200 hover:bg-[#1A2820] hover:border-gray-500'
    }`;
    div.innerHTML = `
      <div class="w-7 h-7 rounded-full flex items-center justify-center font-bold text-sm mr-3 ${
        isSelected ? 'bg-amber-400 text-black' : 'bg-gray-800 text-gray-300 border border-gray-600'
      }">
        ${opt.key}
      </div>
      <div class="text-sm md:text-base leading-relaxed flex-1">${optText}</div>
    `;

    div.addEventListener('click', () => {
      selectOption(q.id, opt.key);
    });

    optionsContainer.appendChild(div);
  });

  renderQuestionPalette();
}

function selectOption(qId, key) {
  userResponses[qId].selectedOption = key;
  // Reload current question to reflect selected style
  loadQuestion(currentQuestionIndex);
}

function saveAndNext() {
  const q = examData.questions[currentQuestionIndex];
  if (userResponses[q.id].selectedOption) {
    userResponses[q.id].status = 'answered';
  } else {
    userResponses[q.id].status = 'not_answered';
  }
  nextQuestion();
}

function markForReviewAndNext() {
  const q = examData.questions[currentQuestionIndex];
  if (userResponses[q.id].selectedOption) {
    userResponses[q.id].status = 'marked_answered';
  } else {
    userResponses[q.id].status = 'marked';
  }
  nextQuestion();
}

function clearResponse() {
  const q = examData.questions[currentQuestionIndex];
  userResponses[q.id].selectedOption = null;
  userResponses[q.id].status = 'not_answered';
  loadQuestion(currentQuestionIndex);
}

function nextQuestion() {
  if (currentQuestionIndex < examData.questions.length - 1) {
    loadQuestion(currentQuestionIndex + 1);
  } else {
    renderQuestionPalette();
  }
}

function previousQuestion() {
  if (currentQuestionIndex > 0) {
    loadQuestion(currentQuestionIndex - 1);
  }
}

function toggleQuestionLanguage() {
  currentLang = (currentLang === 'en') ? 'hi' : 'en';
  const btn = document.getElementById('btn-toggle-lang');
  if (btn) btn.textContent = (currentLang === 'en') ? 'हिंदी में देखें' : 'View in English';
  loadQuestion(currentQuestionIndex);
}

function renderQuestionPalette() {
  const paletteContainer = document.getElementById('cbt-palette-grid');
  if (!paletteContainer) return;
  paletteContainer.innerHTML = '';

  let counts = { answered: 0, not_answered: 0, not_visited: 0, marked: 0, marked_answered: 0 };

  examData.questions.forEach((q, idx) => {
    const status = userResponses[q.id].status;
    counts[status] = (counts[status] || 0) + 1;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = idx + 1;
    btn.className = `palette-btn palette-${status.replace('_', '-')}`;

    if (idx === currentQuestionIndex) {
      btn.classList.add('palette-active');
    }

    btn.addEventListener('click', () => {
      loadQuestion(idx);
    });

    paletteContainer.appendChild(btn);
  });

  // Update status summary counters
  const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  setEl('palette-count-answered', counts.answered + counts.marked_answered);
  setEl('palette-count-not-answered', counts.not_answered);
  setEl('palette-count-not-visited', counts.not_visited);
  setEl('palette-count-marked', counts.marked);
  setEl('palette-count-marked-answered', counts.marked_answered);
}

function openSubmitModal() {
  let answered = 0;
  let notAnswered = 0;
  let marked = 0;
  let notVisited = 0;

  examData.questions.forEach(q => {
    const s = userResponses[q.id].status;
    if (s === 'answered' || s === 'marked_answered') answered++;
    else if (s === 'marked') marked++;
    else if (s === 'not_answered') notAnswered++;
    else notVisited++;
  });

  document.getElementById('modal-summary-answered').textContent = answered;
  document.getElementById('modal-summary-unanswered').textContent = notAnswered;
  document.getElementById('modal-summary-marked').textContent = marked;
  document.getElementById('modal-summary-notvisited').textContent = notVisited;

  const modal = document.getElementById('cbt-submit-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeSubmitModal() {
  const modal = document.getElementById('cbt-submit-modal');
  if (modal) modal.classList.add('hidden');
}

function finalizeSubmission() {
  clearInterval(timerInterval);
  const timeTaken = (examData.durationMinutes * 60) - Math.max(0, remainingSeconds);

  // Prepare submission payload
  const payload = {
    paper_id: examData.paperId,
    time_taken_seconds: timeTaken,
    responses: userResponses
  };

  fetch('/api/submit-test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      localStorage.removeItem(`cbt_session_${examData.paperId}`);
      window.location.href = `/test-result/${data.attempt_id}`;
    } else {
      alert("Submission error: " + (data.error || "Please try again"));
    }
  })
  .catch(err => {
    console.error(err);
    alert("Connection error while submitting. Please check internet and retry.");
  });
}
