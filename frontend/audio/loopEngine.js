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
//   setPreset(genre)           — hot-apply genre-specific synth settings
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

  // ── Genre preset — applied when a new loop identity is loaded ────────────────
  const _PRESETS = {
    rage: {
      motif: { oscillator: { type: 'sawtooth' },
               filter: { frequency: 1600, Q: 3.8 },
               envelope: { attack: 0.004, decay: 0.10, sustain: 0.18, release: 0.32 },
               filterEnvelope: { attack: 0.003, decay: 0.09, sustain: 0.15, release: 0.28,
                                 baseFrequency: 800, octaves: 2.8 } },
      bass:  { filter: { frequency: 140 } },
    },
    pluggnb: {
      motif: { oscillator: { type: 'triangle' },
               filter: { frequency: 2400, Q: 1.8 },
               envelope: { attack: 0.014, decay: 0.22, sustain: 0.50, release: 0.90 },
               filterEnvelope: { attack: 0.012, decay: 0.18, sustain: 0.35, release: 0.70,
                                 baseFrequency: 600, octaves: 2.0 } },
      bass:  { filter: { frequency: 210 } },
    },
    dark_trap: {
      motif: { oscillator: { type: 'square' },
               filter: { frequency: 900, Q: 4.5 },
               envelope: { attack: 0.008, decay: 0.16, sustain: 0.28, release: 0.65 },
               filterEnvelope: { attack: 0.006, decay: 0.14, sustain: 0.22, release: 0.50,
                                 baseFrequency: 500, octaves: 2.2 } },
      bass:  { filter: { frequency: 110 } },
    },
    cloud: {
      motif: { oscillator: { type: 'triangle' },
               filter: { frequency: 3200, Q: 1.2 },
               envelope: { attack: 0.022, decay: 0.28, sustain: 0.65, release: 1.30 },
               filterEnvelope: { attack: 0.018, decay: 0.22, sustain: 0.50, release: 1.00,
                                 baseFrequency: 900, octaves: 1.8 } },
      bass:  { filter: { frequency: 260 } },
    },
  };

  function setPreset(genre) {
    if (!ready) return;
    const p = _PRESETS[genre] ?? _PRESETS.rage;
    try { if (p.motif) motifSynth.set(p.motif); } catch (_) {}
    try { if (p.bass)  bassSynth.set({ filter: p.bass.filter }); } catch (_) {}
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

  // Apply lead instrument config received from API (overrides genre preset)
  function applyInstrumentConfig(cfg) {
    if (!ready || !cfg) return;
    try {
      const patch = {};
      if (cfg.osc_type)   patch.oscillator    = { type: cfg.osc_type };
      if (cfg.envelope)   patch.envelope      = cfg.envelope;
      if (cfg.filter_env) patch.filterEnvelope = cfg.filter_env;
      if (cfg.filter_freq || cfg.filter_q) {
        patch.filter = {};
        if (cfg.filter_freq) patch.filter.frequency = cfg.filter_freq;
        if (cfg.filter_q)    patch.filter.Q         = cfg.filter_q;
      }
      motifSynth.set(patch);
    } catch (_) {}
    if (cfg.portamento !== undefined) setPortamento(cfg.portamento);
  }

  function isReady() { return ready; }

  return { init, setPreset, applyInstrumentConfig, gateOn, gateOff,
           startTextures, stopTextures, stopAll, setMotifOsc, setPortamento, isReady };
})();
