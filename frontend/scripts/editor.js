// ── Phase 4 — Interactive Editor ──────────────────────────────────────────────
// Layered on top of the existing transport / audio / render system.
//
// CONTRACT:
//   NEVER touches: T, tick(), updatePlayhead(), AudioScheduler.process()
//   ALWAYS uses:   DAW_STATE as editing source; patchScheduler() to push changes
//
// Public surface:
//   initEditorFromData(data)  — call after renderAll() + AudioScheduler.load()
//   patchScheduler(stop?)     — rebuild scheduler queue from DAW_STATE
//   snapBeat(b, grid)         — utility, visible to console for debugging

// ── Instrument presets ────────────────────────────────────────────────────────
const PRESETS = {
  melody: {
    'piano':    { oscillator: { type: 'triangle8' }, envelope: { attack: 0.02,  decay: 0.10, sustain: 0.35, release: 0.50 } },
    'synth':    { oscillator: { type: 'sawtooth'  }, envelope: { attack: 0.008, decay: 0.12, sustain: 0.40, release: 0.30 } },
    'pluck':    { oscillator: { type: 'triangle'  }, envelope: { attack: 0.001, decay: 0.25, sustain: 0.00, release: 0.20 } },
    'soft pad': { oscillator: { type: 'sine'      }, envelope: { attack: 0.30,  decay: 0.20, sustain: 0.80, release: 1.50 } },
  },
  chords: {
    'piano':    { oscillator: { type: 'sine'      }, envelope: { attack: 0.06,  decay: 0.30, sustain: 0.45, release: 1.20 } },
    'synth':    { oscillator: { type: 'sawtooth'  }, envelope: { attack: 0.02,  decay: 0.20, sustain: 0.50, release: 0.50 } },
    'pluck':    { oscillator: { type: 'triangle'  }, envelope: { attack: 0.001, decay: 0.40, sustain: 0.00, release: 0.30 } },
    'soft pad': { oscillator: { type: 'sine'      }, envelope: { attack: 0.40,  decay: 0.20, sustain: 0.80, release: 2.00 } },
  },
};

// ── DAW_STATE ─────────────────────────────────────────────────────────────────
const DAW_STATE = {
  notes:       [],                   // melody notes — editable
  chords:      [],                   // chord events — editable
  drums:       [],                   // drum events  — read-only (no edit UI yet)
  pitchRange:  { lo: 59, hi: 85 },  // MIDI bounds for piano-roll hit-test
  totalBeats:  16,
  beatsPerBar: 4,
  bpm:         120,
  muted:       new Set(),            // track names currently muted
  soloed:      new Set(),            // track names currently soloed
  instruments: { melody: 'piano', chords: 'piano' },
  selectedIds: new Set(),
};

// ── Entry point ───────────────────────────────────────────────────────────────
// Called from studio.js after renderAll() + AudioScheduler.load().
function initEditorFromData(data) {
  DAW_STATE.totalBeats  = data.total_beats;
  DAW_STATE.beatsPerBar = data.time_signature?.[0] ?? 4;
  DAW_STATE.bpm         = data.bpm;
  DAW_STATE.selectedIds.clear();

  // Melody notes
  DAW_STATE.notes = (data.melody_data?.notes ?? []).map((n, i) => ({
    id: `mn-${i}`, beat: n.beat, duration: n.duration,
    pitch: n.pitch, velocity: n.velocity, _el: null,
  }));
  _recalcPitchRange();

  // Chords
  DAW_STATE.chords = (data.chord_data?.chords ?? []).map((c, i) => ({
    id: `ch-${i}`, beat_start: c.beat_start, beat_duration: c.beat_duration,
    notes: c.notes, label: c.label, degree_label: c.degree_label,
    quality: c.quality, velocity: 82, _el: null,
  }));

  // Drums (read-only — we keep them for scheduler patching)
  DAW_STATE.drums = (data.drum_data?.events ?? []).map((e, i) => ({
    id: `dr-${i}`, beat: e.beat, duration: e.duration,
    pitch: e.pitch, velocity: e.velocity, drum_type: e.drum_type,
  }));

  // Reset mute/solo UI (keep user's choices across generates if desired)
  // We intentionally do NOT clear muted/soloed here so that the user's
  // mute state survives a re-generate. Clear is only on fresh page load.

  // Link state objects → DOM elements created by renderAll()
  _wireElRefs();

  // Attach chord resize handles
  for (const chord of DAW_STATE.chords) {
    if (chord._el) _attachResizeHandle(chord);
  }

  // Wire interaction handlers (guarded — set up only once)
  _setupInteractions();

  // Rebuild track controls (M/S/instrument) — remove stale ones first
  document.querySelectorAll('.track-controls').forEach(el => el.remove());
  _setupTrackControls();
}

