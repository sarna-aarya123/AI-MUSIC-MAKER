// ── Loop Identity Generator — Main Controller ─────────────────────────────────
// Manages: transport, API calls, phase-derived visuals, UI wiring.
//
// The scheduler receives only currentPhase (0→1). This file is the ONLY place
// where wall-clock time is converted to phase. Everything downstream is phase-only.
//
// No chord logic. No DAW state. No timeline. No song concept.

// ── Transport state ────────────────────────────────────────────────────────────
const T = {
  isPlaying:     false,
  bpm:           140,
  loopLength:    8,      // beats per cycle
  startWall:     0,      // performance.now() at last play()
  startBeat:     0,      // beat position at play() — resets on stop
  currentPhase:  0,      // 0 → 1, current loop position
  rafId:         null,
};

// ── Loop state (what we received from the API, what drives audio) ──────────────
const LOOP_STATE = {
  motif:       [],
  bass:        [],
  textures:    [],
  bpm:         140,
  loopLength:  8,
  tonalCenter: 69,
  root:        'A',
  genre:       'rage',
  muted:       new Set(),   // 'motif' | 'bass' | 'texture'
};

// ── DOM refs ───────────────────────────────────────────────────────────────────
const elEvolve    = document.getElementById('btn-evolve');
const elActivate  = document.getElementById('btn-activate');
const elStop      = document.getElementById('btn-stop');
const elMutate    = document.getElementById('btn-mutate');
const elStatus    = document.getElementById('status-text');   // controls-strip brief msg
const elStatusMain = document.getElementById('status-main'); // footer long description
const elPhaseBar  = document.getElementById('phase-bar');
// Playhead elements in each layer clip
const elPhMotif  = document.getElementById('ph-motif');
const elPhBass   = document.getElementById('ph-bass');

// ── Transport: RAF loop ────────────────────────────────────────────────────────
function _tick() {
  if (!T.isPlaying) return;

  // Wall-clock → beat → phase
  const elapsedSec  = (performance.now() - T.startWall) / 1000;
  const absBeats    = T.startBeat + elapsedSec * (T.bpm / 60);
  const currentPhase = (absBeats % T.loopLength) / T.loopLength;  // [0, 1)

  T.currentPhase = currentPhase;

  // All scheduling lives here — phase only
  LoopScheduler.tick(currentPhase, T.bpm);

  // Visual: update pulse indicator
  _updatePulse(currentPhase);

  T.rafId = requestAnimationFrame(_tick);
}

function _startTransport() {
  if (T.isPlaying) return;
  T.isPlaying  = true;
  T.startWall  = performance.now();
  T.startBeat  = 0;
  elActivate.textContent = '■ PLAYING';
  elActivate.classList.add('active');
  elStop.disabled = false;
  T.rafId = requestAnimationFrame(_tick);
}

function _stopTransport() {
  T.isPlaying = false;
  if (T.rafId) { cancelAnimationFrame(T.rafId); T.rafId = null; }
  LoopScheduler.reset();
  _updatePulse(0);
  elActivate.textContent = '▶ PLAY LOOP';
  elActivate.classList.remove('active');
  elStop.disabled = true;
}

// ── Visual: phase pulse + layer playheads ─────────────────────────────────────
function _updatePulse(phase) {
  const pct = `${(phase * 100).toFixed(3)}%`;

  // Top phase bar (scale from left)
  if (elPhaseBar) elPhaseBar.style.transform = `scaleX(${phase.toFixed(4)})`;

  // Vertical playhead lines in each layer clip
  if (elPhMotif) elPhMotif.style.left = pct;
  if (elPhBass)  elPhBass.style.left  = pct;
}

// ── Evolve: fetch new loop identity from backend ───────────────────────────────
async function evolve() {
  if (T.isPlaying) _stopTransport();

  elEvolve.disabled    = true;
  elEvolve.textContent = 'GENERATING…';
  // Blur text input so repeated Enter key doesn't re-trigger
  document.getElementById('input-describe')?.blur();
  _setStatus('Generating loop identity…');

  try {
    const params = _getParams();
    const res    = await fetch('/api/loop/evolve', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(params),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || `HTTP ${res.status}`);
    }

    const data = await res.json();
    _installLoop(data);

  } catch (err) {
    _setStatus(`Error: ${err.message}`, true);
    console.error('[LoopStudio]', err);
  } finally {
    elEvolve.disabled    = false;
    elEvolve.textContent = 'CREATE LOOP';
  }
}

function _getParams() {
  const desc      = document.getElementById('input-describe')?.value?.trim() ?? '';
  const leadInst  = document.getElementById('ctrl-lead-inst')?.value ?? '';
  return {
    genre:           document.getElementById('ctrl-genre')?.value ?? 'rage',
    root:            document.getElementById('ctrl-root')?.value  ?? 'A',
    bpm:             parseInt(document.getElementById('ctrl-bpm')?.value  ?? '140', 10),
    bars:            parseInt(document.getElementById('ctrl-bars')?.value ?? '4',   10),
    seed:            Math.floor(Math.random() * 99999),
    description:     desc || undefined,
    lead_instrument: leadInst || undefined,
  };
}

