"""
audio/feature_extractor.py
Extracts higher-level musical features from audio for use by the
similarity generation pipeline.

Provides:
  extract_features(audio_path) → {
    bpm, key, mode,
    energy,          # RMS energy level → maps to mood intensity
    spectral_centroid,  # brightness → maps to genre hint
    zero_crossing_rate, # noisiness → percussive vs tonal
    estimated_genre,    # heuristic guess: "lo-fi" | "edm" | "jazz" | etc.
    estimated_mood,     # "happy" | "sad" | "energetic" | "calm"
  }

These features are used ONLY as soft constraints for generation.
"""
