"""
services/chord_service.py
Generates diatonic chord progressions grounded in real music theory.

Public API:
  generate_chord_progression(**params) → dict

The returned dict is JSON-serialisable and contains:
  key, mode, scale, genre, bpm, bars, time_signature,
  progression_name, with_seventh, spread,
  chords: list of chord event dicts

Each chord event:
  degree          int        1-7 scale degree
  degree_label    str        Roman numeral (I, ii°, IV, etc.)
  quality         str        chord quality key (major, min7, dom7, ...)
  label           str        display name  (C, Dm7, G7, ...)
  notes           list[int]  voiced MIDI note numbers
  note_names      list[str]  human-readable names  (C4, E4, G4)
  beat_start      float      beat number where chord begins (0-indexed)
  beat_duration   float      number of beats this chord lasts

Pipeline:
  1. scales.resolve_mode       → canonical scale name
  2. harmony.CHORD_SCALE_FALLBACK → heptatonic equivalent (for pentatonic/blues)
  3. scales.notes_in_octave    → 7-note scale for chord building
  4. harmony.choose_progression → best progression for scale + genre
  5. harmony.get_chord_quality  → correct diatonic quality per degree
  6. chords.diatonic_chord     → MIDI notes stacked from scale degrees
  7. chords.voice_chord        → apply inversion + spread voicing
  8. Package timing, labels, note names → return
"""

from __future__ import annotations

from music_theory.scales import (
    resolve_mode,
    notes_in_octave,
    get_note_name,
)
from music_theory.chords import (
    diatonic_chord,
    voice_chord,
    chord_name,
    pitch_class_name,
)
from music_theory.harmony import (
    PROGRESSIONS,
    CHORD_SCALE_FALLBACK,
    choose_progression,
    get_chord_quality,
)
from music_theory.genres import get_genre_profile

# ── Roman numeral helpers ──────────────────────────────────────────────────────

_ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']

def _degree_label(degree: int, quality: str) -> str:
    """
    Return a Roman numeral label reflecting the chord quality.
      major/dom7/maj7/aug  → uppercase (I, V, IV)
      minor/min7/min_maj7  → lowercase (i, iv, ii)
      dim/half_dim7/dim7   → lowercase + ° (vii°)
      aug                  → uppercase + + (III+)
    """
    roman = _ROMAN[degree - 1]
    if quality in ('dim', 'half_dim7', 'dim7'):
        return roman.lower() + '°'
    if quality == 'aug':
        return roman + '+'
    if quality in ('major', 'dom7', 'maj7', 'aug_maj7', 'add9', 'maj9', 'dom9'):
        return roman
    # minor family (minor, min7, min_maj7, min9, sus2, sus4)
    return roman.lower()

# ── Octave safety ──────────────────────────────────────────────────────────────

def _safe_octave(octave: int) -> int:
    """Clamp octave so the chord notes stay within MIDI range 0-127."""
    return max(1, min(octave, 6))

# ── Public service function ────────────────────────────────────────────────────

def generate_chord_progression(
    key: str,
    mode: str,
    genre: str = 'pop',
    bpm: int = 120,
    bars: int = 4,
    octave: int = 4,
    with_seventh: bool | None = None,
    spread: str | None = None,
) -> dict:
    """
    Generate a diatonic chord progression.

    Parameters
    ----------
    key          : Root note, e.g. 'C', 'F#', 'Bb'
    mode         : Scale name or mood alias ('major', 'minor', 'happy', 'jazzy', …)
    genre        : Genre name ('pop', 'jazz', 'lo-fi', 'edm', …)
    bpm          : Tempo in beats per minute
    bars         : Length of progression in bars (4/4 time)
    octave       : Octave anchor for chord voicing (typically 3-5)
    with_seventh : Include 7th notes. None → use genre default.
    spread       : Voicing spread ('close', 'open', 'drop2'). None → genre default.

    Returns
    -------
    dict  JSON-serialisable progression data (see module docstring).
    """
    # ── 1. Resolve inputs ────────────────────────────────────────────────────
    canonical_scale = resolve_mode(mode)
    genre_profile   = get_genre_profile(genre)
    octave          = _safe_octave(octave)

    # Apply genre defaults for unspecified params
    if with_seventh is None:
        with_seventh = genre_profile['with_seventh']
    if spread is None:
        spread = genre_profile['spread']

    # ── 2. Get heptatonic scale notes for this octave ────────────────────────
    # Non-heptatonic scales (pentatonic, blues) fall back to a 7-note equivalent
    # so diatonic_chord can stack thirds correctly.
    chord_scale = CHORD_SCALE_FALLBACK.get(canonical_scale, canonical_scale)
    scale_notes = notes_in_octave(key, chord_scale, octave)

    # ── 3. Choose + resolve progression ─────────────────────────────────────
    prog_name = choose_progression(canonical_scale, genre)
    degrees   = PROGRESSIONS[prog_name]
    n_chords  = len(degrees)

    # ── 4. Timing: evenly distribute beats across bars (4/4) ─────────────────
    total_beats    = bars * 4
    beat_duration  = total_beats / n_chords

    # ── 5. Build each chord ──────────────────────────────────────────────────
    chords: list[dict] = []
    for i, degree in enumerate(degrees):
        quality = get_chord_quality(chord_scale, degree, with_seventh)

        # Build raw diatonic notes (stacked thirds from scale)
        raw_notes = diatonic_chord(scale_notes, degree, with_seventh=with_seventh)
        chord_root = raw_notes[0]   # preserve root before voicing may reorder notes

        # Apply voicing (inversion 0 = root position)
        voiced = voice_chord(raw_notes, inversion=0, spread=spread)

        chords.append({
            'degree':       degree,
            'degree_label': _degree_label(degree, quality),
            'quality':      quality,
            'label':        chord_name(chord_root, quality),   # root, not bass after drop2
            'notes':        voiced,
            'note_names':   [get_note_name(n) for n in voiced],
            'beat_start':   round(i * beat_duration, 4),
            'beat_duration': round(beat_duration, 4),
        })

    # ── 6. Return structured result ───────────────────────────────────────────
    return {
        'key':              key,
        'mode':             mode,
        'scale':            canonical_scale,
        'chord_scale':      chord_scale,
        'genre':            genre,
        'bpm':              bpm,
        'bars':             bars,
        'time_signature':   [4, 4],
        'progression_name': prog_name,
        'with_seventh':     with_seventh,
        'spread':           spread,
        'chords':           chords,
    }
