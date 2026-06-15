"""
midi/builder.py
Multi-track Standard MIDI File (format 1, PPQ=480) composition engine.

Public API:
  MidiBuilder                            — event collector + SMF serialiser
    .add_track(name)        → int        register a music track, return its index
    .set_tempo(bpm)                      set global tempo
    .set_time_signature(num, denom)      set time signature (denom must be power of 2)
    .add_note(track, ch, pitch,          schedule a note-on / note-off pair
              start_beat, dur_beats,
              velocity)
    .add_program_change(track, ch, prog) select a GM instrument
    .add_control_change(track, ch,       send a MIDI CC message (e.g. sustain pedal)
                        cc, value, beat)
    .to_bytes()             → bytes      serialise to raw SMF bytes (safe to call repeatedly)
    .save(path)                          write .mid file to disk
    .track_count            property
    .note_count             property
    .summary()              → dict

  GM_PROGRAMS              dict          common GM instrument name → program number

  build_from_chord_progression(          high-level: chord_service dict → MidiBuilder
      chord_data, instrument,
      velocity_top, velocity_inner)

SMF layout produced:
  Track 0  tempo track  — tempo + time signature (managed by MIDIUtil internally)
  Track 1  user track 0 — first add_track() call  (e.g. "Chords")
  Track 2  user track 1 — second add_track() call (e.g. "Melody")   [future]
  …

No imports from music_theory or backend — pure MIDI construction.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

from midiutil import MIDIFile

# ── Internal event types ───────────────────────────────────────────────────────

@dataclass(slots=True)
class _Note:
    track: int
    channel: int
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int


@dataclass(slots=True)
class _ProgramChange:
    track: int
    channel: int
    program: int
    beat: float


@dataclass(slots=True)
class _ControlChange:
    track: int
    channel: int
    controller: int
    value: int
    beat: float


# ── General MIDI instrument map (subset) ──────────────────────────────────────

GM_PROGRAMS: dict[str, int] = {
    # Piano family
    'piano':        0,
    'bright_piano': 1,
    'epiano':       4,   # Electric Piano 1
    'harpsichord':  6,
    'vibraphone':   11,
    'organ':        16,
    # Guitar / bass
    'guitar':       25,  # Acoustic Guitar (steel)
    'clean_guitar': 27,
    'bass':         32,  # Acoustic Bass
    'electric_bass':33,
    # Strings / pads
    'strings':      48,
    'string_ens':   49,
    'synth_strings':50,
    'choir':        52,
    'pad':          88,  # Pad 1 — New Age
    'warm_pad':     89,
    'polysynth':    90,
    # Brass
    'trumpet':      56,
    'trombone':     57,
    'brass':        61,
    # Woodwinds
    'saxophone':    66,
    'flute':        73,
}


# ── MidiBuilder ────────────────────────────────────────────────────────────────

class MidiBuilder:
    """
    Collects note and control events then serialises to a Standard MIDI File.

    All time values are in *beats* (quarter notes), not ticks.
    MIDIUtil converts beats → ticks internally using PPQ=480.

    A MidiBuilder with N music tracks produces a format-1 file with N+1 tracks:
    the first track is an auto-generated tempo/time-signature track; user tracks
    start at physical track index 1.
    """

    PPQ: int = 480  # ticks per quarter note — matches Ableton, FL Studio, Logic defaults

    def __init__(self) -> None:
        self._track_names: list[str] = []
        self._notes: list[_Note] = []
        self._programs: list[_ProgramChange] = []
        self._cc: list[_ControlChange] = []
        self._tempo: float = 120.0
        self._time_sig: tuple[int, int] = (4, 4)

    # ── Track management ───────────────────────────────────────────────────────

    def add_track(self, name: str = '') -> int:
        """
        Register a new music track and return its 0-based user index.

          track_0 = builder.add_track('Chords')   → 0
          track_1 = builder.add_track('Melody')   → 1
        """
        self._track_names.append(name)
        return len(self._track_names) - 1

    # ── Global settings ────────────────────────────────────────────────────────

    def set_tempo(self, bpm: float) -> None:
        """Set the global tempo. Applied to the tempo track at beat 0."""
        if bpm <= 0:
            raise ValueError(f"BPM must be > 0, got {bpm}.")
        self._tempo = float(bpm)

    def set_time_signature(self, numerator: int, denominator: int) -> None:
        """
        Set the global time signature.
        denominator must be a power of 2: 1, 2, 4, 8, or 16.

          builder.set_time_signature(4, 4)   # 4/4
          builder.set_time_signature(3, 4)   # 3/4
          builder.set_time_signature(6, 8)   # 6/8
        """
        valid_denoms = {1, 2, 4, 8, 16}
        if denominator not in valid_denoms:
            raise ValueError(
                f"Denominator must be a power of 2 {sorted(valid_denoms)}, got {denominator}."
            )
        self._time_sig = (numerator, denominator)

    # ── Note events ────────────────────────────────────────────────────────────

    def add_note(
        self,
        track: int,
        channel: int,
        pitch: int,
        start_beat: float,
        duration_beats: float,
        velocity: int = 80,
    ) -> None:
        """
        Schedule a note-on / note-off pair.

        Args:
            track          : 0-based user track index (returned by add_track)
            channel        : MIDI channel 0-15  (9 = GM drums — reserved)
            pitch          : MIDI note number 0-127
            start_beat     : Start time in beats from bar 0, beat 0
            duration_beats : Duration in beats (must be > 0)
            velocity       : MIDI velocity 1-127  (default 80)
        """
        if not (0 <= pitch <= 127):
            raise ValueError(f"Pitch {pitch} out of range 0-127.")
        if not (1 <= velocity <= 127):
            raise ValueError(f"Velocity {velocity} out of range 1-127.")
        if duration_beats <= 0:
            raise ValueError(f"duration_beats must be > 0, got {duration_beats}.")
        if start_beat < 0:
            raise ValueError(f"start_beat must be >= 0, got {start_beat}.")
        self._notes.append(
            _Note(track, channel, pitch, start_beat, duration_beats, velocity)
        )

    # ── Program / CC events ────────────────────────────────────────────────────

    def add_program_change(
        self,
        track: int,
        channel: int,
        program: int,
        beat: float = 0.0,
    ) -> None:
        """
        Select a General MIDI instrument on a channel.

          builder.add_program_change(0, 0, GM_PROGRAMS['piano'])
          builder.add_program_change(1, 0, GM_PROGRAMS['strings'])
        """
        if not (0 <= program <= 127):
            raise ValueError(f"Program number {program} out of range 0-127.")
        self._programs.append(_ProgramChange(track, channel, program, beat))

    def add_control_change(
        self,
        track: int,
        channel: int,
        controller: int,
        value: int,
        beat: float,
    ) -> None:
        """
        Send a MIDI Continuous Controller (CC) message.

        Common controllers:
          7  = Channel Volume
          10 = Pan
          64 = Sustain pedal (0 = off, 127 = on)
          91 = Reverb depth
        """
        if not (0 <= controller <= 127):
            raise ValueError(f"Controller number {controller} out of range 0-127.")
        if not (0 <= value <= 127):
            raise ValueError(f"CC value {value} out of range 0-127.")
        self._cc.append(_ControlChange(track, channel, controller, value, beat))

    # ── Export ─────────────────────────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        """
        Serialise all registered events to raw Standard MIDI File bytes.

        Output format:
          - SMF format 1 (multi-track)
          - PPQ = 480  (ticks per quarter note)
          - Track 0: tempo + time signature  (MIDIUtil auto-manages this)
          - Track 1+: user tracks in registration order

        Safe to call multiple times — does not mutate internal state.
        """
        n_music_tracks = max(len(self._track_names), 1)

        midi = MIDIFile(
            numTracks=n_music_tracks,
            adjust_origin=False,
            file_format=1,
            ticks_per_quarternote=self.PPQ,
            eventtime_is_ticks=False,   # all our times are in beats
        )

        # ── Tempo track (always track 0 in format 1) ──────────────────────────
        midi.addTempo(0, 0, self._tempo)

        # MIDI spec encodes the denominator as log2(actual denominator)
        log2_denom = int(math.log2(self._time_sig[1]))
        midi.addTimeSignature(
            track=0,
            time=0,
            numerator=self._time_sig[0],
            denominator=log2_denom,
            clocks_per_tick=24,
            notes_per_quarter=8,
        )

        # ── Program changes ───────────────────────────────────────────────────
        for pc in self._programs:
            midi.addProgramChange(pc.track, pc.channel, pc.beat, pc.program)

        # ── CC messages ───────────────────────────────────────────────────────
        for cc in self._cc:
            midi.addControllerEvent(
                cc.track, cc.channel, cc.beat, cc.controller, cc.value
            )

        # ── Notes ─────────────────────────────────────────────────────────────
        for n in self._notes:
            midi.addNote(
                n.track, n.channel, n.pitch,
                n.start_beat, n.duration_beats, n.velocity,
            )

        buf = io.BytesIO()
        midi.writeFile(buf)
        return buf.getvalue()

    def save(self, path: str | Path) -> None:
        """Write the MIDI file to *path*. Creates parent directories if needed."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.to_bytes())

    # ── Introspection ──────────────────────────────────────────────────────────

    @property
    def track_count(self) -> int:
        """Number of registered user music tracks (excludes the tempo track)."""
        return len(self._track_names)

    @property
    def note_count(self) -> int:
        """Total number of scheduled note events across all tracks."""
        return len(self._notes)

    def summary(self) -> dict:
        """Return a JSON-serialisable summary of the builder's current state."""
        return {
            'bpm':             self._tempo,
            'time_signature':  list(self._time_sig),
            'ppq':             self.PPQ,
            'tracks':          list(self._track_names),
            'note_count':      len(self._notes),
            'program_changes': len(self._programs),
            'cc_events':       len(self._cc),
        }


