"""
audio/analyzer.py
Core audio analysis using librosa.

Provides:
  detect_bpm(audio_path)          → float (beats per minute)
  detect_key(audio_path)          → { key: str, mode: "major"|"minor", confidence: float }
  detect_bpm_and_key(audio_path)  → combined result dict

Uses chromagram + Krumhansl-Schmuckler key-finding algorithm for key detection.
Uses librosa.beat.beat_track for BPM estimation.
"""
