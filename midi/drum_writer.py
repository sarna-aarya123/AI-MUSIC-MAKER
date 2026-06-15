"""
midi/drum_writer.py
Writes a drum pattern to MIDI channel 10 (General MIDI percussion).

Provides:
  write_drums(builder, track_idx, pattern_grid, bpm, bars)
    pattern_grid: dict of { gm_note: [beat positions] }
                  e.g. { 36: [0,2], 38: [1,3], 42: [0,0.5,1,...] }

GM drum note map constants included here (KICK=36, SNARE=38, etc.).
"""