// ── Install a loop identity received from the API ──────────────────────────────
function _installLoop(data) {
  // Store in LOOP_STATE
  LOOP_STATE.motif       = (data.motif ?? []).map(n => ({
    phaseStart:    n.phase_start    ?? 0,
    phaseDuration: n.phase_duration ?? 0.1,
    pitch:         n.pitch,
    velocity:      n.velocity,
  }));
  LOOP_STATE.bass        = (data.bass ?? []).map(n => ({
    phaseStart:    n.phase_start    ?? 0,
    phaseDuration: n.phase_duration ?? 0.5,
    pitch:         n.pitch,
    velocity:      n.velocity,
  }));
  LOOP_STATE.textures    = data.textures    ?? [];
  LOOP_STATE.bpm         = data.bpm         ?? 140;
  LOOP_STATE.loopLength  = data.loop_length ?? 8;
  LOOP_STATE.tonalCenter = data.tonal_center ?? 69;
  LOOP_STATE.root        = data.root        ?? 'A';
  LOOP_STATE.genre       = data.genre       ?? 'rage';

  // Sync transport BPM
  T.bpm        = LOOP_STATE.bpm;
  T.loopLength = LOOP_STATE.loopLength;

  // Override BPM display
  const bpmEl = document.getElementById('ctrl-bpm');
  if (bpmEl) bpmEl.value = T.bpm;

  // Prime audio engine + apply synth settings
  LoopEngine.init(data.portamento ?? 0.02);
  LoopEngine.setPortamento(data.portamento ?? 0.02);
  LoopEngine.setPreset(data.genre ?? 'rage');
  // Lead instrument config overrides genre preset when present
  if (data.synth_config) LoopEngine.applyInstrumentConfig(data.synth_config);

  // Load scheduler — phase-space only from here
  LoopScheduler.load(data);

  // Render layer visualisations
  _renderMotifLayer(LOOP_STATE.motif);
  _renderBassLayer(LOOP_STATE.bass);
  _renderTextureStack(LOOP_STATE.textures);

  // Enable controls
  elActivate.disabled = false;
  elMutate.disabled   = false;

  // Show main view
  document.getElementById('empty-state').hidden = true;
  document.getElementById('loop-view').hidden   = false;

  const scaleName = { rage: 'minor pent', pluggnb: 'natural minor', dark_trap: 'phrygian', cloud: 'major pent' }[data.genre] ?? '';
  const instLabel = data.lead_instrument ? `  ·  ${data.lead_instrument.replace('_', ' ')} lead` : '';
  const summary = `${data.genre.toUpperCase()}  ·  ${data.root} ${scaleName}${instLabel}  ·  ${data.bpm} BPM  ·  ${data.loop_length / 4}-bar loop  ·  ${LOOP_STATE.motif.length} motif notes  ·  ${data.textures.length} texture layers`;
  if (elStatusMain) elStatusMain.textContent = summary;
  _setStatus('Loop ready');
}

// ── Layer renders ──────────────────────────────────────────────────────────────

function _renderMotifLayer(motif) {
  const clip = document.getElementById('clip-motif');
  if (!clip) return;

  // Preserve the playhead node — innerHTML clear detaches it
  const ph = clip.querySelector('.layer-playhead');
  clip.innerHTML = '';
  if (ph) clip.appendChild(ph);

  if (!motif.length) return;

  const pitches = motif.map(n => n.pitch);
  const lo      = Math.min(...pitches) - 1;
  const hi      = Math.max(...pitches) + 1;
  const range   = hi - lo || 1;

  // Grid lines at quarter-phase marks (25 / 50 / 75 %)
  for (const frac of [0.25, 0.5, 0.75]) {
    const line = document.createElement('div');
    line.className = 'phase-grid-line';
    line.style.left = `${frac * 100}%`;
    clip.appendChild(line);
  }

  for (const note of motif) {
    const bottom = ((note.pitch - lo) / range) * 78 + 6;
    const alpha  = 0.50 + (note.velocity / 127) * 0.50;

    const el = document.createElement('div');
    el.className     = 'motif-note';
    el.style.left    = `${note.phaseStart * 100}%`;
    el.style.width   = `${Math.max(0.5, note.phaseDuration * 100)}%`;
    el.style.bottom  = `${bottom}%`;
    el.style.opacity = alpha;
    el.title = `pitch ${note.pitch}  φ ${note.phaseStart.toFixed(3)}`;
    clip.appendChild(el);
  }
}

function _renderBassLayer(bass) {
  const clip = document.getElementById('clip-bass');
  if (!clip) return;

  const ph = clip.querySelector('.layer-playhead');
  clip.innerHTML = '';
  if (ph) clip.appendChild(ph);

  for (const note of bass) {
    const el = document.createElement('div');
    el.className   = 'bass-note';
    el.style.left  = `${note.phaseStart * 100}%`;
    el.style.width = `calc(${Math.min(note.phaseDuration, 1 - note.phaseStart) * 100}% - 2px)`;
    el.title       = `root ${note.pitch}  φ ${note.phaseStart.toFixed(3)}`;
    clip.appendChild(el);
  }
}

