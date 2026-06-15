// ── AudioEngine ────────────────────────────────────────────────────────────────
// Thin Tone.js wrapper. Knows NOTHING about beats or BPM.
// Only responsibility: play a sound at a given AudioContext time.
//
// All scheduling math lives in scheduler.js.
// init() is idempotent — safe to call multiple times.

const AudioEngine = (() => {
  let ready = false;

  // ── Instruments ─────────────────────────────────────────────────────────────
  let master;
  let kick, snare, hihat, openHat, ride, crash, rim;
  let melodySynth, chordSynth;

  function init() {
    if (ready) return;

    master = new Tone.Gain(0.75).toDestination();

    // ── Kick ─ membrane synthesis (tunable pitch + decay) ───────────────────
    kick = new Tone.MembraneSynth({
      pitchDecay : 0.05,
      octaves    : 10,
      envelope   : { attack: 0.001, decay: 0.32, sustain: 0, release: 0.1 },
    }).connect(new Tone.Gain(0.9).connect(master));

    // ── Snare ─ white noise, short decay ────────────────────────────────────
    const snareGain = new Tone.Gain(0.55).connect(master);
    snare = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : { attack: 0.001, decay: 0.15, sustain: 0, release: 0.05 },
    }).connect(snareGain);

    // ── Closed hihat ─ high-passed white noise ───────────────────────────────
    const hihatChain = new Tone.Filter(9000, 'highpass')
      .connect(new Tone.Gain(0.45).connect(master));
    hihat = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : { attack: 0.001, decay: 0.045, sustain: 0, release: 0.02 },
    }).connect(hihatChain);

    // ── Open hihat ─ same but longer tail ───────────────────────────────────
    const openChain = new Tone.Filter(7500, 'highpass')
      .connect(new Tone.Gain(0.4).connect(master));
    openHat = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : { attack: 0.001, decay: 0.35, sustain: 0, release: 0.15 },
    }).connect(openChain);

    // ── Ride ─ metallic shimmer ──────────────────────────────────────────────
    const rideChain = new Tone.Filter(6000, 'highpass')
      .connect(new Tone.Gain(0.35).connect(master));
    ride = new Tone.NoiseSynth({
      noise    : { type: 'pink' },
      envelope : { attack: 0.001, decay: 0.45, sustain: 0, release: 0.2 },
    }).connect(rideChain);

    // ── Crash ─ long wash ────────────────────────────────────────────────────
    const crashChain = new Tone.Filter(5000, 'highpass')
      .connect(new Tone.Gain(0.4).connect(master));
    crash = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : { attack: 0.001, decay: 0.9,  sustain: 0, release: 0.4 },
    }).connect(crashChain);

    // ── Rim ─ bandpass crack ─────────────────────────────────────────────────
    const rimChain = new Tone.Filter(1200, 'bandpass')
      .connect(new Tone.Gain(0.5).connect(master));
    rim = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : { attack: 0.001, decay: 0.06, sustain: 0, release: 0.02 },
    }).connect(rimChain);

    // ── Melody ─ triangle-ish synth, moderate attack ─────────────────────────
    melodySynth = new Tone.Synth({
      oscillator : { type: 'triangle8' },
      envelope   : { attack: 0.02, decay: 0.1, sustain: 0.35, release: 0.5 },
    }).connect(new Tone.Gain(0.55).connect(master));

    // ── Chords ─ polyphonic, soft sine ───────────────────────────────────────
    chordSynth = new Tone.PolySynth(Tone.Synth, {
      oscillator : { type: 'sine' },
      envelope   : { attack: 0.06, decay: 0.3, sustain: 0.45, release: 1.2 },
    }).connect(new Tone.Gain(0.35).connect(master));
    chordSynth.maxPolyphony = 12;

    ready = true;
  }

  // ── Drum dispatch ──────────────────────────────────────────────────────────
  // drumType: 'kick'|'snare'|'hihat'|'open_hat'|'ride'|'crash'|'rim'
  // velocity: 0–127
  // audioTime: Tone.js AudioContext time in seconds
  // durationSec: nominal duration (envelope governs actual sound length)
  function playDrum(drumType, velocity, audioTime, durationSec) {
    if (!ready) return;
    const vel = Math.max(0.01, Math.min(1, velocity / 127));
    const dur = Math.max(0.05, durationSec);

    try {
      switch (drumType) {
        case 'kick':
          kick.triggerAttackRelease('C1', dur, audioTime, vel);
          break;
        case 'snare':
          snare.triggerAttackRelease(dur, audioTime, vel);
          break;
        case 'hihat':
          hihat.triggerAttackRelease(dur, audioTime, vel);
          break;
        case 'open_hat':
          openHat.triggerAttackRelease(dur, audioTime, vel);
          break;
        case 'ride':
          ride.triggerAttackRelease(dur, audioTime, vel);
          break;
        case 'crash':
          crash.triggerAttackRelease(dur, audioTime, vel);
          break;
        case 'rim':
          rim.triggerAttackRelease(dur, audioTime, vel);
          break;
        // unknown drum types are silently ignored
      }
    } catch (_) { /* scheduling collisions on fast loops — ignore */ }
  }

  // ── Melody note ───────────────────────────────────────────────────────────
  // midiPitch: MIDI note number (e.g. 60 = C4)
  function playNote(midiPitch, velocity, audioTime, durationSec) {
    if (!ready) return;
    const freq = Tone.Frequency(midiPitch, 'midi').toFrequency();
    const vel  = Math.max(0.01, Math.min(1, velocity / 127));
    try {
      melodySynth.triggerAttackRelease(freq, Math.max(0.05, durationSec), audioTime, vel);
    } catch (_) {}
  }

  // ── Chord (polyphonic) ────────────────────────────────────────────────────
  // midiPitches: array of MIDI note numbers
  function playChord(midiPitches, velocity, audioTime, durationSec) {
    if (!ready || !midiPitches?.length) return;
    const freqs = midiPitches.map(p => Tone.Frequency(p, 'midi').toFrequency());
    const vel   = Math.max(0.01, Math.min(0.65, velocity / 127));
    try {
      chordSynth.triggerAttackRelease(freqs, Math.max(0.1, durationSec), audioTime, vel);
    } catch (_) {}
  }

  // ── Stop all sustained notes ──────────────────────────────────────────────
  function stopAll() {
    if (!ready) return;
    try { melodySynth.triggerRelease(); } catch (_) {}
    try { chordSynth.releaseAll();      } catch (_) {}
    // Percussive synths are self-decaying; no explicit stop needed.
  }

  // ── Instrument preset switching ───────────────────────────────────────────
  // preset: { oscillator: { type }, envelope: { attack, decay, sustain, release } }
  function setInstrument(track, preset) {
    if (!ready) return;
    try {
      if (track === 'melody') {
        melodySynth.set(preset);
      } else if (track === 'chords') {
        chordSynth.releaseAll();   // release any held voices before changing timbre
        chordSynth.set(preset);
      }
    } catch (_) {}
  }

  // ── Drum slot reconfiguration (for One-Shot assign) ──────────────────────
  // Mutates the envelope of an existing drum synth in-place.
  // p is the parsed param object from OneShotEngine._parse().
  // Slot: 'kick' | 'snare' | 'hihat'  (open_hat / ride / crash not supported)
  function configDrumSlot(slot, p) {
    if (!ready) return;
    try {
      if (slot === 'kick' && kick) {
        kick.pitchDecay        = p.tight ? 0.02 : p.punchy ? 0.08 : 0.05;
        kick.envelope.decay    = Math.max(0.05, p.decayTime);
        kick.envelope.release  = Math.max(0.05, p.releaseTime);
      } else if (slot === 'snare' && snare) {
        snare.envelope.attack  = p.attackTime;
        snare.envelope.decay   = Math.max(0.04, p.decayTime);
        snare.envelope.release = Math.max(0.02, p.releaseTime);
      } else if (slot === 'hihat' && hihat) {
        hihat.envelope.decay   = Math.max(0.02, p.long ? 0.4 : p.tight ? 0.03 : 0.08);
        hihat.envelope.release = Math.max(0.01, p.tight ? 0.01 : 0.03);
      }
    } catch (_) {}
  }

  return { init, playDrum, playNote, playChord, stopAll, setInstrument, configDrumSlot };
})();