// ── Scheduler bridge ──────────────────────────────────────────────────────────
// Converts DAW_STATE into the flat event format AudioScheduler.patch() expects.
// Pass stopSustained=true when muting/soloing to cut held notes immediately.
function patchScheduler(stopSustained = false) {
  const active     = _getActiveTracks();
  const secPerBeat = 60 / DAW_STATE.bpm;
  const events     = [];

  if (active.has('drums')) {
    for (const ev of DAW_STATE.drums) {
      events.push({
        type: 'drum',   beat: ev.beat,
        durSec:  Math.max(0.04, ev.duration * secPerBeat),
        velocity: ev.velocity, drumType: ev.drum_type,
      });
    }
  }
  if (active.has('melody')) {
    for (const n of DAW_STATE.notes) {
      events.push({
        type: 'melody', beat: n.beat,
        durSec:  Math.max(0.05, n.duration * secPerBeat),
        pitch: n.pitch, velocity: n.velocity,
      });
    }
  }
  if (active.has('chords')) {
    for (const c of DAW_STATE.chords) {
      events.push({
        type: 'chord',  beat: c.beat_start,
        durSec:  Math.max(0.1, c.beat_duration * secPerBeat * 0.92),
        pitches: c.notes, velocity: c.velocity,
      });
    }
  }

  AudioScheduler.patch(events, T.currentBeat);
  if (stopSustained) AudioEngine.stopAll();
}

function _getActiveTracks() {
  if (DAW_STATE.soloed.size > 0) return new Set(DAW_STATE.soloed);
  const all = new Set(['chords', 'melody', 'drums']);
  for (const t of DAW_STATE.muted) all.delete(t);
  return all;
}

// ── Snap / pitch helpers ──────────────────────────────────────────────────────
function snapBeat(beat, grid = 0.25) {
  return Math.round(beat / grid) * grid;
}

function _recalcPitchRange() {
  if (DAW_STATE.notes.length === 0) {
    DAW_STATE.pitchRange = { lo: 59, hi: 85 };
    return;
  }
  const pitches = DAW_STATE.notes.map(n => n.pitch);
  DAW_STATE.pitchRange = {
    lo: Math.min(...pitches) - 3,
    hi: Math.max(...pitches) + 3,
  };
}

// Recalculates and patches the `bottom` / `left` % of every melody note element.
// Called when the pitch range changes (note added/deleted).
function _repositionAllNotes() {
  const { lo, hi } = DAW_STATE.pitchRange;
  const range = (hi - lo) || 1;
  const tb    = DAW_STATE.totalBeats;
  for (const n of DAW_STATE.notes) {
    if (!n._el) continue;
    const left   = (n.beat / tb) * 100;
    const w      = Math.max(0.4, (n.duration / tb) * 100);
    const bottom = ((n.pitch - lo) / range) * 78 + 6;
    const alpha  = 0.45 + (n.velocity / 127) * 0.55;
    n._el.style.cssText = `left:${left}%;width:calc(${w}% - 1px);bottom:${bottom}%;opacity:${alpha}`;
    n._el.title = `MIDI ${n.pitch}  beat ${n.beat.toFixed(2)}`;
  }
}

// ── Wire DOM refs ─────────────────────────────────────────────────────────────
function _wireElRefs() {
  // Notes — renderAll() creates them in the same order as data.melody_data.notes
  const noteEls  = document.querySelectorAll('#clip-melody .melody-note');
  DAW_STATE.notes.forEach((n, i) => {
    n._el = noteEls[i] ?? null;
    if (!n._el) return;
    n._el.dataset.noteId = n.id;
    n._el.addEventListener('mousedown',   e => { e.stopPropagation(); _startNoteDrag(e, n); });
    n._el.addEventListener('contextmenu', e => { e.preventDefault();  _deleteNote(n); });
  });

  // Chords
  const chordEls = document.querySelectorAll('#clip-chords .chord-block');
  DAW_STATE.chords.forEach((c, i) => {
    c._el = chordEls[i] ?? null;
    if (c._el) c._el.dataset.chordId = c.id;
  });
}

