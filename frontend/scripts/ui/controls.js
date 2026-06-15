/**
 * controls.js
 * Renders and manages the main control panel UI:
 *   - Key selector (C, C#, D … B)
 *   - Mode/mood selector (major, minor, dorian, mixolydian, etc.)
 *   - Genre selector (pop, jazz, lo-fi, edm, classical, etc.)
 *   - BPM slider + numeric input
 *   - Octave range picker (low/mid/high or explicit range)
 *   - Note duration selector (whole, half, quarter, eighth, sixteenth)
 *   - Generate buttons (chords / melody / drums / full composition)
 *
 * Emits a CustomEvent("generate-requested", { detail: params }) on submit.
 */
