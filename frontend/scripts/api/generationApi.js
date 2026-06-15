/**
 * generationApi.js
 * Fetch wrappers for the music generation backend endpoints:
 *   POST /api/generate/chords
 *   POST /api/generate/melody
 *   POST /api/generate/drums
 *   POST /api/generate/composition   (full song — chords + melody + drums)
 *
 * Each function accepts a params object and returns a Promise
 * resolving to { midi_b64, preview_notes, metadata }.
 */