// ── Selection ─────────────────────────────────────────────────────────────────
function _selectItem(id) {
  _clearSelection();
  DAW_STATE.selectedIds.add(id);
  const item = [...DAW_STATE.notes, ...DAW_STATE.chords].find(x => x.id === id);
  item?._el?.classList.add('selected');
}

function _clearSelection() {
  for (const id of DAW_STATE.selectedIds) {
    const item = [...DAW_STATE.notes, ...DAW_STATE.chords].find(x => x.id === id);
    item?._el?.classList.remove('selected');
  }
  DAW_STATE.selectedIds.clear();
}

// ── Import: replace melody track from extracted notes ─────────────────────────
// Called by importUI.js after MelodyExtractor runs.
// newNotes: [{ beat, pitch, duration, velocity }]
function refreshMelodyTrack(newNotes) {
  // Remove existing note DOM elements
  for (const n of DAW_STATE.notes) {
    if (n._el) { n._el.remove(); n._el = null; }
  }
  DAW_STATE.selectedIds.clear();

  // Install new notes
  DAW_STATE.notes = (newNotes || []).map((n, i) => ({
    id:       `mn-imp-${Date.now()}-${i}`,
    beat:     Math.max(0, Math.min(n.beat,     DAW_STATE.totalBeats - 0.25)),
    duration: Math.max(0.125,                  n.duration ?? 0.25),
    pitch:    Math.max(24, Math.min(96,        n.pitch)),
    velocity: Math.max(30, Math.min(127,       n.velocity ?? 85)),
    _el:      null,
  }));

  // Rebuild pitch range + DOM
  _recalcPitchRange();
  const clip = document.getElementById('clip-melody');
  for (const note of DAW_STATE.notes) {
    note._el = _buildNoteEl(note);
    clip.appendChild(note._el);
  }

  const metaEl = document.getElementById('meta-melody');
  if (metaEl) {
    metaEl.textContent = DAW_STATE.notes.length
      ? `${DAW_STATE.notes.length} notes` : 'empty';
  }

  patchScheduler();
}

// ── Note operations ───────────────────────────────────────────────────────────
function _addNote(data) {
  const note = {
    id:       `mn-${Date.now()}`,
    beat:     Math.max(0, Math.min(data.beat, DAW_STATE.totalBeats - 0.25)),
    duration: data.duration ?? 0.25,
    pitch:    data.pitch,
    velocity: data.velocity ?? 90,
    _el:      null,
  };

  // Expand pitch range if needed and reposition existing notes
  const newLo = Math.min(DAW_STATE.pitchRange.lo, note.pitch - 3);
  const newHi = Math.max(DAW_STATE.pitchRange.hi, note.pitch + 3);
  const rangeChanged = newLo !== DAW_STATE.pitchRange.lo || newHi !== DAW_STATE.pitchRange.hi;
  if (rangeChanged) {
    DAW_STATE.pitchRange = { lo: newLo, hi: newHi };
    _repositionAllNotes();
  }

  DAW_STATE.notes.push(note);

  const clip = document.getElementById('clip-melody');
  note._el   = _buildNoteEl(note);
  clip.appendChild(note._el);

  const metaEl = document.getElementById('meta-melody');
  if (metaEl) metaEl.textContent = `${DAW_STATE.notes.length} notes`;

  patchScheduler();
}

function _deleteNote(note) {
  note._el?.remove();
  note._el = null;
  DAW_STATE.notes    = DAW_STATE.notes.filter(n => n.id !== note.id);
  DAW_STATE.selectedIds.delete(note.id);

  _recalcPitchRange();
  if (DAW_STATE.notes.length > 0) _repositionAllNotes();

  const metaEl = document.getElementById('meta-melody');
  if (metaEl) metaEl.textContent = DAW_STATE.notes.length
    ? `${DAW_STATE.notes.length} notes` : 'empty';

  patchScheduler();
}

