"""
services/analysis_service.py
Orchestrates audio analysis of uploaded MP3 files.

Calls:
  audio/analyzer.py         → librosa-based BPM and key detection
  audio/feature_extractor.py → additional spectral/timbral features

Returns: { key, mode, bpm, confidence, features }
"""
