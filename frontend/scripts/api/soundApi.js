/**
 * soundApi.js
 * Fetch wrappers for the WAV sound-design backend endpoint:
 *   POST /api/sound/generate         — text prompt → WAV one-shot
 *
 * Returns a Blob URL for in-browser playback and direct download.
 * Completely separate from MIDI generation — no shared state.
 */
