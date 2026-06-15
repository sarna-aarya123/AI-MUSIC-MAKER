"""
services/drum_service.py
Orchestrates drum pattern generation.

Calls:
  music_theory/rhythm.py    → base grid patterns (kick, snare, hi-hat, etc.)
  music_theory/genres.py    → genre-specific groove templates
  midi/drum_writer.py       → write drum pattern to MIDI channel 10

Returns: { midi_bytes, pattern_grid }
"""
