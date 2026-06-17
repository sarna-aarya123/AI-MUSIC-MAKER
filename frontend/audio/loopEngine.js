// ── LoopEngine ─────────────────────────────────────────────────────────────────
// Underground beat synthesis layer.
// Knows nothing about beats or scheduling — only plays sounds at given AudioContext times.
//
// Instruments:
//   motifSynth  — MonoSynth for looping melodic motif
//   bassSynth   — deep sub MonoSynth
//   textureLayers[] — continuous detuned oscillators (texture stack)
//
// Public API:
//   init(portamento?)
//   gateOn(layer, midi, vel)   — 'motif' | 'bass' : immediate triggerAttack
//   gateOff(layer)             — immediate triggerRelease
//   startTextures(textureDefs[])
//   stopTextures()
//   stopAll()
//   setMotifOsc(type)
//   isReady()

const LoopEngine = (() => {
  let ready        = false;
  let master, masterVerb, masterDelay;
  let motifSynth, bassSynth;
  let textureLayers = [];

  // ── init (idempotent) ────────────────────────────────────────────────────────
  function init(portamento = 0.02) {
    if (ready) return;

    // Master chain: gain → subtle reverb → destination
    masterVerb  = new Tone.Reverb({ decay: 1.8, preDelay: 0.01, wet: 0.12 });
    masterDelay = new Tone.FeedbackDelay({ delayTime: '16n', feedback: 0.18, wet: 0.08 });
    master      = new Tone.Gain(0.82);
    master.chain(masterDelay, masterVerb, Tone.getDestination());

    // ── Motif synth — aggressive, melodic sawtooth ───────────────────────────
    motifSynth = new Tone.MonoSynth({
      oscillator   : { type: 'sawtooth' },
      filter       : { frequency: 1400, type: 'lowpass', Q: 3 },
      envelope     : { attack: 0.006, decay: 0.12, sustain: 0.28, release: 0.45 },
      filterEnvelope: {
        attack: 0.004, decay: 0.10, sustain: 0.20, release: 0.35,
        baseFrequency: 700, octaves: 2.5,
      },
      portamento,
      volume: -4,
    });
    motifSynth.connect(new Tone.Gain(0.70).connect(master));

    // ── Bass synth — sub sine, long sustain ──────────────────────────────────
    bassSynth = new Tone.MonoSynth({
      oscillator   : { type: 'sine' },
      filter       : { frequency: 180, type: 'lowpass', Q: 0.8 },
      envelope     : { attack: 0.015, decay: 0.6, sustain: 0.85, release: 1.2 },
      filterEnvelope: {
        attack: 0.01, decay: 0.3, sustain: 0.5, release: 0.8,
        baseFrequency: 100, octaves: 1.5,
      },
      portamento: 0.06,
      volume: 2,
    });
    bassSynth.connect(new Tone.Gain(0.90).connect(master));

    ready = true;
  }

  // ── Gate model — no future scheduling, no duration ───────────────────────────
  function gateOn(layer, midiPitch, velocity) {
    if (!ready) return;
    try {
      const freq = Tone.Frequency(midiPitch, 'midi').toFrequency();
      const vel  = Math.max(0.01, Math.min(1, velocity / 127));
      if (layer === 'motif')     motifSynth.triggerAttack(freq, Tone.now(), vel);
      else if (layer === 'bass') bassSynth.triggerAttack(freq, Tone.now(), vel);
    } catch (_) {}
  }

  function gateOff(layer) {
    if (!ready) return;
    try {
      if (layer === 'motif')     motifSynth.triggerRelease(Tone.now());
      else if (layer === 'bass') bassSynth.triggerRelease(Tone.now());
    } catch (_) {}
  }

  // ── Texture stack ────────────────────────────────────────────────────────────
  // Each def: { osc_type, detune, filter_freq, filter_q, reverb_wet, pan, gain, pitch }
  function startTextures(defs) {
    stopTextures();
    if (!ready || !defs?.length) return;

    for (const def of defs) {
      try {
        const osc    = new Tone.Oscillator({
          type      : def.osc_type ?? 'sawtooth',
          frequency : Tone.Frequency(def.pitch ?? 48, 'midi').toFrequency(),
          detune    : def.detune ?? 0,
          volume    : -Infinity,
        });
        const filter  = new Tone.Filter(def.filter_freq ?? 800, 'lowpass');
        filter.Q.value = def.filter_q ?? 1;
        const verb    = new Tone.Reverb({ decay: 4, preDelay: 0.02, wet: def.reverb_wet ?? 0.5 });
        const gain    = new Tone.Gain(def.gain ?? 0.12);
        const panner  = new Tone.Panner(def.pan ?? 0);

        osc.connect(filter);
        filter.connect(verb);
        verb.connect(gain);
        gain.connect(panner);
        panner.connect(master);

        // Fade in to avoid click
        osc.volume.setValueAtTime(-Infinity, Tone.now());
        osc.volume.linearRampToValueAtTime(0, Tone.now() + 0.3);
        osc.start();

        textureLayers.push({ osc, filter, verb, gain, panner, def });
      } catch (_) {}
    }
  }

  function stopTextures() {
    for (const { osc, filter, verb, gain, panner } of textureLayers) {
      try {
        osc.volume.linearRampToValueAtTime(-Infinity, Tone.now() + 0.15);
        setTimeout(() => {
          try { osc.stop(); osc.dispose(); } catch (_) {}
          try { filter.dispose(); }          catch (_) {}
          try { verb.dispose(); }            catch (_) {}
          try { gain.dispose(); }            catch (_) {}
          try { panner.dispose(); }          catch (_) {}
        }, 250);
      } catch (_) {}
    }
    textureLayers = [];
  }

  // ── Stop all (called on transport stop) ──────────────────────────────────────
  function stopAll() {
    if (!ready) return;
    try { motifSynth.triggerRelease(); } catch (_) {}
    try { bassSynth.triggerRelease();  } catch (_) {}
    stopTextures();
  }

  // ── Live preset updates ───────────────────────────────────────────────────────
  function setMotifOsc(type) {
    if (!ready) return;
    try { motifSynth.set({ oscillator: { type } }); } catch (_) {}
  }

  function setPortamento(val) {
    if (!ready) return;
    try { motifSynth.portamento = Math.max(0, val); } catch (_) {}
  }

  function isReady() { return ready; }

  return { init, gateOn, gateOff, startTextures, stopTextures,
           stopAll, setMotifOsc, setPortamento, isReady };
})();
