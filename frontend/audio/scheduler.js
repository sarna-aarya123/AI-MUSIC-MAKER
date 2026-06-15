// ── AudioScheduler ─────────────────────────────────────────────────────────────
// Beat-to-audio bridge. Called every animation frame from tick() in studio.js.
//
// Responsibilities:
//   load(data)              — convert API response to flat sorted event list
//   process(beat, bpm)      — schedule events in the lookahead window
//   reset()                 — clear pointer + stop sustained notes (on stop/loop)
//
// What it does NOT do:
//   - Calculate beats or time (that's tick()'s job)
//   - Schedule setInterval / setTimeout for timing (no independent clocks)

const AudioScheduler = (() => {
  // Events are sorted by beat; nextIdx is a cursor that advances forward.
  // On loop wrap or reset, nextIdx is reset to 0.
  let events   = [];
  let nextIdx  = 0;
  let lastBeat = -1;
  let loaded   = false;

  // How far ahead (in wall-clock seconds) to pre-schedule audio events.
  // Larger = more buffer against jank; smaller = tighter sync.
  // 0.12 s at 120 BPM ≈ 0.24 beats of lookahead.
  const LOOKAHEAD_SEC  = 0.12;
  const PAST_TOLERANCE = 0.04; // beats; accept slightly late events

  // ── load ─────────────────────────────────────────────────────────────────
  // Call after every successful /api/generate/composition response.
  function load(data) {
    events   = [];
    nextIdx  = 0;
    lastBeat = -1;
    loaded   = false;

    const bpm          = data.bpm;
    const secPerBeat   = 60 / bpm;

    // ── Drums ───────────────────────────────────────────────────────────────
    for (const ev of (data.drum_data?.events ?? [])) {
      events.push({
        beat:     ev.beat,
        durSec:   Math.max(0.04, ev.duration * secPerBeat),
        velocity: ev.velocity,
        drumType: ev.drum_type,
        type:     'drum',
      });
    }

    // ── Melody ──────────────────────────────────────────────────────────────
    for (const note of (data.melody_data?.notes ?? [])) {
      events.push({
        beat:     note.beat,
        durSec:   Math.max(0.05, note.duration * secPerBeat),
        pitch:    note.pitch,
        velocity: note.velocity,
        type:     'melody',
      });
    }

    // ── Chords ──────────────────────────────────────────────────────────────
    for (const chord of (data.chord_data?.chords ?? [])) {
      events.push({
        beat:     chord.beat_start,
        // Trim chord duration slightly so adjacent chords don't bleed together
        durSec:   Math.max(0.1, chord.beat_duration * secPerBeat * 0.92),
        pitches:  chord.notes,       // array of MIDI pitch numbers
        velocity: 82,
        type:     'chord',
      });
    }

    // Sort ascending by beat so the cursor scan is O(events) total
    events.sort((a, b) => a.beat - b.beat);
    loaded = true;
  }

  // ── reset ─────────────────────────────────────────────────────────────────
  // Call on Stop, and on loop wrap (detected internally in process()).
  function reset() {
    nextIdx  = 0;
    lastBeat = -1;
    AudioEngine.stopAll();
  }

  // ── process ───────────────────────────────────────────────────────────────
  // Called every RAF frame from tick(). Schedules all events whose beat
  // falls within [currentBeat − tolerance, currentBeat + lookaheadBeats).
  function process(currentBeat, bpm) {
    if (!loaded || events.length === 0) return;

    // ── Loop wrap detection ─────────────────────────────────────────────────
    // A significant backwards jump means the loop has reset.
    if (lastBeat >= 0 && currentBeat < lastBeat - 0.5) {
      nextIdx = 0;
      AudioEngine.stopAll();
    }
    lastBeat = currentBeat;

    const secPerBeat     = 60 / bpm;
    const lookaheadBeats = LOOKAHEAD_SEC / secPerBeat;
    const windowEnd      = currentBeat + lookaheadBeats;

    // Advance cursor through all events that fall before the window end.
    while (nextIdx < events.length && events[nextIdx].beat < windowEnd) {
      const ev = events[nextIdx];
      nextIdx++;

      // Skip events that have already passed (beyond tolerance).
      if (ev.beat < currentBeat - PAST_TOLERANCE) continue;

      // Convert beat offset to AudioContext seconds.
      const offsetSec = (ev.beat - currentBeat) * secPerBeat;
      const audioTime = Tone.now() + Math.max(0, offsetSec);

      _dispatch(ev, audioTime);
    }
  }

  // ── _dispatch ─────────────────────────────────────────────────────────────
  function _dispatch(ev, audioTime) {
    switch (ev.type) {
      case 'drum':
        AudioEngine.playDrum(ev.drumType, ev.velocity, audioTime, ev.durSec);
        break;
      case 'melody':
        AudioEngine.playNote(ev.pitch, ev.velocity, audioTime, ev.durSec);
        break;
      case 'chord':
        AudioEngine.playChord(ev.pitches, ev.velocity, audioTime, ev.durSec);
        break;
    }
  }

  // ── patch ─────────────────────────────────────────────────────────────────
  // Hot-swap the event queue from DAW_STATE edits (note drag, mute, etc.).
  // Repositions the cursor to currentBeat so in-progress playback is unaffected.
  function patch(newEvents, currentBeat) {
    events   = [...newEvents].sort((a, b) => a.beat - b.beat);
    lastBeat = currentBeat ?? lastBeat;  // prevent false loop-reset on next process()
    // Rewind cursor to the first event that hasn't cleanly passed yet
    nextIdx = 0;
    const floor = (currentBeat ?? 0) - PAST_TOLERANCE;
    while (nextIdx < events.length && events[nextIdx].beat < floor) nextIdx++;
  }

  return { load, reset, process, patch };
})();
