/**
 * analysisApi.js
 * Fetch wrappers for the audio analysis backend endpoints:
 *   POST /api/analysis/detect        — upload MP3, returns { key, bpm, mode }
 *   POST /api/similarity/generate    — upload MP3, returns a new MIDI file
 *
 * Handles multipart/form-data uploads for audio files.
 */
