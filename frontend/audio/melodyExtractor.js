// ── MelodyExtractor ────────────────────────────────────────────────────────────
// Decodes an audio file, extracts the dominant pitch over time using
// autocorrelation, and generates a rhythmically-similar melody variant.
//
// Fully independent from DAW_STATE, AudioEngine, and the transport clock.
// All heavy work is async so the UI stays responsive.
//
// Public API:
//   MelodyExtractor.extractFromFile(file, bpm, totalBeats, onProgress)
//     → Promise<{ notes:[{beat,pitch,duration,velocity}], key:{root,type,name} } | null>

const MelodyExtractor = (() => {

  // ── Constants ────────────────────────────────────────────────────────────────
  const TARGET_SR  = 11025;   // downsample to this (Hz) for speed
  const FRAME      = 2048;    // analysis window (samples) ≈ 185 ms
  const HOP        = 1024;    // hop size (samples) ≈ 93 ms
  const MIN_FREQ   = 82;      // lowest pitch to detect  (E2 ≈ MIDI 40)
  const MAX_FREQ   = 1047;    // highest pitch to detect (C6 ≈ MIDI 84)
  const RMS_THR    = 0.008;   // frames quieter than this are treated as silence
  const CONF_THR   = 0.28;    // minimum normalised ACF peak to accept as pitched
  const MAX_SECS   = 30;      // cap analysis at 30 s regardless of file length
  const SNAP       = 0.25;    // beat-grid resolution (16th note)

  // Krumhansl–Schmuckler key-finding profiles
  const KS_MAJ = [6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88];
  const KS_MIN = [6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17];

  const NOTE_NAMES = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];

  const SCALES = {
    major: [0,2,4,5,7,9,11],
    minor: [0,2,3,5,7,8,10],
  };

  // ── Step 1: Load & decode audio ─────────────────────────────────────────────
  async function _loadBuffer(file) {
    let ab;
    if (typeof file.arrayBuffer === 'function') {
      ab = await file.arrayBuffer();
    } else {
      ab = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = e => res(e.target.result);
        r.onerror = rej;
        r.readAsArrayBuffer(file);
      });
    }
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const buf = await ctx.decodeAudioData(ab);
    ctx.close();
    return buf;
  }

  // ── Step 2: Mono mix-down ────────────────────────────────────────────────────
  function _toMono(buf) {
    const ch  = buf.numberOfChannels;
    const len = buf.length;
    const out = new Float32Array(len);
    for (let c = 0; c < ch; c++) {
      const data = buf.getChannelData(c);
      for (let i = 0; i < len; i++) out[i] += data[i] / ch;
    }
    return out;
  }

  // ── Step 3: Downsample (integer decimation) ──────────────────────────────────
  // Simple decimation is fine here because we only care about frequencies
  // below MAX_FREQ (~1 kHz), well below the Nyquist of TARGET_SR (5.5 kHz).
  function _downsample(samples, fromRate) {
    const ratio  = Math.round(fromRate / TARGET_SR);
    const outLen = Math.floor(samples.length / ratio);
    const out    = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) out[i] = samples[i * ratio];
    return out;
  }

  // ── Step 4: Frame-by-frame pitch detection ───────────────────────────────────
  // Yields to the UI every 50 frames so the browser stays responsive.
  async function _detectPitches(samples, onProgress) {
    const minLag  = Math.floor(TARGET_SR / MAX_FREQ);  // ≈ 10 at 11025 Hz
    const maxLag  = Math.ceil(TARGET_SR / MIN_FREQ);   // ≈ 135 at 11025 Hz
    const limit   = Math.min(samples.length, MAX_SECS * TARGET_SR);
    const nFrames = Math.floor((limit - FRAME) / HOP);
    const pitches = [];

    for (let fi = 0; fi < nFrames; fi++) {
      if (fi % 50 === 0) {
        if (onProgress) onProgress(fi / nFrames);
        await new Promise(r => setTimeout(r, 0)); // yield
      }
      const start = fi * HOP;
      const frame = samples.subarray(start, start + FRAME);
      pitches.push({ time: start / TARGET_SR, ..._pitchInFrame(frame, minLag, maxLag) });
    }
    return pitches;
  }

  // ── Pitch in one frame (normalised autocorrelation) ──────────────────────────
  function _pitchInFrame(frame, minLag, maxLag) {
    // RMS energy gate
    let sumSq = 0;
    for (let i = 0; i < FRAME; i++) sumSq += frame[i] * frame[i];
    const rms = Math.sqrt(sumSq / FRAME);
    if (rms < RMS_THR) return { freq: null, confidence: 0, energy: rms };

    const ac0 = sumSq / FRAME;  // normalisation factor (≈ signal power)
    if (ac0 < 1e-12) return { freq: null, confidence: 0, energy: rms };

    // Find lag with maximum normalised autocorrelation in [minLag, maxLag]
    let bestLag  = -1;
    let bestCorr = 0;

    for (let lag = minLag; lag <= maxLag; lag++) {
      const len = FRAME - lag;
      let sum = 0;
      for (let i = 0; i < len; i++) sum += frame[i] * frame[i + lag];
      // Normalise by window size AND signal power → r≈1 for clean sinusoid
      const r = sum / (len * ac0 + 1e-12);
      if (r > bestCorr) { bestCorr = r; bestLag = lag; }
    }

    if (bestLag < 0 || bestCorr < CONF_THR) {
      return { freq: null, confidence: bestCorr, energy: rms };
    }
    return { freq: TARGET_SR / bestLag, confidence: bestCorr, energy: rms };
  }

  // ── Step 5: Segment pitch frames into note events ────────────────────────────
  // Consecutive frames with similar MIDI pitch are grouped into one note.
  function _segmentNotes(pitches) {
    const notes = [];
    let seg = null; // { startTime, midi, energySum, count }

    for (const p of pitches) {
      const midi = (p.freq && p.confidence >= CONF_THR) ? _freqToMidi(p.freq) : null;

      if (midi === null) {
        if (seg) { notes.push(_closeSeg(seg, p.time)); seg = null; }
        continue;
      }

      if (!seg) {
        seg = { startTime: p.time, midi, energySum: p.energy, count: 1 };
      } else if (Math.abs(midi - seg.midi) <= 2) {
        // Same note (allow ±2 semitone jitter from pitch wobble)
        seg.midi       = Math.round((seg.midi * seg.count + midi) / (seg.count + 1));
        seg.energySum += p.energy;
        seg.count++;
      } else {
        notes.push(_closeSeg(seg, p.time));
        seg = { startTime: p.time, midi, energySum: p.energy, count: 1 };
      }
    }

    if (seg && pitches.length > 0) {
      const lastTime = pitches[pitches.length - 1].time + HOP / TARGET_SR;
      notes.push(_closeSeg(seg, lastTime));
    }
    return notes;
  }

  function _closeSeg(seg, endTime) {
    return { startTime: seg.startTime, endTime, midi: seg.midi,
             avgEnergy: seg.energySum / seg.count };
  }

  // ── Step 6: Convert note events to DAW beat format ───────────────────────────
  function _toDAWNotes(noteEvents, bpm, totalBeats) {
    const spb = 60 / bpm;
    const seen = new Set();
    const out  = [];

    for (const n of noteEvents) {
      const beat     = _snap(n.startTime / spb);
      const rawDur   = (n.endTime - n.startTime) / spb;
      const duration = Math.max(SNAP, Math.min(_snap(rawDur), 2.0));
      const velocity = Math.max(45, Math.min(110, Math.round(50 + n.avgEnergy * 5000)));
      const pitch    = Math.max(36, Math.min(84, n.midi));

      if (beat < 0 || beat >= totalBeats) continue;
      if (seen.has(beat)) continue; // skip duplicate beats (snapping collisions)
      seen.add(beat);

      out.push({ beat, pitch, duration, velocity });
    }
    return out;
  }

  // ── Step 7: Key detection (Krumhansl–Schmuckler) ─────────────────────────────
  function _detectKey(notes) {
    if (!notes.length) return { root: 0, type: 'major', name: 'C major' };

    // Build pitch-class histogram weighted by note duration
    const hist = new Float32Array(12);
    for (const n of notes) hist[n.pitch % 12] += n.duration;
    const total = hist.reduce((a, b) => a + b, 1);
    for (let i = 0; i < 12; i++) hist[i] /= total;

    // Find best-matching key via Pearson correlation with KS profiles
    let bestScore = -Infinity, bestRoot = 0, bestType = 'major';
    for (let root = 0; root < 12; root++) {
      const maj = _ksCorr(hist, KS_MAJ, root);
      const min = _ksCorr(hist, KS_MIN, root);
      if (maj > bestScore) { bestScore = maj; bestRoot = root; bestType = 'major'; }
      if (min > bestScore) { bestScore = min; bestRoot = root; bestType = 'minor'; }
    }
    return { root: bestRoot, type: bestType, name: `${NOTE_NAMES[bestRoot]} ${bestType}` };
  }

  function _ksCorr(hist, profile, root) {
    let sumH = 0, sumP = 0, sumHH = 0, sumPP = 0, sumHP = 0;
    for (let i = 0; i < 12; i++) {
      const h = hist[(i + root) % 12];
      const p = profile[i];
      sumH += h; sumP += p; sumHH += h*h; sumPP += p*p; sumHP += h*p;
    }
    const n   = 12;
    const num = n * sumHP - sumH * sumP;
    const den = Math.sqrt((n * sumHH - sumH * sumH) * (n * sumPP - sumP * sumP));
    return den < 1e-10 ? 0 : num / den;
  }

  // ── Step 8: Similarity generation ────────────────────────────────────────────
  // Keeps ~75 % of notes intact; mutates the rest by ±1–2 scale degrees.
  function _makeSimilar(notes, key) {
    if (!notes.length) return notes;
    const scaleArr = SCALES[key.type].map(s => (key.root + s) % 12);

    return notes.map(note => {
      if (Math.random() < 0.75) return { ...note };

      const pc     = note.pitch % 12;
      const octave = Math.floor(note.pitch / 12);

      // Nearest scale degree
      let nearestIdx = 0, minDist = 13;
      for (let i = 0; i < scaleArr.length; i++) {
        const d = Math.min(Math.abs(scaleArr[i] - pc), 12 - Math.abs(scaleArr[i] - pc));
        if (d < minDist) { minDist = d; nearestIdx = i; }
      }

      // Step ±1 (70 %) or ±2 (30 %) scale degrees
      const steps  = Math.random() < 0.70 ? 1 : 2;
      const dir    = Math.random() < 0.5  ? 1 : -1;
      const newIdx = ((nearestIdx + dir * steps) % scaleArr.length + scaleArr.length) % scaleArr.length;
      const newPc  = scaleArr[newIdx];

      // Reconstruct pitch, correcting for octave wraps at scale boundaries
      let newPitch = octave * 12 + newPc;
      while (newPitch < note.pitch - 6) newPitch += 12;
      while (newPitch > note.pitch + 6) newPitch -= 12;

      // Clamp to playable range
      while (newPitch < 40) newPitch += 12;
      while (newPitch > 84) newPitch -= 12;

      return { ...note, pitch: newPitch };
    });
  }

  // ── Utilities ─────────────────────────────────────────────────────────────────
  function _freqToMidi(freq) {
    return Math.round(12 * Math.log2(freq / 440) + 69);
  }

  function _snap(val) {
    return Math.round(val / SNAP) * SNAP;
  }

  // ── Public: extractFromFile ───────────────────────────────────────────────────
  // onProgress: (0–1) → void  (optional)
  // Returns { notes, key } or null if no melody was detected.
  async function extractFromFile(file, bpm, totalBeats, onProgress) {
    const prog = pct => { if (onProgress) onProgress(Math.min(1, pct)); };

    prog(0.02);
    const audioBuf = await _loadBuffer(file);
    prog(0.06);

    const mono = _toMono(audioBuf);
    const ds   = _downsample(mono, audioBuf.sampleRate);
    prog(0.08);

    const rawPitches = await _detectPitches(ds, p => prog(0.08 + p * 0.72));
    prog(0.82);

    const noteEvents = _segmentNotes(rawPitches);
    if (!noteEvents.length) return null;
    prog(0.86);

    const dawNotes = _toDAWNotes(noteEvents, bpm, totalBeats);
    if (!dawNotes.length) return null;
    prog(0.90);

    const key     = _detectKey(dawNotes);
    const similar = _makeSimilar(dawNotes, key);
    prog(1.0);

    return { notes: similar, key };
  }

  return { extractFromFile };
})();