function _buildNoteEl(note) {
  const { lo, hi } = DAW_STATE.pitchRange;
  const range  = (hi - lo) || 1;
  const tb     = DAW_STATE.totalBeats;
  const left   = (note.beat / tb) * 100;
  const w      = Math.max(0.4, (note.duration / tb) * 100);
  const bottom = ((note.pitch - lo) / range) * 78 + 6;
  const alpha  = 0.45 + (note.velocity / 127) * 0.55;

  const el = document.createElement('div');
  el.className     = 'melody-note';
  el.dataset.noteId = note.id;
  el.style.cssText = `left:${left}%;width:calc(${w}% - 1px);bottom:${bottom}%;opacity:${alpha}`;
  el.title         = `MIDI ${note.pitch}  beat ${note.beat.toFixed(2)}`;

  el.addEventListener('mousedown',   e => { e.stopPropagation(); _startNoteDrag(e, note); });
  el.addEventListener('contextmenu', e => { e.preventDefault();  _deleteNote(note); });
  return el;
}

// ── Note drag ─────────────────────────────────────────────────────────────────
function _startNoteDrag(e, note) {
  if (e.button !== 0) return;
  e.preventDefault();
  _selectItem(note.id);

  const clip      = document.getElementById('clip-melody');
  const rect      = clip.getBoundingClientRect();
  const startX    = e.clientX;
  const startBeat = note.beat;
  let moved = false;

  document.body.classList.add('daw-dragging');

  function onMove(e) {
    moved = true;
    const dx  = e.clientX - startX;
    const raw = startBeat + (dx / rect.width) * DAW_STATE.totalBeats;
    note.beat = Math.max(0, Math.min(DAW_STATE.totalBeats - note.duration, snapBeat(raw)));
    note._el.style.left  = `${(note.beat / DAW_STATE.totalBeats) * 100}%`;
    note._el.title       = `MIDI ${note.pitch}  beat ${note.beat.toFixed(2)}`;
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup',   onUp);
    document.body.classList.remove('daw-dragging');
    if (moved) patchScheduler();
  }

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup',   onUp);
}

// ── Chord resize ──────────────────────────────────────────────────────────────
function _attachResizeHandle(chord) {
  chord._el.querySelector('.chord-resize-handle')?.remove();
  const handle = document.createElement('div');
  handle.className = 'chord-resize-handle';
  handle.title     = 'Drag to resize chord';
  chord._el.appendChild(handle);

  handle.addEventListener('mousedown', e => {
    e.stopPropagation();
    e.preventDefault();
    _startChordResize(e, chord);
  });
}

function _startChordResize(e, chord) {
  const clip     = document.getElementById('clip-chords');
  const rect     = clip.getBoundingClientRect();
  const startX   = e.clientX;
  const startDur = chord.beat_duration;

  document.body.classList.add('daw-resizing');
  _selectItem(chord.id);

  function onMove(e) {
    const dx = e.clientX - startX;
    const raw = startDur + (dx / rect.width) * DAW_STATE.totalBeats;
    chord.beat_duration = Math.max(0.25,
      Math.min(snapBeat(raw), DAW_STATE.totalBeats - chord.beat_start));
    const w = (chord.beat_duration / DAW_STATE.totalBeats) * 100;
    chord._el.style.width = `calc(${w}% - 3px)`;
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup',   onUp);
    document.body.classList.remove('daw-resizing');
    patchScheduler();
  }

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup',   onUp);
}

