/* app.js — Vergi Köməkçisi frontend */

const $ = (id) => document.getElementById(id);

const scroller    = $('sheet-scroll');
const entries     = $('chat-messages');
const cover       = $('empty-state');
const form        = $('composer');
const input       = $('query-input');
const sendBtn     = $('send-btn');
const historyList = $('history-list');

let busy = false;
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
const scrollMode = () => (reduceMotion.matches ? 'auto' : 'smooth');
const announce = (msg) => { const a = $('announcer'); a.textContent = ''; setTimeout(() => (a.textContent = msg), 50); };
let counter = 0;          // unique id per entry (for note anchors)

// ── Boot ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadHistory();
  autoResize();

  document.querySelectorAll('.topic').forEach((b) =>
    b.addEventListener('click', () => { setQuery(b.dataset.q); send(); })
  );

  $('brand').addEventListener('click', (e) => {
    // Plain click returns to the start screen in place; Ctrl/Cmd-click still opens a new tab.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    goHome();
  });

  $('register-toggle').addEventListener('click', () => setDrawer(!document.body.classList.contains('register-open')));
  $('register-scrim').addEventListener('click', () => setDrawer(false));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.body.classList.contains('register-open')) setDrawer(false, true);
  });

  // About panel: native <dialog> gives focus trapping and Esc-to-close for free.
  const about = $('about');
  $('about-toggle').addEventListener('click', () => { loadAbout(); about.showModal(); });
  $('about-close').addEventListener('click', () => about.close());
  about.addEventListener('click', (e) => { if (e.target === about) about.close(); });   // backdrop
});

// Fill the panel with live config from the server; the HTML defaults stay if it fails.
let aboutLoaded = false;
async function loadAbout() {
  if (aboutLoaded) return;
  try {
    const res = await fetch('/about');
    if (!res.ok) return;
    const d = await res.json();
    const fmt = (k, v) => (k === 'db_docs' ? String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : String(v));
    document.querySelectorAll('[data-about]').forEach((el) => {
      const k = el.dataset.about;
      if (d[k] !== undefined && d[k] !== null) el.textContent = fmt(k, d[k]);
    });
    aboutLoaded = true;
  } catch { /* keep defaults */ }
}

// Back to the start screen: clear the conversation, show the cover, scroll to top.
function goHome() {
  activeTyper?.finish();
  entries.innerHTML = '';
  cover.hidden = false;
  setDrawer(false);
  input.value = '';
  autoResize();
  scroller.scrollTo({ top: 0, behavior: scrollMode() });
  input.focus();
  announce('Əsas səhifə.');
}

function setDrawer(open, returnFocus = false) {
  document.body.classList.toggle('register-open', open);
  $('register-toggle').setAttribute('aria-expanded', String(open));
  if (open) historyList.querySelector('button')?.focus();
  else if (returnFocus) $('register-toggle').focus();
}