# ── High-level builder ────────────────────────────────────────────────────────

def build_from_chord_progression(
    chord_data: dict,
    instrument: str | int = 'piano',
    velocity_top: int = 85,
    velocity_inner: int = 72,
) -> MidiBuilder:
    """
    Convert the output of ``chord_service.generate_chord_progression()``
    into a MidiBuilder populated with a single 'Chords' track (track index 0).

    The top note of each voiced chord receives ``velocity_top`` to naturally
    emphasise the melodic voice; all other notes receive ``velocity_inner``.
    Additional tracks (melody, drums) can be added to the returned builder
    before calling ``to_bytes()`` / ``save()``.

    Args:
        chord_data      : dict returned by chord_service.generate_chord_progression()
        instrument      : GM instrument name (key of GM_PROGRAMS) or raw 0-127 int
                          Default 'piano' (program 0).
        velocity_top    : MIDI velocity for the highest note in each chord (1-127)
        velocity_inner  : MIDI velocity for all inner notes (1-127)

    Returns:
        MidiBuilder  — ready for to_bytes() or save(), or further track additions.

    Example:
        from backend.services.chord_service import generate_chord_progression
        from midi.builder import build_from_chord_progression

        data    = generate_chord_progression('C', 'major', genre='jazz', bars=8)
        builder = build_from_chord_progression(data, instrument='epiano')
        builder.save('output/chords.mid')
    """
    # Resolve instrument to a GM program number
    if isinstance(instrument, str):
        program = GM_PROGRAMS.get(instrument.lower(), 0)
    else:
        program = int(instrument)
        if not (0 <= program <= 127):
            raise ValueError(f"GM program {program} out of range 0-127.")

    builder = MidiBuilder()

    # Global metadata from chord_service output
    builder.set_tempo(chord_data['bpm'])
    ts = chord_data.get('time_signature', [4, 4])
    builder.set_time_signature(ts[0], ts[1])

    # Track 0 — Chords
    track_idx = builder.add_track('Chords')
    channel   = 0
    builder.add_program_change(track_idx, channel, program)

    for chord in chord_data['chords']:
        notes    = chord['notes']          # sorted ascending by voice_chord()
        start    = chord['beat_start']
        duration = chord['beat_duration']

        for i, pitch in enumerate(notes):
            is_top   = (i == len(notes) - 1)
            velocity = velocity_top if is_top else velocity_inner
            builder.add_note(track_idx, channel, pitch, start, duration, velocity)

    return builder
