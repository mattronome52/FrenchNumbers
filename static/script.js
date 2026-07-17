/* ── State ──────────────────────────────────────────────── */
let currentItem     = null;
let answered        = false;
let sessionActive   = false;
let pendingComplete = null;  // holds final session status until user presses Next
let prefs = {
  voice_pref:    'female',
  speed_pref:    'normal',
  session_size:  10,
  exercise_type: 'all',
};

const SPEED_RATES = { slow: 0.6, normal: 0.9, fast: 1.2 };

/* ── DOM refs ───────────────────────────────────────────── */
const promptTextEl    = document.getElementById('prompt-text');
const hintTextEl      = document.getElementById('hint-text');
const playBtn         = document.getElementById('play-btn');
const answerInput     = document.getElementById('answer-input');
const submitBtn       = document.getElementById('submit-btn');
const answerArea      = document.getElementById('answer-area');
const resultArea      = document.getElementById('result-area');
const resultMsg       = document.getElementById('result-msg');
const correctDisplay  = document.getElementById('correct-display');
const exerciseCard    = document.getElementById('exercise-card');
const completeCard    = document.getElementById('complete-card');
const completeMsgEl   = document.getElementById('complete-msg');
const nextBtn         = document.getElementById('next-btn');
const progressArea    = document.getElementById('progress-area');
const progressText    = document.getElementById('progress-text');
const progressFill    = document.getElementById('progress-bar-fill');
const prefsOverlay    = document.getElementById('prefs-overlay');
const prefsOpenBtn    = document.getElementById('prefs-open-btn');
const prefsCancelBtn  = document.getElementById('prefs-cancel-btn');
const startSessionBtn = document.getElementById('start-session-btn');
const newSessionBtn   = document.getElementById('new-session-btn');
const redoSessionBtn  = document.getElementById('redo-session-btn');
const sessionSizeInput = document.getElementById('session-size-input');
const euroSymbol      = document.getElementById('euro-symbol');


/* ── Web Speech API ─────────────────────────────────────── */

// Voices load asynchronously on some browsers (notably Chrome).
// speakWhenReady() waits for them before calling speak().
function speakWhenReady(text) {
  if (speechSynthesis.getVoices().length > 0) {
    speak(text);
  } else {
    speechSynthesis.addEventListener('voiceschanged', () => speak(text), { once: true });
  }
}

// Strip accents so "Amélie" matches "amelie", etc.
function asciify(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function getFrenchVoice(preferMale) {
  const voices = speechSynthesis.getVoices();
  const fr = voices.filter(v => v.lang.startsWith('fr'));
  if (!fr.length) return null;

  const maleParts   = ['thomas', 'pierre', 'nicolas', 'male', 'homme'];
  const femaleParts = ['amelie', 'aurelie', 'marie', 'juliette', 'female', 'femme'];
  const targets = preferMale ? maleParts : femaleParts;

  const match = fr.find(v => targets.some(t => asciify(v.name).includes(t)));
  if (match) return match;

  // Secondary fallback for female: pick any non-Thomas voice
  if (!preferMale) {
    const nonMale = fr.find(v => !asciify(v.name).includes('thomas'));
    if (nonMale) return nonMale;
  }

  return fr[0];
}

function speak(text) {
  speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = 'fr-FR';
  utt.rate = SPEED_RATES[prefs.speed_pref] || 0.9;

  const voice = getFrenchVoice(prefs.voice_pref === 'male');
  if (voice) utt.voice = voice;

  playBtn.textContent = '⏸ Playing…';
  playBtn.classList.add('playing');

  utt.onend  = () => { playBtn.textContent = '▶ Replay'; playBtn.classList.remove('playing'); };
  utt.onerror = () => { playBtn.textContent = '▶ Replay'; playBtn.classList.remove('playing'); };

  speechSynthesis.speak(utt);
}

function replayCurrentItem() {
  if (currentItem) speak(currentItem.spoken);
}

playBtn.addEventListener('click', () => {
  replayCurrentItem();
  if (!answered) answerInput.focus();
});


/* ── Preferences panel ──────────────────────────────────── */

function radioValue(name) {
  const el = document.querySelector(`input[name="${name}"]:checked`);
  return el ? el.value : null;
}

function setRadio(name, value) {
  const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (el) el.checked = true;
}

async function openPrefs() {
  try {
    const resp = await fetch('/api/preferences');
    const p    = await resp.json();
    prefs = { ...prefs, ...p };
  } catch (_) { /* use last known prefs */ }

  setRadio('exercise_type', prefs.exercise_type || 'all');
  setRadio('voice_pref',    prefs.voice_pref    || 'female');
  setRadio('speed_pref',    prefs.speed_pref    || 'normal');
  sessionSizeInput.value = prefs.session_size   || 10;

  prefsOverlay.classList.remove('hidden');
}

function closePrefs() {
  prefsOverlay.classList.add('hidden');
}

prefsOpenBtn.addEventListener('click', openPrefs);
prefsCancelBtn.addEventListener('click', closePrefs);
prefsOverlay.addEventListener('click', e => {
  if (e.target === prefsOverlay) closePrefs();
});


/* ── Session ────────────────────────────────────────────── */

async function startSession() {
  prefs.exercise_type = radioValue('exercise_type') || 'all';
  prefs.voice_pref    = radioValue('voice_pref')    || 'female';
  prefs.speed_pref    = radioValue('speed_pref')    || 'normal';
  prefs.session_size  = parseInt(sessionSizeInput.value, 10) || 10;

  await fetch('/api/preferences', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(prefs),
  });

  const resp = await fetch('/api/session/start', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(prefs),
  });

  if (!resp.ok) { alert('Could not start session.'); return; }

  const status  = await resp.json();
  sessionActive = true;
  updateProgress(status);
  closePrefs();
  loadItem();
}

