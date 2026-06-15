"""
services/similarity_service.py
Orchestrates the "inspired-by" MIDI generation pipeline.

Steps:
  1. analysis_service.py    → detect key, BPM, mood from uploaded MP3
  2. chord_service.py       → generate new chords constrained by detected key/mood
  3. melody_service.py      → generate new melody over those chords
  4. drum_service.py        → generate new drums at detected BPM
  5. midi/builder.py        → combine tracks into one MIDI file

Audio is never copied — only its detected features act as constraints.
Returns: { midi_bytes, detected_features }
"""
