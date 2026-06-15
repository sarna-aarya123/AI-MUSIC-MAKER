"""
sound/wav_generator.py
Generates WAV one-shot sounds from a text prompt.

Approach options (selected at implementation time):
  A. Synthesis-based: parse prompt → map to oscillator/envelope/filter params
     → synthesize with numpy/scipy, output WAV bytes
  B. Model-based: send prompt to an audio generation model API
     → receive WAV → pass through as bytes

Provides:
  generate_wav(prompt, sound_type, duration_ms, sample_rate=44100) → bytes (WAV)
  SOUND_TYPE_HINTS   — list of recognized hint strings: "kick", "snare",
                       "hihat", "pad", "synth", "bass", "fx", "string"

Output is always 44.1 kHz, 16-bit mono WAV — compatible with all DAWs.
"""
