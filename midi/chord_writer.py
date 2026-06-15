"""
midi/chord_writer.py
Writes a chord progression (list of chord-note-lists with timing) to a MIDI track.

Provides:
  write_chords(builder, track_idx, chords, bpm, bars, velocity_range)
    chords: list of { notes: [int], start_beat: float, duration_beats: float }
    Handles voicing spread, sustain pedal CC, and velocity humanization.
"""