function _renderTextureStack(textures) {
  const stack = document.getElementById('texture-stack');
  if (!stack) return;
  stack.innerHTML = '';

  textures.forEach((tx, i) => {
    const row = document.createElement('div');
    row.className = 'texture-row';

    // Color by texture archetype
    const hue = tx.archetype === 'aggressive' ? 15
              : tx.archetype === 'dark'        ? 270
              : tx.archetype === 'ambient'     ? 160
              : tx.archetype === 'airy'        ? 190
              : tx.archetype === 'wide'        ? 265
              : 265;
    row.style.setProperty('--tx-hue', hue);

    const archLabel = (tx.archetype ?? tx.osc_type ?? '—').toUpperCase().slice(0, 4);
    const panStr    = tx.pan > 0.05 ? `R${Math.round(tx.pan * 100)}`
                    : tx.pan < -0.05 ? `L${Math.round(Math.abs(tx.pan) * 100)}`
                    : 'C';
    row.innerHTML = `
      <span class="tx-osc">${archLabel}</span>
      <span class="tx-detail">
        <strong>${tx.osc_type.slice(0, 3).toUpperCase()}</strong>
        · det <strong>${tx.detune > 0 ? '+' : ''}${tx.detune.toFixed(0)}</strong>
        · filt <strong>${Math.round(tx.filter_freq)} Hz</strong>
        · rev <strong>${Math.round(tx.reverb_wet * 100)}%</strong>
        · pan <strong>${panStr}</strong>
      </span>
      <div class="tx-bar" style="opacity:${0.25 + tx.gain * 3}"></div>
    `;
    stack.appendChild(row);
  });
}

// ── Mute controls ──────────────────────────────────────────────────────────────
function _toggleMute(layer) {
  const muted = !LOOP_STATE.muted.has(layer);
  if (muted) LOOP_STATE.muted.add(layer);
  else        LOOP_STATE.muted.delete(layer);

  LoopScheduler.setMute(layer, muted);

  // Texture layer: start/stop oscillators
  if (layer === 'texture') {
    if (muted) LoopEngine.stopTextures();
    else        LoopEngine.startTextures(LOOP_STATE.textures);
  }

  // Update mute button appearance
  const btn = document.querySelector(`.btn-mute[data-layer="${layer}"]`);
  if (btn) btn.classList.toggle('muted', muted);
}

// ── Event wiring ───────────────────────────────────────────────────────────────
elEvolve?.addEventListener('click', evolve);

elActivate?.addEventListener('click', async () => {
  if (T.isPlaying) {
    _stopTransport();
    // Stop textures too
    LoopEngine.stopTextures();
  } else {
    await Tone.start();
    LoopEngine.init(0.02);
    // Start texture oscillators (continuous — not scheduled)
    if (!LOOP_STATE.muted.has('texture')) {
      LoopEngine.startTextures(LOOP_STATE.textures);
    }
    _startTransport();
  }
});

elStop?.addEventListener('click', () => {
  _stopTransport();
  LoopEngine.stopTextures();
});

elMutate?.addEventListener('click', () => {
  LoopScheduler.triggerVariation();
  // Re-render motif layer to show mutation
  _renderMotifLayer(LoopScheduler.getCurrentMotif());
  _flashStatus('Variation applied');
});

// Mute buttons
document.querySelectorAll('.btn-mute').forEach(btn => {
  btn.addEventListener('click', () => _toggleMute(btn.dataset.layer));
});

// Spacebar: toggle transport (not when user is typing)
document.addEventListener('keydown', e => {
  if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
    e.preventDefault();
    elActivate?.click();
  }
  // Enter in describe field → generate
  if (e.code === 'Enter' && e.target.id === 'input-describe') {
    e.preventDefault();
    elEvolve?.click();
  }
});

// ── LoopTransport global — used by importUI for loop preview in import panel ──
window.LoopTransport = {
  start: async () => {
    if (T.isPlaying) return;
    await Tone.start();
    LoopEngine.init(0.02);
    if (!LOOP_STATE.muted.has('texture')) LoopEngine.startTextures(LOOP_STATE.textures);
    _startTransport();
  },
  stop: () => {
    _stopTransport();
    LoopEngine.stopTextures();
  },
  isPlaying: () => T.isPlaying,
  getPhase:  () => T.currentPhase,
  hasLoop:   () => LOOP_STATE.motif.length > 0,
};

// ── Status helpers ─────────────────────────────────────────────────────────────
function _setStatus(msg, isError = false) {
  if (!elStatus) return;
  elStatus.textContent = msg;
  elStatus.classList.toggle('error', isError);
}

function _flashStatus(msg) {
  const prev = elStatus?.textContent;
  _setStatus(msg);
  setTimeout(() => { if (elStatus) elStatus.textContent = prev; }, 1200);
}

// Initial state
elActivate && (elActivate.disabled = true);
elMutate   && (elMutate.disabled   = true);
elStop     && (elStop.disabled     = true);

// Expose _installLoop globally for importUI.js
window._installLoop = _installLoop;
