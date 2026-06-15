"""
scales.py
Scale and key definitions using semitone intervals.

Public API:
  SCALES              dict  scale_name → [semitone intervals from root]
  MOOD_TO_SCALE       dict  mood alias → scale name
  resolve_mode(mode)        mood/alias → canonical scale key
  get_scale_notes(key, mode, octave_min, octave_max) → [MIDI ints]
  notes_in_octave(key, mode, octave)                 → [MIDI ints]
  get_note_name(midi_note)  → "C4", "F#3"
  get_midi_number(note_name) → 60
  scale_degree(midi_note, key, mode) → 1-7 or None

MIDI convention used throughout: middle C = C4 = 60, C-1 = 0.
"""

from __future__ import annotations

import re

# ── Chromatic reference ────────────────────────────────────────────────────────

CHROMATIC_NOTES: list[str] = [
    'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B',
]

# Flat/enharmonic spellings → canonical sharp spelling
ENHARMONIC_MAP: dict[str, str] = {
    'Db': 'C#', 'Eb': 'D#', 'Fb': 'E',
    'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B',
}

MIDI_MIN = 0
MIDI_MAX = 127

# ── Scale interval tables ──────────────────────────────────────────────────────

SCALES: dict[str, list[int]] = {
    # Diatonic modes
    'major':            [0, 2, 4, 5, 7, 9, 11],
    'minor':            [0, 2, 3, 5, 7, 8, 10],   # natural minor
    'harmonic_minor':   [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor':    [0, 2, 3, 5, 7, 9, 11],   # ascending form
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'phrygian':         [0, 1, 3, 5, 7, 8, 10],
    'lydian':           [0, 2, 4, 6, 7, 9, 11],
    'mixolydian':       [0, 2, 4, 5, 7, 9, 10],
    'locrian':          [0, 1, 3, 5, 6, 8, 10],
    # Pentatonic / blues
    'pentatonic_major': [0, 2, 4, 7, 9],
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'blues':            [0, 3, 5, 6, 7, 10],
}

# Human-readable degree names for each scale (index 0 = degree I)
DEGREE_NAMES: dict[str, list[str]] = {
    'major':           ['I',  'II',  'III', 'IV', 'V',   'VI',  'VII'],
    'minor':           ['i',  'ii°', 'III', 'iv', 'v',   'VI',  'VII'],
    'harmonic_minor':  ['i',  'ii°', 'III+','iv', 'V',   'VI',  'vii°'],
    'dorian':          ['i',  'II',  'III', 'IV', 'v',   'vi°', 'VII'],
    'mixolydian':      ['I',  'II',  'iii', 'IV', 'v',   'vi°', 'VII'],
}

# ── Mood / genre aliases ───────────────────────────────────────────────────────

MOOD_TO_SCALE: dict[str, str] = {
    'happy':        'major',
    'energetic':    'major',
    'upbeat':       'major',
    'sad':          'minor',
    'melancholy':   'pentatonic_minor',
    'dark':         'harmonic_minor',
    'mysterious':   'locrian',
    'jazzy':        'dorian',
    'funky':        'mixolydian',
    'exotic':       'phrygian',
    'dreamy':       'lydian',
    'ethereal':     'lydian',
    'calm':         'pentatonic_major',
    'peaceful':     'pentatonic_major',
    'soulful':      'blues',
    'tense':        'harmonic_minor',
}

# ── Internal helpers ───────────────────────────────────────────────────────────

def _normalize_key(key: str) -> str:
    """Title-case a key name and resolve flat spellings to sharp canonical form."""
    key = key.strip().title()
    return ENHARMONIC_MAP.get(key, key)


def _root_semitone(key: str) -> int:
    """Return 0-11 chromatic index for a key name.  'F#' → 6, 'Bb' → 10."""
    canonical = _normalize_key(key)
    if canonical not in CHROMATIC_NOTES:
        raise ValueError(
            f"Unknown key: '{key}'. "
            f"Use note names like C, D, F#, Bb (flats are auto-converted)."
        )
    return CHROMATIC_NOTES.index(canonical)

# ── Public API ─────────────────────────────────────────────────────────────────

def resolve_mode(mode: str) -> str:
    """
    Return a canonical SCALES key from a scale name or mood alias.

      resolve_mode('happy')    → 'major'
      resolve_mode('dorian')   → 'dorian'
      resolve_mode('Lydian')   → 'lydian'
    """
    normalized = mode.strip().lower().replace(' ', '_')
    if normalized in SCALES:
        return normalized
    if normalized in MOOD_TO_SCALE:
        return MOOD_TO_SCALE[normalized]
    raise ValueError(
        f"Unknown mode/mood: '{mode}'. "
        f"Valid scales: {sorted(SCALES)}. "
        f"Valid moods: {sorted(MOOD_TO_SCALE)}."
    )


def get_scale_notes(
    key: str,
    mode: str,
    octave_min: int = 2,
    octave_max: int = 6,
) -> list[int]:
    """
    Return all MIDI note numbers belonging to the given key/mode
    across the octave range [octave_min, octave_max] inclusive.

    Notes that fall outside 0-127 are silently discarded.

    Example:
      get_scale_notes('C', 'major', octave_min=4, octave_max=4)
      → [60, 62, 64, 65, 67, 69, 71]   # C4 D4 E4 F4 G4 A4 B4
    """
    root = _root_semitone(key)
    intervals = SCALES[resolve_mode(mode)]

    notes: set[int] = set()
    for octave in range(octave_min, octave_max + 1):
        c_midi = (octave + 1) * 12          # MIDI number for C in this octave
        for interval in intervals:
            midi = c_midi + root + interval
            if MIDI_MIN <= midi <= MIDI_MAX:
                notes.add(midi)

    return sorted(notes)


def notes_in_octave(key: str, mode: str, octave: int) -> list[int]:
    """
    Return the MIDI notes for a single octave of the scale
    (convenience wrapper around get_scale_notes).
    """
    return get_scale_notes(key, mode, octave_min=octave, octave_max=octave)


def get_note_name(midi_note: int) -> str:
    """
    Convert a MIDI note number to a human-readable string.

      get_note_name(60)  → 'C4'
      get_note_name(61)  → 'C#4'
      get_note_name(57)  → 'A3'
      get_note_name(0)   → 'C-1'
    """
    if not (MIDI_MIN <= midi_note <= MIDI_MAX):
        raise ValueError(f"MIDI note {midi_note} is out of range 0-127.")
    octave = (midi_note // 12) - 1
    note = CHROMATIC_NOTES[midi_note % 12]
    return f"{note}{octave}"


def get_midi_number(note_name: str) -> int:
    """
    Convert a note name (with octave) to a MIDI number.

      get_midi_number('C4')   → 60
      get_midi_number('F#3')  → 54
      get_midi_number('Bb5')  → 82
      get_midi_number('C-1')  → 0
    """
    match = re.match(r'^([A-Ga-g][#b]?)(-?\d+)$', note_name.strip())
    if not match:
        raise ValueError(
            f"Cannot parse note name: '{note_name}'. "
            f"Expected format like 'C4', 'F#3', 'Bb5', 'C-1'."
        )
    note_part, octave_str = match.groups()
    canonical = _normalize_key(note_part)
    if canonical not in CHROMATIC_NOTES:
        raise ValueError(f"Unknown note: '{note_part}'.")
    semitone = CHROMATIC_NOTES.index(canonical)
    midi = (int(octave_str) + 1) * 12 + semitone
    if not (MIDI_MIN <= midi <= MIDI_MAX):
        raise ValueError(
            f"'{note_name}' maps to MIDI {midi}, which is out of range 0-127."
        )
    return midi


def scale_degree(midi_note: int, key: str, mode: str) -> int | None:
    """
    Return the 1-based scale degree of a MIDI note in the given key/mode,
    or None if the note is chromatic (not in the scale).

      scale_degree(60, 'C', 'major') → 1   (C is degree I)
      scale_degree(62, 'C', 'major') → 2   (D is degree II)
      scale_degree(61, 'C', 'major') → None (C# is not in C major)
    """
    root = _root_semitone(key)
    intervals = SCALES[resolve_mode(mode)]
    offset = (midi_note - root) % 12
    if offset in intervals:
        return intervals.index(offset) + 1
    return None
