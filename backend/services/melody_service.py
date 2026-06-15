"""
services/melody_service.py
Orchestrates melody generation over a given chord progression.

Calls:
  music_theory/scales.py    → valid melody notes per chord
  music_theory/rhythm.py    → rhythmic variation patterns
  music_theory/genres.py    → genre-appropriate phrasing rules
  midi/melody_writer.py     → write melody to a MIDI track

Returns: { midi_bytes, note_events }
"""