// ── One-time interaction setup ────────────────────────────────────────────────
let _interactionsReady = false;
function _setupInteractions() {
  if (_interactionsReady) return;
  _interactionsReady = true;

  // ── Melody clip: click background → add note ──────────────────────────────
  const melodyClip = document.getElementById('clip-melody');

  melodyClip.addEventListener('mousedown', e => {
    // Clear selection when clicking bare background
    const cls = e.target.classList;
    if (!cls.contains('melody-note') && !e.target.closest('.melody-note')) {
      _clearSelection();
    }
  });

  melodyClip.addEventListener('click', e => {
    const cls = e.target.classList;
    // Ignore hits on notes and overlay elements
    if (cls.contains('melody-note') || e.target.closest('.melody-note')) return;
    if (cls.contains('playhead-line') || cls.contains('bar-highlight') ||
        cls.contains('grid-bar')      || cls.contains('grid-beat')     ||
        cls.contains('playhead-ruler')) return;

    const rect  = melodyClip.getBoundingClientRect();
    const beat  = snapBeat(Math.max(0, (e.clientX - rect.left) / rect.width * DAW_STATE.totalBeats));
    const { lo, hi } = DAW_STATE.pitchRange;
    const pitch = Math.round(lo + (1 - (e.clientY - rect.top) / rect.height) * (hi - lo));

    _addNote({ beat, pitch });
  });

  // ── Chord clip: click block → select ─────────────────────────────────────
  const chordsClip = document.getElementById('clip-chords');
  chordsClip.addEventListener('click', e => {
    const el = e.target.closest('.chord-block');
    if (!el) { _clearSelection(); return; }
    const chord = DAW_STATE.chords.find(c => c._el === el);
    if (chord) _selectItem(chord.id);
  });

  // ── Keyboard: Escape = deselect, Delete = remove selected notes ───────────
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

    if (e.key === 'Escape') {
      _clearSelection();
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      const toDelete = DAW_STATE.notes.filter(n => DAW_STATE.selectedIds.has(n.id));
      for (const n of toDelete) _deleteNote(n);
    }
  });
}

// ── Track controls (M / S / instrument) ──────────────────────────────────────
function _setupTrackControls() {
  const defs = [
    { name: 'chords', cls: 'track--chords', instr: true  },
    { name: 'melody', cls: 'track--melody', instr: true  },
    { name: 'drums',  cls: 'track--drums',  instr: false },
  ];

  for (const def of defs) {
    const header = document.querySelector(`.${def.cls} .track-header`);
    if (!header) continue;

    const row = document.createElement('div');
    row.className = 'track-controls';

    // Mute button
    const muteBtn = document.createElement('button');
    muteBtn.className = 'btn-track-ctrl btn-mute';
    muteBtn.textContent = 'M';
    muteBtn.title = 'Mute';
    if (DAW_STATE.muted.has(def.name)) muteBtn.classList.add('muted');
    muteBtn.addEventListener('click', () => _toggleMute(def.name, muteBtn));
    row.appendChild(muteBtn);

    // Solo button
    const soloBtn = document.createElement('button');
    soloBtn.className = 'btn-track-ctrl btn-solo';
    soloBtn.textContent = 'S';
    soloBtn.title = 'Solo';
    if (DAW_STATE.soloed.has(def.name)) soloBtn.classList.add('soloed');
    soloBtn.addEventListener('click', () => _toggleSolo(def.name, soloBtn));
    row.appendChild(soloBtn);

    // Instrument dropdown (chords + melody only)
    if (def.instr) {
      const sel = document.createElement('select');
      sel.className = 'track-instr-select';
      sel.title = 'Instrument';
      for (const name of Object.keys(PRESETS[def.name])) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (name === DAW_STATE.instruments[def.name]) opt.selected = true;
        sel.appendChild(opt);
      }
      sel.addEventListener('change', () => _setInstrument(def.name, sel.value));
      row.appendChild(sel);
    }

    header.appendChild(row);
  }
}

function _toggleMute(name, btn) {
  if (DAW_STATE.muted.has(name)) {
    DAW_STATE.muted.delete(name);
    btn.classList.remove('muted');
  } else {
    DAW_STATE.muted.add(name);
    DAW_STATE.soloed.delete(name); // muting removes from solo
    btn.classList.add('muted');
    // Update solo button visually
    document.querySelector(`.track--${name} .btn-solo`)?.classList.remove('soloed');
  }
  patchScheduler(true);
}

function _toggleSolo(name, btn) {
  if (DAW_STATE.soloed.has(name)) {
    DAW_STATE.soloed.delete(name);
    btn.classList.remove('soloed');
  } else {
    DAW_STATE.soloed.add(name);
    DAW_STATE.muted.delete(name); // solo unmutes
    btn.classList.add('soloed');
    document.querySelector(`.track--${name} .btn-mute`)?.classList.remove('muted');
  }
  patchScheduler(true);
}

function _setInstrument(track, presetName) {
  DAW_STATE.instruments[track] = presetName;
  const preset = PRESETS[track]?.[presetName];
  if (preset) AudioEngine.setInstrument(track, preset);
}