async function loadHistory() {
  try {
    const data = await (await fetch("/history?n=60")).json();
    // Newest first; show each question once even if it was asked repeatedly.
    const seen = new Set();
    const qs = (data.queries || []).filter((e) => {
      const key = e.query.trim().toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    historyList.innerHTML = '';
    qs.forEach((e) => {
      const li = document.createElement('li');
      li.innerHTML = `<button type="button" class="register-item"><span>${esc(e.query)}</span></button>`;
      li.querySelector('button').onclick = () => {
        setQuery(e.query);
        setDrawer(false);
      };
      historyList.appendChild(li);
    });
  } catch { /* history is optional */ }
}

// ── Composer ──────────────────────────────────────────────
input.addEventListener('keydown', (e) => {
  // Don't submit while an IME is still composing (e.g. Turkish/Azeri layouts with dead keys).
  if (e.key !== 'Enter' || e.shiftKey || e.isComposing || e.keyCode === 229) return;
  e.preventDefault();
  if (!e.repeat) send();
});
input.addEventListener('input', autoResize);
form.addEventListener('submit', (e) => { e.preventDefault(); send(); });

function autoResize() {
  input.style.height = 'auto';
  const h = input.scrollHeight + 1;   // +1 for the bottom rule
  input.style.height = Math.min(h, 180) + 'px';
  input.style.overflowY = h > 180 ? 'auto' : 'hidden';
}
function setQuery(text) { input.value = text; autoResize(); input.focus(); }

// ── Ask ───────────────────────────────────────────────────
async function send() {
  const query = input.value.trim();
  if (!query || busy) return;

  busy = true;
  sendBtn.disabled = true;
  cover.hidden = true;
  input.value = '';
  autoResize();

  counter += 1;
  const entry = buildEntry(counter, query);
  entries.appendChild(entry.el);
  entry.el.scrollIntoView({ behavior: scrollMode(), block: 'start' });
  announce('Sorğu göndərildi, cavab hazırlanır.');

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    if (!res.ok) {
      let msg = 'Server xətası (' + res.status + ')';
      try { msg = (await res.json()).detail || msg; } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    await fillEntry(entry, data);
    announce(`Cavab hazırdır. ${data.sources?.length || 0} mənbə.`);
    loadHistory();
  } catch (err) {
    entry.answer.innerHTML = `<p class="answer--error">Cavab alınmadı: ${esc(err.message)}</p>`;
    entry.notes.remove();
    announce('Xəta: cavab alınmadı.');
  } finally {
    entry.el.removeAttribute('aria-busy');
    busy = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

function buildEntry(no, query) {
  const el = document.createElement('article');
  el.className = 'entry';
  el.dataset.no = no;
  el.setAttribute('aria-busy', 'true');
  el.setAttribute('aria-labelledby', `q-${no}`);
  el.innerHTML = `
    <h3 class="entry-q" id="q-${no}">${esc(query)}</h3>
    <div class="reply">
      <div class="bot"><svg class="bot-star" aria-hidden="true"><use href="#star" /></svg>Köməkçi</div>
      <div class="answer">
        <div class="pending" aria-hidden="true">Arxivdə oxşar izahlar axtarılır…</div>
      </div>
    </div>
    <aside class="notes" aria-label="Mənbələr"></aside>`;
  return {
    el,
    answer: el.querySelector('.answer'),
    notes: el.querySelector('.notes'),
  };
}

async function fillEntry(entry, data) {
  const sources = data.sources || [];
  entry.answer.innerHTML = renderAnswer(data.answer);
  await typeOut(entry.answer);

  if (!sources.length) entry.notes.remove();
  else {
    entry.notes.insertAdjacentHTML('beforeend', '<div class="notes-head">Mənbələr</div>');
    sources.forEach((s, i) => entry.notes.appendChild(buildNote(s, i, entry.el.dataset.no)));
  }

  wireCitations(entry);
}

function buildNote(s, i, no) {
  const note = document.createElement('div');
  note.className = 'note';
  note.dataset.rank = s.rank;
  note.id = `n${no}-${s.rank}`;
  note.tabIndex = -1;
  note.style.animationDelay = 150 + i * 80 + 'ms';
  note.innerHTML = `
    <div class="note-q"><span class="note-no">${s.rank}</span>${esc(s.question)}</div>
    <div class="note-a">${esc(s.answer)}</div>
    <button type="button" class="note-more" aria-expanded="false">tam mətn</button>
    ${s.source_url ? `<a class="note-link" href="${esc(s.source_url)}" target="_blank" rel="noopener">${s.answer_date ? esc(s.answer_date) + ' · ' : ''}orijinal<span class="sr-only"> (yeni pəncərədə)</span></a>` : ''}`;

  const more = note.querySelector('.note-more');
  const body = note.querySelector('.note-a');
  requestAnimationFrame(() => { if (body.scrollHeight <= body.clientHeight + 2) more.remove(); });
  more.onclick = () => {
    const open = note.classList.toggle('open');
    more.textContent = open ? 'qısalt' : 'tam mətn';
    more.setAttribute('aria-expanded', String(open));
  };
  return note;
}

// Footnote markers ↔ margin notes
function wireCitations(entry) {
  const find = (r) => entry.notes.querySelector(`.note[data-rank="${r}"]`);
  entry.answer.querySelectorAll('.cite').forEach((c) => {
    const note = find(c.dataset.ref);
    if (!note) { c.replaceWith(document.createTextNode(c.textContent)); return; }
    c.href = '#' + note.id;
    c.setAttribute('aria-label', `Mənbə ${c.dataset.ref}`);
    const on = () => { c.classList.add('on'); note.classList.add('on'); };
    const off = () => { c.classList.remove('on'); note.classList.remove('on'); };
    c.addEventListener('mouseenter', on);
    c.addEventListener('mouseleave', off);
    c.addEventListener('focus', on);
    c.addEventListener('blur', off);
    c.addEventListener('click', (e) => {
      e.preventDefault();
      note.scrollIntoView({ behavior: scrollMode(), block: 'center' });
      note.focus({ preventScroll: true });
      note.classList.remove('flash'); void note.offsetWidth; note.classList.add('flash');
    });
  });
  entry.notes.querySelectorAll('.note').forEach((n) => {
    const cites = entry.answer.querySelectorAll(`.cite[data-ref="${n.dataset.rank}"]`);
    n.addEventListener('mouseenter', () => cites.forEach((c) => c.classList.add('on')));
    n.addEventListener('mouseleave', () => cites.forEach((c) => c.classList.remove('on')));
  });
}

// ── Typewriter reveal ─────────────────────────────────────
// The answer arrives whole; reveal the already-rendered HTML word by word so
// markup (lists, bold, citation markers) is intact at every frame.
// Pace adapts to length: short answers ~1.5 s, long ones capped near 2.6 s.
let activeTyper = null;   // lets a new question or a click finish the current one instantly

function typeOut(root) {
  activeTyper?.finish();
  if (reduceMotion.matches) return Promise.resolve();

  // Collect units in document order: words of text nodes, and citation markers as atoms.
  const units = [];

  const walk = (node, block) => {
    node.childNodes.forEach((n) => {
      if (n.nodeType === Node.TEXT_NODE) {
        const words = n.textContent.match(/\S+\s*|\s+/g) || [];
        if (words.length) units.push({ kind: 'text', node: n, words, block });
        n.textContent = '';
      } else if (n.nodeType === Node.ELEMENT_NODE) {
        if (n.classList.contains('cite')) { units.push({ kind: 'cite', el: n, block }); n.hidden = true; return; }
        const isBlock = /^(P|LI|UL|OL)$/.test(n.tagName);
        if (isBlock) { n.classList.add('tw-wait'); }
        walk(n, isBlock ? n : block);
      }
    });
  };
  walk(root, null);

  const total = units.reduce((s, u) => s + (u.kind === 'text' ? u.words.join('').length : 2), 0);
  if (!total) return Promise.resolve();
  const cps = Math.min(Math.max(total / 2.6, 220), 900);   // characters per second

  const caret = document.createElement('span');
  caret.className = 'tw-caret';
  caret.setAttribute('aria-hidden', 'true');
  root.classList.add('typing');

  const show = (block) => {
    for (let b = block; b && b !== root; b = b.parentElement) b.classList.remove('tw-wait');
  };

  let ui = 0, wi = 0, shown = 0, raf = 0, resolve;
  const done = new Promise((r) => (resolve = r));

  const step = (budget) => {
    while (shown < budget && ui < units.length) {
      const u = units[ui];
      show(u.block);
      if (u.kind === 'cite') {
        u.el.hidden = false;
        u.el.after(caret);
        shown += 2; ui += 1;
        continue;
      }
      const w = u.words[wi++];
      u.node.textContent += w;
      u.node.after(caret);
      shown += w.length;
      if (wi >= u.words.length) { ui += 1; wi = 0; }
    }
  };

  const finish = () => {
    if (activeTyper !== typer) return;
    activeTyper = null;
    cancelAnimationFrame(raf);
    step(Infinity);
    caret.remove();
    root.classList.remove('typing');
    root.removeEventListener('click', finish);
    resolve();
  };
  const typer = { finish };
  activeTyper = typer;
  root.addEventListener('click', finish);   // click to skip

  const start = performance.now();
  const tick = (now) => {
    step(((now - start) / 1000) * cps);
    if (ui >= units.length) finish();
    else raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return done;
}

// ── Lightweight markdown → HTML ───────────────────────────
// Groups consecutive lines into <p>, <ul> or <ol>; a blank line closes a paragraph.
function renderAnswer(text) {
  const UL = /^\s*[-*•]\s+/;
  const OL = /^\s*\d+[.)]\s+/;
  const out = [];
  let kind = null, buf = [];

  const flush = () => {
    if (!buf.length) return;
    if (kind === 'p') out.push(`<p>${buf.map(inline).join('<br>')}</p>`);
    else out.push(`<${kind}>${buf.map((l) => `<li>${inline(l)}</li>`).join('')}</${kind}>`);
    buf = []; kind = null;
  };

  String(text || '').trim().split('\n').forEach((line) => {
    if (!line.trim()) { flush(); return; }
    const k = UL.test(line) ? 'ul' : OL.test(line) ? 'ol' : 'p';
    if (k !== kind) flush();
    kind = k;
    buf.push(k === 'ul' ? line.replace(UL, '') : k === 'ol' ? line.replace(OL, '') : line);
  });
  flush();
  return out.join('');
}

function inline(s) {
  let out = esc(s);
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, '$1<em>$2</em>');
  // [Mənbə 1], [Mənbə 1, 2], [Mənbə 1, Mənbə 3] → superscript markers
  out = out.replace(/\[\s*Mənbə[^\]]*\]/gi, (m) =>
    (m.match(/\d+/g) || []).map((n) => `<a class="cite" data-ref="${n}">${n}</a>`).join('')
  );
  return out;
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
