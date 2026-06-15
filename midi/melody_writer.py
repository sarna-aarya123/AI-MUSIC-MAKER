"""
midi/melody_writer.py
Writes melody events from melody_service output to a MidiBuilder track.

All timing and pitch values are pre-resolved by melody_service.
This writer contains no music-theory logic — it is a pure MIDI translator.

Public API
──────────
  MELODY_CHANNEL  int   1 (channel 0 is used by chords; 1 by convention for melody)
  write_melody(builder, melody_data, track_name, channel, instrument) -> int

Usage
─────
  from midi.builder      import MidiBuilder
  from midi.melody_writer import write_melody
  from backend.services.melody_service import generate_melody

  builder     = MidiBuilder()
  builder.set_tempo(120)
  melody_data = generate_melody(chord_data, octave=5, density=0.75, seed=42)
  track_idx   = write_melody(builder, melody_data)
  builder.save('output.mid')
"""

from __future__ import annotations

from midi.builder import GM_PROGRAMS, MidiBuilder

MELODY_CHANNEL: int = 1  # conventional; channel 0 = chords, 9 = drums


def write_melody(
    builder: MidiBuilder,
    melody_data: dict,
    track_name: str = 'Melody',
    channel: int = MELODY_CHANNEL,
    instrument: str | int = 'piano',
) -> int:
    """
    Add a melody track to builder and write all notes from melody_service output.

    Parameters
    ----------
    builder : MidiBuilder
        The MIDI builder to write into.  Caller is responsible for setting
        tempo and time signature before writing.
    melody_data : dict
        Output from melody_service.generate_melody().
        Must contain a 'notes' list where each note has:
          beat, duration, pitch, velocity  (pitch_name and accent are ignored here)
    track_name : str
        Label for the MIDI track.
    channel : int
        MIDI channel (0-indexed).  Default 1 keeps melody separate from chords.
    instrument : str | int
        GM instrument name (key of GM_PROGRAMS) or raw program number 0-127.
        Default 'piano' (program 0).

    Returns
    -------
    int
        The 0-based track index assigned by MidiBuilder.add_track().
    """
    if isinstance(instrument, str):
        program = GM_PROGRAMS.get(instrument.lower(), 0)
    else:
        program = int(instrument)

    track_idx = builder.add_track(track_name)
    builder.add_program_change(track_idx, channel, program, beat=0.0)

    for note in melody_data['notes']:
        builder.add_note(
            track          = track_idx,
            channel        = channel,
            pitch          = note['pitch'],
            start_beat     = note['beat'],
            duration_beats = note['duration'],
            velocity       = note['velocity'],
        )

    return track_idx
