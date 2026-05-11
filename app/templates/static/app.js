/* app.js — Vergi Chatbotu frontend logic */

const chatMessages  = document.getElementById('chat-messages');
const emptyState    = document.getElementById('empty-state');
const queryInput    = document.getElementById('query-input');
const sendBtn       = document.getElementById('send-btn');
const historyList   = document.getElementById('history-list');
const dbCount       = document.getElementById('db-count');
const statusDot     = document.getElementById('status-dot');
const statusText    = document.getElementById('status-text');

let isLoading = false;

// ── On load ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadHistory();
  autoResize(queryInput);
});

// ── Health check ──────────────────────────────────────────
async function checkHealth() {
  try {
    const res  = await fetch('/health');
    const data = await res.json();

    dbCount.textContent = data.db_docs.toLocaleString() + ' sənəd';

    const dot  = statusDot.querySelector('.dot');
    dot.className = 'dot dot--ok';
    statusText.textContent = 'Hazır';
  } catch (e) {
    const dot = statusDot.querySelector('.dot');
    dot.className = 'dot dot--error';
    statusText.textContent = 'Xəta';
  }
}

// ── History ───────────────────────────────────────────────
async function loadHistory() {
  try {
    const res  = await fetch('/history?n=20');
    const data = await res.json();

    if (!data.queries || data.queries.length === 0) return;

    historyList.innerHTML = '';
    data.queries.forEach(entry => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <div class="history-query">${escapeHtml(entry.query)}</div>
        <div class="history-meta">${entry.retrieval_ms}ms + ${entry.llm_ms}ms</div>
      `;
      item.onclick = () => fillQueryText(entry.query);
      historyList.appendChild(item);
    });
  } catch (e) {
    // silently fail — history is non-critical
  }
}

// ── Input handling ────────────────────────────────────────
queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!isLoading) sendQuery();
  }
});

queryInput.addEventListener('input', () => autoResize(queryInput));

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function fillQuery(btn) {
  queryInput.value = btn.textContent;
  autoResize(queryInput);
  queryInput.focus();
}

function fillQueryText(text) {
  queryInput.value = text;
  autoResize(queryInput);
  queryInput.focus();
}

// ── Send query ────────────────────────────────────────────
async function sendQuery() {
  const query = queryInput.value.trim();
  if (!query || isLoading) return;

  // Hide empty state on first message
  emptyState.style.display = 'none';

  // Lock input
  isLoading = true;
  sendBtn.disabled = true;
  queryInput.value = '';
  autoResize(queryInput);

  // Add user bubble
  appendMessage('user', query);

  // Add loading bubble
  const loadingId = 'loading-' + Date.now();
  appendLoading(loadingId);

  try {
    const res  = await fetch('/ask', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ query }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Server error');
    }

    const data = await res.json();

    // Remove loading bubble
    document.getElementById(loadingId)?.remove();

    // Add bot answer
    appendBotMessage(data);

    // Refresh history sidebar
    loadHistory();

  } catch (e) {
    document.getElementById(loadingId)?.remove();
    appendMessage('bot', `⚠️ Xəta: ${e.message}`);
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    queryInput.focus();
  }
}

// ── DOM helpers ───────────────────────────────────────────
function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message message--${role}`;
  div.innerHTML = `
    <div class="message-bubble">${role === 'bot' ? formatText(text) : escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function appendLoading(id) {
  const div = document.createElement('div');
  div.id        = id;
  div.className = 'message message--bot';
  div.innerHTML = `
    <div class="message-bubble message-bubble--loading">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function appendBotMessage(data) {
  const div = document.createElement('div');
  div.className = 'message message--bot';

  // Answer bubble
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = formatText(data.answer);
  div.appendChild(bubble);

  // Sources panel
  if (data.sources && data.sources.length > 0) {
    const panel = buildSourcesPanel(data.sources);
    div.appendChild(panel);
  }

  // Timing bar
  const timing = document.createElement('div');
  timing.className = 'timing-bar';
  timing.innerHTML = `
    <span class="timing-item">
      <span class="timing-label">retrieval</span>
      <span class="timing-val">${Math.round(data.retrieval_ms)}ms</span>
    </span>
    <span class="timing-item">
      <span class="timing-label">llm</span>
      <span class="timing-val">${Math.round(data.llm_ms)}ms</span>
    </span>
    <span class="timing-item">
      <span class="timing-label">mənbə</span>
      <span class="timing-val">${data.sources.length}</span>
    </span>
  `;
  div.appendChild(timing);

  chatMessages.appendChild(div);
  scrollToBottom();
}

function buildSourcesPanel(sources) {
  const panel = document.createElement('div');
  panel.className = 'sources-panel';

  const toggle = document.createElement('button');
  toggle.className = 'sources-toggle';
  toggle.innerHTML = `
    <span>${sources.length} mənbə tapıldı</span>
    <span class="arrow">▼</span>
  `;

  const content = document.createElement('div');
  content.className = 'sources-content';

  sources.forEach(s => {
    const item = document.createElement('div');
    item.className = 'source-item';
    item.innerHTML = `
      <div class="source-header">
        <span class="source-rank">#${s.rank}</span>
        <span class="source-sim">${Math.round(s.similarity * 100)}% uyğun</span>
        <span class="source-date">${s.answer_date}</span>
      </div>
      <div class="source-q">${escapeHtml(s.question)}</div>
      <div class="source-a">${escapeHtml(s.answer)}</div>
    `;
    content.appendChild(item);
  });

  toggle.onclick = () => {
    const isOpen = content.classList.toggle('open');
    toggle.classList.toggle('open', isOpen);
  };

  panel.appendChild(toggle);
  panel.appendChild(content);
  return panel;
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Text formatting ───────────────────────────────────────
function formatText(text) {
  // Escape HTML first
  let safe = escapeHtml(text);

  // Bold: **text**
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Newlines to <br>
  safe = safe.replace(/\n/g, '<br>');

  return safe;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
