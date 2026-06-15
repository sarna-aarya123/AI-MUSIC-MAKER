// ── OneShotEngine ──────────────────────────────────────────────────────────────
// Text-to-sound generator. Fully independent from DAW_STATE, AudioScheduler,
// and the transport clock.
//
// Each call to previewOneShot() creates a temporary Tone.js synth, plays it
// immediately, then schedules self-disposal. Nothing is added to the timeline.
//
// Public API:
//   previewOneShot(text)           → plays sound, returns parsed param object
//   assignToDrumSlot(text, slot)   → patches AudioEngine drum slot envelope

const OneShotEngine = (() => {

  // ── Keyword parser ──────────────────────────────────────────────────────────
  function _parse(text) {
    const t = text.toLowerCase();

    // ── Instrument type ───────────────────────────────────────────────────────
    let type = 'synth';
    if      (/\bkick\b|bass[\s-]?drum|\bbd\b/.test(t))        type = 'kick';
    else if (/\bsnare\b|\bsnr\b|\bclap\b|\bsnap\b/.test(t))  type = 'snare';
    else if (/hi[\s-]?hat|\bhat\b|\bhh\b|\bcymbal\b/.test(t)) type = 'hat';
    else if (/\bpluck\b|\bpick\b|\bguitar\b|\barp\b/.test(t)) type = 'pluck';
    else if (/\bpad\b|\bwash\b|\bambient\b|\bdrone\b/.test(t)) type = 'pad';
    else if (/\bclick\b|\btick\b|\brim\b|\bwood\b/.test(t))   type = 'click';
    else if (/\bbell\b|\btone\b|\bping\b|\bchime\b/.test(t))  type = 'bell';

    // ── Modifier flags ────────────────────────────────────────────────────────
    const tight    = /tight|short|crisp|snap|fast|quick/.test(t);
    const long     = /long|slow|loose|sustained|full|open/.test(t);
    const punchy   = /punch|hard|strong|heavy|big|fat/.test(t);
    const soft     = /soft|quiet|gentle|mellow|weak/.test(t);
    const bright   = /bright|high|sharp|sparkle|shiny|crispy|treble/.test(t);
    const dark     = /dark|low|deep|warm|muffled|muddy|bass/.test(t);
    const metallic = /metal|ring|clang|resonant|tin|ping/.test(t);
    const airy     = /air|reverb|roomy|space|open|wet/.test(t);

    // ── Derived envelope parameters ───────────────────────────────────────────
    const decayTime   = tight  ? 0.05  : long   ? 1.1   : punchy ? 0.14  : 0.22;
    const attackTime  = punchy ? 0.001 : soft   ? 0.07  : 0.003;
    const releaseTime = long   ? 2.0   : tight  ? 0.05  : airy   ? 0.9   : 0.28;
    const gainDb      = soft   ? -14   : punchy ? -4     : -8;

    return {
      type,
      tight, long, punchy, soft, bright, dark, metallic, airy,
      decayTime, attackTime, releaseTime, gainDb,
    };
  }

  // ── Synth builders ──────────────────────────────────────────────────────────
  // Each returns { play(), dispose() }.
  // Disposal is deferred so the sound can fully decay before the node is freed.

  function _kick(p) {
    const synth = new Tone.MembraneSynth({
      pitchDecay : p.tight ? 0.02 : p.punchy ? 0.08 : 0.05,
      octaves    : p.punchy ? 12   : p.dark   ? 7    : 10,
      envelope   : {
        attack  : p.attackTime,
        decay   : p.decayTime,
        sustain : 0,
        release : p.releaseTime,
      },
      volume : p.gainDb,
    }).toDestination();

    const note = p.dark ? 'C0' : 'C1';
    const dur  = Math.max(0.05, p.decayTime);
    return {
      play    : () => synth.triggerAttackRelease(note, dur, Tone.now()),
      dispose : () => setTimeout(() => { try { synth.dispose(); } catch(_){} },
                                  (p.decayTime + p.releaseTime + 0.5) * 1000),
    };
  }

  function _snare(p) {
    const filterFreq = p.bright ? 3000 : p.dark ? 600 : p.metallic ? 2500 : 1400;
    const filterType = p.dark ? 'lowpass' : 'bandpass';
    const filter     = new Tone.Filter(filterFreq, filterType).toDestination();

    const synth = new Tone.NoiseSynth({
      noise    : { type: p.metallic ? 'pink' : 'white' },
      envelope : {
        attack  : p.attackTime,
        decay   : p.decayTime,
        sustain : 0,
        release : p.releaseTime,
      },
      volume : p.gainDb,
    }).connect(filter);

    const dur  = Math.max(0.04, p.decayTime);
    const life = (p.decayTime + p.releaseTime + 0.6) * 1000;
    return {
      play    : () => synth.triggerAttackRelease(dur, Tone.now()),
      dispose : () => setTimeout(() => {
        try { synth.dispose(); } catch(_){}
        try { filter.dispose(); } catch(_){}
      }, life),
    };
  }

  function _hat(p) {
    const freq = p.bright ? 11000 : p.dark ? 4500 : p.metallic ? 7500 : 8500;
    const filter = new Tone.Filter(freq, 'highpass').toDestination();

    const synth = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : {
        attack  : 0.001,
        decay   : p.long ? 0.45 : p.tight ? 0.028 : 0.08,
        sustain : 0,
        release : p.long ? 0.25 : 0.02,
      },
      volume : p.soft ? -16 : -10,
    }).connect(filter);

    const dur  = p.long ? 0.45 : 0.08;
    const life = (dur + 0.5) * 1000;
    return {
      play    : () => synth.triggerAttackRelease(dur, Tone.now()),
      dispose : () => setTimeout(() => {
        try { synth.dispose(); } catch(_){}
        try { filter.dispose(); } catch(_){}
      }, life),
    };
  }

  function _pluck(p) {
    const oscType = p.dark ? 'triangle' : p.bright ? 'sawtooth' : 'triangle8';
    const synth   = new Tone.Synth({
      oscillator : { type: oscType },
      envelope   : {
        attack  : 0.001,
        decay   : p.long ? 0.9 : p.tight ? 0.07 : 0.32,
        sustain : 0,
        release : p.long ? 0.6 : 0.1,
      },
      volume : p.soft ? -16 : -8,
    }).toDestination();

    const note = p.dark ? 'G2' : p.bright ? 'G4' : 'G3';
    return {
      play    : () => synth.triggerAttackRelease(note, '8n', Tone.now()),
      dispose : () => setTimeout(() => { try { synth.dispose(); } catch(_){} }, 2500),
    };
  }

  function _pad(p) {
    const synth = new Tone.PolySynth(Tone.Synth, {
      oscillator : { type: p.bright ? 'sawtooth' : 'sine' },
      envelope   : {
        attack  : p.tight ? 0.04 : p.soft ? 0.5 : 0.28,
        decay   : 0.2,
        sustain : 0.7,
        release : p.long ? 3.0 : 1.5,
      },
      volume : p.soft ? -18 : -13,
    }).toDestination();

    const chord = p.dark ? ['C2', 'G2', 'C3'] : ['C4', 'E4', 'G4'];
    return {
      play    : () => synth.triggerAttackRelease(chord, '2n', Tone.now()),
      dispose : () => setTimeout(() => { try { synth.dispose(); } catch(_){} }, 5500),
    };
  }

  function _click(p) {
    const freq   = p.bright ? 6000 : p.dark ? 1200 : 2200;
    const filter = new Tone.Filter(freq, 'bandpass').toDestination();

    const synth = new Tone.NoiseSynth({
      noise    : { type: 'white' },
      envelope : { attack: 0.001, decay: 0.04, sustain: 0, release: 0.02 },
      volume   : p.soft ? -14 : -6,
    }).connect(filter);

    return {
      play    : () => synth.triggerAttackRelease(0.04, Tone.now()),
      dispose : () => setTimeout(() => {
        try { synth.dispose(); } catch(_){}
        try { filter.dispose(); } catch(_){}
      }, 500),
    };
  }

  function _bell(p) {
    const synth = new Tone.Synth({
      oscillator : { type: 'sine' },
      envelope   : {
        attack  : 0.001,
        decay   : p.tight ? 0.18 : p.long ? 1.2 : 0.7,
        sustain : 0,
        release : p.long ? 2.2 : 0.5,
      },
      volume : p.soft ? -18 : -10,
    }).toDestination();

    const note = p.dark ? 'C4' : p.bright ? 'C6' : 'C5';
    return {
      play    : () => synth.triggerAttackRelease(note, '8n', Tone.now()),
      dispose : () => setTimeout(() => { try { synth.dispose(); } catch(_){} }, 3500),
    };
  }

  function _generic(p) {
    const oscType = p.bright ? 'sawtooth' : p.dark ? 'triangle' : 'sine';
    const synth   = new Tone.Synth({
      oscillator : { type: oscType },
      envelope   : {
        attack  : p.attackTime,
        decay   : p.decayTime,
        sustain : p.long ? 0.4 : 0,
        release : p.releaseTime,
      },
      volume : p.gainDb,
    }).toDestination();

    const note = p.dark ? 'A2' : p.bright ? 'A4' : 'A3';
    return {
      play    : () => synth.triggerAttackRelease(note, p.decayTime, Tone.now()),
      dispose : () => setTimeout(() => { try { synth.dispose(); } catch(_){} },
                                  (p.decayTime + p.releaseTime + 1) * 1000),
    };
  }

  // ── Instrument dispatch ────────────────────────────────────────────────────
  const _builders = {
    kick: _kick, snare: _snare, hat: _hat,
    pluck: _pluck, pad: _pad, click: _click, bell: _bell,
  };

  // ── Public: previewOneShot ─────────────────────────────────────────────────
  async function previewOneShot(text) {
    await Tone.start();
    AudioEngine.init(); // idempotent — also ensures assign works before first Play
    if (!text || !text.trim()) return null;

    const p     = _parse(text.trim());
    const build = _builders[p.type] ?? _generic;
    const inst  = build(p);

    inst.play();
    inst.dispose(); // schedules cleanup — does NOT block or affect playback

    return p;
  }

  // ── Public: assignToDrumSlot ───────────────────────────────────────────────
  // Mutates an existing AudioEngine drum slot's envelope parameters.
  // Slot must be 'kick' | 'snare' | 'hihat'.
  // Does NOT modify DAW_STATE or scheduler.
  async function assignToDrumSlot(text, slot) {
    await Tone.start();
    AudioEngine.init();
    if (!text || !slot) return;
    const p = _parse(text.trim());
    if (typeof AudioEngine.configDrumSlot === 'function') {
      AudioEngine.configDrumSlot(slot, p);
    }
  }

  return { previewOneShot, assignToDrumSlot };
})();
