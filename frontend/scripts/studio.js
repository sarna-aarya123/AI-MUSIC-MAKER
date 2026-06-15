// ── State ──────────────────────────────────────────────────────────────────────
console.log("STUDIO JS LOADED");
let midiB64 = null;

// ── Transport state ────────────────────────────────────────────────────────────
const T = {
  isPlaying:   false,
  currentBeat: 0,
  startWall:   0,      // performance.now() when we began playing from startBeat
  startBeat:   0,      // beat position at the moment play() was called
  bpm:         120,
  totalBeats:  16,
  beatsPerBar: 4,
  loop:        true,
  rafId:       null,
};

// Live playhead/highlight elements — rebuilt after each render
let playheadEls     = [];
let barHighlightEls = [];
let rulerPlayhead   = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const btnGenerate     = document.getElementById('btn-generate');
const btnDownload     = document.getElementById('btn-download');
const btnPlay         = document.getElementById('btn-play');
const btnLoop         = document.getElementById('btn-loop');
const statusEl        = document.getElementById('status-text');
const emptyState      = document.getElementById('empty-state');
const tracksContainer = document.getElementById('tracks-container');
const debugPanel      = document.getElementById('debug-panel');
const dbgBpm          = document.getElementById('dbg-bpm');
const dbgTotal        = document.getElementById('dbg-total');
const dbgBeat         = document.getElementById('dbg-beat');
const dbgBar          = document.getElementById('dbg-bar');

