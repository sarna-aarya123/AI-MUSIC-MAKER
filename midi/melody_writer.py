"""
midi/melody_writer.py
Writes a melody (list of note events with timing) to a MIDI track.

Provides:
  write_melody(builder, track_idx, notes, bpm, velocity_range)
    notes: list of { pitch: int, start_beat: float, duration_beats: float }
    Applies legato/staccato articulation based on note density.
"""
