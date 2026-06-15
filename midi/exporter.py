"""
midi/exporter.py
Final MIDI packaging and export utilities.

Provides:
  export_to_bytes(builder)   → raw SMF bytes, ready for download
  export_to_file(builder, path) → writes .mid file to disk
  export_multitrack(tracks)  → combines separate chord/melody/drum builders
                               into a single format-1 MIDI file
  validate_midi(midi_bytes)  → basic sanity checks (tempo, track count, note range)
"""