// ── Params ────────────────────────────────────────────────────────────────────
function getParams() {
  return {
    key:   document.getElementById('ctrl-key').value,
    mode:  document.getElementById('ctrl-mode').value,
    genre: document.getElementById('ctrl-genre').value,
    bpm:   parseInt(document.getElementById('ctrl-bpm').value, 10),
    bars:  parseInt(document.getElementById('ctrl-bars').value, 10),
    seed:  Math.floor(Math.random() * 99999),
  };
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function generateSong() {
  console.log("GENERATE FUNCTION FIRED");
  if (T.isPlaying) stopTransport();
  btnGenerate.disabled = true;
  btnGenerate.textContent = 'Generating…';
  setStatus('Composing…');

  try {
    console.log("1: BEFORE PARAMS");
    const params = getParams();
    console.log("2: AFTER PARAMS", params);

    console.log("3: BEFORE FETCH");

    const res = await fetch('/api/generate/composition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    console.log("4: AFTER FETCH", res);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || `HTTP ${res.status}`);
    }

    const data = await res.json();
    midiB64 = data.midi;
    console.log("FINAL DATA:", data);

    // Sync transport to new composition
    T.bpm         = data.bpm;
    T.totalBeats  = data.total_beats;
    T.beatsPerBar = data.time_signature?.[0] ?? 4;
    T.currentBeat = 0;
    T.startBeat   = 0;

    renderAll(data);
    AudioScheduler.load(data);    // prime event queue for playback
    initEditorFromData(data);     // Phase 4: wire editing state + interactions

    btnDownload.disabled = false;
    btnPlay.disabled     = false;
    btnLoop.disabled     = false;

    // Populate debug panel
    if (dbgBpm)   dbgBpm.textContent   = data.bpm;
    if (dbgTotal) dbgTotal.textContent = data.total_beats.toFixed(0);
    if (dbgBeat)  dbgBeat.textContent  = '0.00';
    if (dbgBar)   dbgBar.textContent   = '1';

    setStatus(
      `${data.key} ${data.mode} · ${data.genre} · ${data.bpm} BPM · ` +
      `${data.bars} bars · ${data.summary.note_count} notes`
    );
  } catch (err) {
    setStatus(`Error: ${err.message}`, true);
    console.error(err);
  } finally {
    btnGenerate.disabled = false;
    btnGenerate.textContent = 'Generate Song';
  }
}

// ── Render all ────────────────────────────────────────────────────────────────
function renderAll(data) {
  console.log("RENDERALL CALLED");
  const tb = data.total_beats;
  renderRuler(tb, data.bars);
  renderChords(data.chord_data.chords, tb, data.chord_data.progression_name);
  renderMelody(data.melody_data?.notes ?? [], tb);
  renderDrums(data.drum_data?.events ?? [], tb, data.genre);

  emptyState.hidden = true;
  tracksContainer.hidden = false;

  setupPlayheadElements();
}

// ── Ruler ─────────────────────────────────────────────────────────────────────
function renderRuler(totalBeats, bars) {
  const ruler = document.getElementById('ruler');
  ruler.innerHTML = '';
  const numBars = bars ?? Math.round(totalBeats / 4);
  for (let i = 0; i < numBars; i++) {
    const mark = document.createElement('span');
    mark.className = 'ruler-mark';
    mark.textContent = i + 1;
    mark.style.left = `${(i / numBars) * 100}%`;
    ruler.appendChild(mark);
  }
  // rulerPlayhead re-created in setupPlayheadElements
}

// ── Grid lines ────────────────────────────────────────────────────────────────
function addGrid(container, totalBeats) {
  for (let b = 1; b < totalBeats; b++) {
    const line = document.createElement('div');
    line.className = b % 4 === 0 ? 'grid-bar' : 'grid-beat';
    line.style.left = `${(b / totalBeats) * 100}%`;
    container.appendChild(line);
  }
}

// ── Chords ────────────────────────────────────────────────────────────────────
function renderChords(chords, totalBeats, progressionName) {
  const clip = document.getElementById('clip-chords');
  const meta = document.getElementById('meta-chords');
  clip.innerHTML = '';
  addGrid(clip, totalBeats);
  meta.textContent = progressionName ?? `${chords.length} chords`;

  for (const chord of chords) {
    const left  = (chord.beat_start    / totalBeats) * 100;
    const width = (chord.beat_duration / totalBeats) * 100;

    const el = document.createElement('div');
    el.className = 'chord-block';
    el.style.left  = `${left}%`;
    el.style.width = `calc(${width}% - 3px)`;
    el.title = `${chord.label} (${chord.quality}) · beat ${chord.beat_start}`;
    el.innerHTML = `
      <span class="chord-name">${chord.label}</span>
      <span class="chord-degree">${chord.degree_label}</span>
    `;
    clip.appendChild(el);
  }
}

// ── Melody ────────────────────────────────────────────────────────────────────
function renderMelody(notes, totalBeats) {
  const clip = document.getElementById('clip-melody');
  const meta = document.getElementById('meta-melody');
  clip.innerHTML = '';
  addGrid(clip, totalBeats);
  meta.textContent = notes.length ? `${notes.length} notes` : 'empty';
  if (!notes.length) return;

  const pitches = notes.map(n => n.pitch);
  const lo = Math.min(...pitches) - 1;
  const hi = Math.max(...pitches) + 1;
  const range = hi - lo || 1;

  for (const note of notes) {
    const left   = (note.beat / totalBeats) * 100;
    const w      = Math.max(0.4, (note.duration / totalBeats) * 100);
    const bottom = ((note.pitch - lo) / range) * 78 + 6;
    const alpha  = 0.45 + (note.velocity / 127) * 0.55;

    const el = document.createElement('div');
    el.className = 'melody-note';
    el.style.cssText = `left:${left}%;width:calc(${w}% - 1px);bottom:${bottom}%;opacity:${alpha}`;
    el.title = `${note.pitch_name} vel:${note.velocity} beat:${note.beat.toFixed(2)}`;
    clip.appendChild(el);
  }
}

// ── Drums ─────────────────────────────────────────────────────────────────────
const DRUM_ORDER = ['crash', 'ride', 'open_hat', 'hihat', 'rim', 'snare', 'kick'];
const DRUM_SHORT = {
  kick: 'KICK', snare: 'SNRE', hihat: 'HHAT', open_hat: 'OHAT',
  ride: 'RIDE', crash: 'CRSH', rim: 'RIM',
};
const DRUM_COLOR = {
  kick: '#e05252', snare: '#e09b34', hihat: '#4fa8d8',
  open_hat: '#4db87f', ride: '#9b6fd4', crash: '#3dcfc9', rim: '#e07d3c',
};

function renderDrums(events, totalBeats, genre) {
  const clip = document.getElementById('clip-drums');
  const meta = document.getElementById('meta-drums');
  clip.innerHTML = '';
  meta.textContent = genre ?? '';
  if (!events.length) return;

  const present = new Set(events.map(e => e.drum_type));
  const voices = DRUM_ORDER.filter(v => present.has(v));
  for (const v of present) if (!voices.includes(v)) voices.push(v);

  const hitAreas = {};
  for (const voice of voices) {
    const row = document.createElement('div');
    row.className = 'drum-row';

    const lbl = document.createElement('div');
    lbl.className = 'drum-row-label';
    lbl.textContent = DRUM_SHORT[voice] ?? voice.slice(0, 4).toUpperCase();
    lbl.style.color = DRUM_COLOR[voice] ?? '#999';

    const hits = document.createElement('div');
    hits.className = 'drum-row-hits';
    addGrid(hits, totalBeats);

    row.appendChild(lbl);
    row.appendChild(hits);
    clip.appendChild(row);
    hitAreas[voice] = hits;
  }

  for (const ev of events) {
    const area = hitAreas[ev.drum_type];
    if (!area) continue;

    const left  = (ev.beat / totalBeats) * 100;
    const alpha = 0.5 + (ev.velocity / 127) * 0.5;
    const color = DRUM_COLOR[ev.drum_type] ?? '#aaa';

    const hit = document.createElement('div');
    hit.className = 'drum-hit';
    hit.style.cssText = `left:${left}%;background:${color};opacity:${alpha}`;
    hit.title = `${ev.drum_type} vel:${ev.velocity} beat:${ev.beat.toFixed(2)}`;
    area.appendChild(hit);
  }
}

// ── Playhead setup ─────────────────────────────────────────────────────────────
// Chords + Melody: one playhead per clip (clip has no sub-columns)
// Drums: one playhead per .drum-row-hits so it aligns with the beat data,
//        not the 48px label column.
function setupPlayheadElements() {
  playheadEls     = [];
  barHighlightEls = [];
  rulerPlayhead   = null;

  for (const clipId of ['clip-chords', 'clip-melody']) {
    const clip = document.getElementById(clipId);
    if (!clip) continue;
    barHighlightEls.push(_insertHighlight(clip));
    playheadEls.push(_insertPlayhead(clip));
  }

  const drumClip = document.getElementById('clip-drums');
  if (drumClip) {
    const hitAreas = drumClip.querySelectorAll('.drum-row-hits');
    for (const area of hitAreas) {
      barHighlightEls.push(_insertHighlight(area));
      playheadEls.push(_insertPlayhead(area));
    }
  }

  const ruler = document.getElementById('ruler');
  if (ruler) {
    rulerPlayhead = document.createElement('div');
    rulerPlayhead.className = 'playhead-ruler';
    ruler.appendChild(rulerPlayhead);
  }

  updatePlayhead(T.currentBeat);
}

function _insertHighlight(parent) {
  const el = document.createElement('div');
  el.className = 'bar-highlight';
  parent.insertBefore(el, parent.firstChild);
  return el;
}

function _insertPlayhead(parent) {
  const el = document.createElement('div');
  el.className = 'playhead-line';
  parent.appendChild(el);
  return el;
}

// ── Timeline engine ────────────────────────────────────────────────────────────
function tick(now) {
  if (!T.isPlaying) return;

  const elapsed = (now - T.startWall) / 1000;
  let beat = T.startBeat + elapsed * (T.bpm / 60);

  if (beat >= T.totalBeats) {
    if (T.loop) {
      T.startWall = now;
      T.startBeat = 0;
      beat = 0;
    } else {
      stopTransport();
      return;
    }
  }

  T.currentBeat = beat;
  updatePlayhead(beat);
  AudioScheduler.process(beat, T.bpm);
  T.rafId = requestAnimationFrame(tick);
}

function updatePlayhead(beat) {
  const pct = `${(beat / T.totalBeats) * 100}%`;
  for (const el of playheadEls)    el.style.left = pct;
  if (rulerPlayhead)                rulerPlayhead.style.left = pct;

  // Bar highlight: snap to the start of the current bar
  const bar    = Math.floor(beat / T.beatsPerBar);
  const barPct = `${(bar * T.beatsPerBar / T.totalBeats) * 100}%`;
  const barW   = `${(T.beatsPerBar      / T.totalBeats) * 100}%`;
  for (const el of barHighlightEls) {
    el.style.left  = barPct;
    el.style.width = barW;
  }

  if (dbgBeat) dbgBeat.textContent = beat.toFixed(2);
  if (dbgBar)  dbgBar.textContent  = bar + 1;
}

async function playTransport() {
  if (T.totalBeats === 0 || btnPlay.disabled) return;
  await Tone.start();   // resume AudioContext on first user gesture (idempotent)
  AudioEngine.init();   // build instruments if not already built (idempotent)
  T.isPlaying = true;
  T.startWall = performance.now();
  T.startBeat = T.currentBeat;
  btnPlay.textContent = '■';
  btnPlay.title = 'Stop  (Space)';
  btnPlay.classList.add('playing');
  T.rafId = requestAnimationFrame(tick);
}

function stopTransport() {
  T.isPlaying   = false;
  T.currentBeat = 0;
  T.startBeat   = 0;
  if (T.rafId) { cancelAnimationFrame(T.rafId); T.rafId = null; }
  updatePlayhead(0);
  AudioScheduler.reset();
  btnPlay.textContent = '▶';
  btnPlay.title = 'Play  (Space)';
  btnPlay.classList.remove('playing');
}

function togglePlay() {
  if (T.isPlaying) stopTransport();
  else             playTransport();
}

// ── Download ──────────────────────────────────────────────────────────────────
function downloadMidi() {
  if (!midiB64) return;
  const bytes = atob(midiB64);
  const buf   = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);
  const blob = new Blob([buf], { type: 'audio/midi' });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), {
    href: url,
    download: buildFilename(),
  });
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function buildFilename() {
  const p = getParams();
  return `${p.key}-${p.mode}-${p.genre}-${p.bpm}bpm.mid`;
}

// ── Status ────────────────────────────────────────────────────────────────────
function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.style.color = isError ? '#e05252' : '';
}

// ── Wire up ───────────────────────────────────────────────────────────────────
btnGenerate.addEventListener('click', generateSong);
btnDownload.addEventListener('click', downloadMidi);

btnPlay.addEventListener('click', togglePlay);

btnLoop.addEventListener('click', () => {
  T.loop = !T.loop;
  btnLoop.classList.toggle('active', T.loop);
  btnLoop.title = T.loop
    ? 'Loop on — click to disable'
    : 'Loop off — click to enable';
});

document.getElementById('btn-debug')?.addEventListener('click', () => {
  if (debugPanel) debugPanel.hidden = !debugPanel.hidden;
});
document.getElementById('dbg-close')?.addEventListener('click', () => {
  if (debugPanel) debugPanel.hidden = true;
});

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); if (!btnPlay.disabled) togglePlay(); }
  if (e.code === 'KeyD')  { if (debugPanel) debugPanel.hidden = !debugPanel.hidden; }
});

// Boot state: loop on by default
btnLoop.classList.add('active');
