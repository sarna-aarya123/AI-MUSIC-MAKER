// ── LoopScheduler ──────────────────────────────────────────────────────────────
// Edge-triggered phase gate evaluator. Receives currentPhase (0→1) each frame.
//
// CONTRACT:
//   - Input: currentPhase ∈ [0, 1)  ← only external input
//   - No lookahead. No event queue. No "fired this cycle" set.
//   - Attack fires ONLY when phase crosses a note's phaseStart boundary.
//   - Release fires ONLY when phase crosses a note's phaseEnd boundary.
//   - Cycle boundary detected by: currentPhase < prevPhase − 0.5
//   - Drift every DRIFT_EVERY completed cycles.
//
// Public:
//   load(loopIdentity)       — install new loop data
//   reset()                  — clear state, silence engine
//   tick(currentPhase, bpm)  — called every RAF frame
//   triggerVariation()       — immediate motif drift (MUTATE button)
//   setMute(layer, bool)     — 'motif' | 'bass'
//   getCurrentMotif()        — live (possibly drifted) motif array

const LoopScheduler = (() => {

  const DRIFT_EVERY = 6;

  let _motif        = [];
  let _bass         = [];
  let _loopLength   = 8;    // beats — for drift nudge calculation
  let _scale        = [0, 3, 5, 7, 10];   // scale intervals, updated per loop
  let _tonalCenter  = 69;                  // MIDI root, updated per loop
  let _loaded       = false;

  // Gate states: "m{i}" | "b{i}" → true (open) | false (closed)
  const _gates    = new Map();
  let _prevPhase  = 1.0;   // init to 1.0 → first frame correctly detects no wrap
  let _cycleCount = 0;
  const _muted    = new Set();

  // ── load ─────────────────────────────────────────────────────────────────────
  function load(identity) {
    _motif       = _prepare(identity.motif ?? []);
    _bass        = _prepare(identity.bass  ?? []);
    _loopLength  = identity.loop_length  ?? 8;
    _scale       = identity.scale        ?? [0, 3, 5, 7, 10];
    _tonalCenter = identity.tonal_center ?? 69;
    _loaded     = true;
    _hardReset();
  }

  function _prepare(notes) {
    return notes.map(n => {
      const ps = n.phase_start    ?? 0;
      const pd = n.phase_duration ?? 0.1;
      return {
        phaseStart:    ps,
        phaseDuration: pd,
        phaseEnd:      (ps + pd) % 1.0,
        pitch:         n.pitch,
        velocity:      n.velocity,
      };
    }).sort((a, b) => a.phaseStart - b.phaseStart);
  }

  // ── reset ─────────────────────────────────────────────────────────────────────
  function reset() {
    _hardReset();
    LoopEngine.stopAll();
  }

  function _hardReset() {
    _gates.clear();
    _prevPhase  = 1.0;
    _cycleCount = 0;
  }

  // ── tick: called every RAF frame ──────────────────────────────────────────────
  function tick(currentPhase /*, bpm — unused in gate model */) {
    if (!_loaded) return;

    const wrapped = currentPhase < _prevPhase - 0.5;
    if (wrapped) {
      _cycleCount++;
      if (_cycleCount % DRIFT_EVERY === 0) _drift();
    }

    if (!_muted.has('motif')) {
      for (let i = 0; i < _motif.length; i++) {
        _evalGate('m', i, _motif[i], _prevPhase, currentPhase, wrapped);
      }
    }

    if (!_muted.has('bass')) {
      for (let i = 0; i < _bass.length; i++) {
        _evalGate('b', i, _bass[i], _prevPhase, currentPhase, wrapped);
      }
    }

    _prevPhase = currentPhase;
  }

  // Check crossings for one note; fire gateOn/gateOff exactly on boundary edges.
  function _evalGate(prefix, i, note, prev, curr, wrapped) {
    const key  = `${prefix}${i}`;
    const open = _gates.get(key) ?? false;

    const attackFired  = _crossed(note.phaseStart, prev, curr, wrapped);
    const releaseFired = _crossed(note.phaseEnd,   prev, curr, wrapped);

    if (attackFired && !open) {
      _gates.set(key, true);
      LoopEngine.gateOn(prefix === 'm' ? 'motif' : 'bass', note.pitch, note.velocity);
    }

    if (releaseFired && open) {
      _gates.set(key, false);
      LoopEngine.gateOff(prefix === 'm' ? 'motif' : 'bass');
    }
  }

  // Did phase cross `boundary` as it moved from prev → curr?
  // In the wrap case the phase covered [prev, 1.0) ∪ [0.0, curr].
  function _crossed(boundary, prev, curr, wrapped) {
    if (!wrapped) return boundary > prev && boundary <= curr;
    return boundary > prev || boundary <= curr;
  }

  // ── triggerVariation: MUTATE button ──────────────────────────────────────────
  function triggerVariation() {
    for (let i = 0; i < _motif.length; i++) {
      if (_gates.get(`m${i}`)) {
        _gates.set(`m${i}`, false);
        LoopEngine.gateOff('motif');
      }
    }
    _drift();
  }

  // ── setMute ───────────────────────────────────────────────────────────────────
  function setMute(layer, muted) {
    if (muted) {
      _muted.add(layer);
      const prefix = layer === 'motif' ? 'm' : 'b';
      const arr    = layer === 'motif' ? _motif : _bass;
      for (let i = 0; i < arr.length; i++) {
        if (_gates.get(`${prefix}${i}`)) {
          _gates.set(`${prefix}${i}`, false);
          LoopEngine.gateOff(layer);
        }
      }
    } else {
      _muted.delete(layer);
    }
  }

  // ── getCurrentMotif ───────────────────────────────────────────────────────────
  function getCurrentMotif() { return [..._motif]; }

  // ── _drift: scale-aware identity-preserving motif mutation ───────────────────
  // Pitch mutations always move to adjacent scale degrees — never outside key.
  function _drift() {
    const nudge    = 0.25 / _loopLength;               // 1/16th note in phase units
    const rootPc   = _tonalCenter % 12;
    const scalePcs = _scale.map(s => (rootPc + s) % 12); // pitch classes in scale

    _motif = _motif.map(note => {
      const r = Math.random();

      if (r < 0.28) {
        // Move to adjacent scale degree (always stays in key)
        const pc  = note.pitch % 12;
        const idx = scalePcs.indexOf(pc);
        if (idx !== -1) {
          const dir    = Math.random() < 0.5 ? 1 : -1;
          const newIdx = ((idx + dir) + scalePcs.length) % scalePcs.length;
          const newPc  = scalePcs[newIdx];
          let delta    = newPc - pc;
          if (delta >  6) delta -= 12;   // prefer smallest interval
          if (delta < -6) delta += 12;
          const newPitch = Math.max(36, Math.min(84, note.pitch + delta));
          return { ...note, pitch: newPitch };
        }
      }

      if (r < 0.44) {
        // Timing nudge ±1 sixteenth, stays snapped to 16th grid
        const sign     = Math.random() < 0.5 ? 1 : -1;
        const raw      = note.phaseStart + sign * nudge;
        const clamped  = Math.max(0, Math.min(0.99 - note.phaseDuration, raw));
        const snapped  = Math.round(clamped / nudge) * nudge;
        const newEnd   = (snapped + note.phaseDuration) % 1.0;
        return { ...note, phaseStart: +snapped.toFixed(6), phaseEnd: +newEnd.toFixed(6) };
      }

      if (r < 0.52) {
        // Velocity accent shift — small, musical
        const dv = Math.round((Math.random() - 0.5) * 18);
        return { ...note, velocity: Math.max(45, Math.min(110, note.velocity + dv)) };
      }

      return { ...note };
    }).sort((a, b) => a.phaseStart - b.phaseStart);
  }

  return { load, reset, tick, triggerVariation, setMute, getCurrentMotif };
})();
