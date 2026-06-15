"""
services/sound_service.py
Orchestrates WAV one-shot sound generation from a text prompt.

Calls:
  sound/wav_generator.py    → synthesize or model-generate the WAV

Completely separate from music_theory and midi modules.
Returns: { wav_bytes, sample_rate, duration_ms }
"""