async function redoSession() {
  const resp = await fetch('/api/session/redo', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
  });
  if (!resp.ok) { alert('Could not redo session.'); return; }
  const status  = await resp.json();
  sessionActive = true;
  updateProgress(status);
  loadItem();
}

startSessionBtn.addEventListener('click', startSession);
redoSessionBtn.addEventListener('click',  redoSession);
newSessionBtn.addEventListener('click',   openPrefs);


/* ── Progress bar ───────────────────────────────────────── */

function updateProgress(status) {
  if (!status || !sessionActive) {
    progressArea.classList.add('hidden');
    return;
  }
  progressArea.classList.remove('hidden');
  const { answered, correct, total } = status;
  progressText.textContent =
    `${answered} / ${total} answered  •  ${correct} correct`;
  const pct = total > 0 ? (answered / total) * 100 : 0;
  progressFill.style.width = pct + '%';
}


/* ── Load next item ─────────────────────────────────────── */

async function loadItem() {
  if (pendingComplete) {
    showComplete(pendingComplete);
    pendingComplete = null;
    return;
  }

  answered = false;
  nextBtn.classList.add('hidden');
  completeCard.classList.add('hidden');
  exerciseCard.classList.remove('hidden');

  // Reset card UI
  resultArea.classList.add('hidden');
  answerArea.classList.remove('hidden');
  resultMsg.textContent      = '';
  resultMsg.className        = 'result-msg';
  correctDisplay.textContent = '';
  answerInput.value          = '';
  answerInput.disabled       = false;
  submitBtn.disabled         = false;
  playBtn.textContent        = '▶ Play';
  playBtn.classList.remove('playing');

  const resp = await fetch('/api/item');
  if (!resp.ok) {
    promptTextEl.textContent = 'Error loading item.';
    return;
  }

  currentItem = await resp.json();
  promptTextEl.textContent = currentItem.prompt;
  hintTextEl.textContent   = currentItem.hint || '';
  // Show € label only for price exercises
  euroSymbol.classList.toggle('hidden', currentItem.type !== 'price');

  // Auto-play, waiting for voices to be ready if needed
  speakWhenReady(currentItem.spoken);

  answerInput.focus();
}


/* ── Submit answer ──────────────────────────────────────── */

async function submitAnswer() {
  if (answered || !currentItem) return;
  const userAnswer = answerInput.value.trim();
  if (!userAnswer) { answerInput.focus(); return; }

  answered = true;
  answerInput.disabled = true;
  submitBtn.disabled   = true;

  const resp = await fetch('/api/answer', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ answer: userAnswer }),
  });

  const result = await resp.json();

  // Show result
  answerArea.classList.add('hidden');
  resultArea.classList.remove('hidden');

  if (result.correct) {
    resultMsg.textContent = '✓ Correct !';
    resultMsg.classList.add('correct');
    correctDisplay.textContent = result.display;
  } else {
    resultMsg.textContent = `✗ You typed: ${userAnswer}`;
    resultMsg.classList.add('wrong');
    correctDisplay.textContent = result.display;
  }

  const ss = result.session_status;
  if (ss) {
    updateProgress(ss);
    if (ss.complete) pendingComplete = ss;
  }

  nextBtn.classList.remove('hidden');
  nextBtn.focus();
}

function showComplete(ss) {
  exerciseCard.classList.add('hidden');
  nextBtn.classList.add('hidden');
  completeMsgEl.textContent =
    `Session complete!  ${ss.correct} / ${ss.total} correct.`;
  completeCard.classList.remove('hidden');
  sessionActive = false;
}

submitBtn.addEventListener('click', submitAnswer);
answerInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitAnswer();
});
nextBtn.addEventListener('click', loadItem);

document.addEventListener('keydown', e => {
  if (e.key === 'r' || e.key === 'R') {
    // Only fire when focus is not inside the answer input
    if (document.activeElement !== answerInput) replayCurrentItem();
  }
});


/* ── Init ───────────────────────────────────────────────── */

async function init() {
  const resp   = await fetch('/api/session/status');
  const status = await resp.json();
  if (status.active && !status.complete) {
    sessionActive = true;
    updateProgress(status);
    loadItem();
  } else {
    openPrefs();
  }
}

init();
