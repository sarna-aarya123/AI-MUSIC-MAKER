"""
chords.py
Chord construction from root notes and scale degrees.

Public API:
  CHORD_QUALITIES     dict  quality_name → [semitone intervals from root]
  CHORD_SYMBOLS       dict  quality_name → display string (e.g. 'm7', 'maj7')

  build_chord(root_midi, quality)                     → [MIDI ints]
  build_triad(root_midi, quality)                     → [MIDI ints]  (3-note shortcut)
  build_seventh(root_midi, quality)                   → [MIDI ints]  (4-note shortcut)

  diatonic_chord(scale_notes_octave, degree, with_seventh) → [MIDI ints]

  invert(notes, inversion)                            → [MIDI ints]
  voice_chord(notes, inversion, spread)               → [MIDI ints]

  chord_name(root_midi, quality)                      → str  e.g. "Cmaj7", "Dm"
  pitch_class_name(midi_note)                         → str  e.g. "C", "F#"

No imports from other music_theory modules — this module is a standalone
building block consumed by chord_service.py and harmony.py.
"""

from __future__ import annotations

# ── Chromatic reference (duplicated intentionally — no circular imports) ──────

_CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# ── Chord quality tables ───────────────────────────────────────────────────────

CHORD_QUALITIES: dict[str, list[int]] = {
    # ── Triads ──────────────────────────────────────────────────────────────
    'major':       [0, 4, 7],
    'minor':       [0, 3, 7],
    'dim':         [0, 3, 6],
    'aug':         [0, 4, 8],
    'sus2':        [0, 2, 7],
    'sus4':        [0, 5, 7],
    # ── Seventh chords ───────────────────────────────────────────────────────
    'maj7':        [0, 4, 7, 11],
    'dom7':        [0, 4, 7, 10],
    'min7':        [0, 3, 7, 10],
    'half_dim7':   [0, 3, 6, 10],   # aka m7♭5
    'dim7':        [0, 3, 6, 9],
    'min_maj7':    [0, 3, 7, 11],   # minor triad + major 7th
    'aug_maj7':    [0, 4, 8, 11],
    # ── Colour / extensions ──────────────────────────────────────────────────
    'add9':        [0, 4, 7, 14],
    'maj9':        [0, 4, 7, 11, 14],
    'dom9':        [0, 4, 7, 10, 14],
    'min9':        [0, 3, 7, 10, 14],
}

# Short display symbols, parallel to CHORD_QUALITIES
CHORD_SYMBOLS: dict[str, str] = {
    'major':     '',
    'minor':     'm',
    'dim':       'dim',
    'aug':       'aug',
    'sus2':      'sus2',
    'sus4':      'sus4',
    'maj7':      'maj7',
    'dom7':      '7',
    'min7':      'm7',
    'half_dim7': 'm7♭5',
    'dim7':      'dim7',
    'min_maj7':  'mMaj7',
    'aug_maj7':  'augMaj7',
    'add9':      'add9',
    'maj9':      'maj9',
    'dom9':      '9',
    'min9':      'm9',
}

# Valid spread values accepted by voice_chord
_SPREADS = ('close', 'open', 'drop2')

# ── Helpers ────────────────────────────────────────────────────────────────────

def pitch_class_name(midi_note: int) -> str:
    """Return the pitch class (no octave): 60 → 'C', 66 → 'F#'."""
    return _CHROMATIC[midi_note % 12]


def _close_position(notes: list[int]) -> list[int]:
    """
    Re-voice a list of MIDI notes into close position starting from the
    lowest note. Each subsequent pitch class is placed in the nearest
    octave strictly above the previous note.
    """
    if not notes:
        return []
    result = [notes[0]]
    for note in notes[1:]:
        pc = note % 12
        prev = result[-1]
        candidate = (prev // 12) * 12 + pc
        if candidate <= prev:
            candidate += 12
        result.append(candidate)
    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def build_chord(root_midi: int, quality: str) -> list[int]:
    """
    Build a chord from a root MIDI note and a quality name.

      build_chord(60, 'major')   → [60, 64, 67]        C major
      build_chord(60, 'maj7')    → [60, 64, 67, 71]     Cmaj7
      build_chord(62, 'min7')    → [62, 65, 69, 72]     Dm7
    """
    if quality not in CHORD_QUALITIES:
        raise ValueError(
            f"Unknown chord quality: '{quality}'. "
            f"Valid qualities: {sorted(CHORD_QUALITIES)}."
        )
    intervals = CHORD_QUALITIES[quality]
    return [root_midi + i for i in intervals]


def build_triad(root_midi: int, quality: str) -> list[int]:
    """
    Convenience wrapper — returns only the first three notes of the quality.
    Useful for qualities that also have a seventh (e.g. 'maj7' → [R, 3, 5]).
    """
    return build_chord(root_midi, quality)[:3]


def build_seventh(root_midi: int, quality: str) -> list[int]:
    """
    Convenience wrapper — builds a four-note chord.
    Falls back to a triad if the quality has fewer than 4 tones.
    """
    notes = build_chord(root_midi, quality)
    return notes[:4]


def diatonic_chord(
    scale_notes_octave: list[int],
    degree: int,
    with_seventh: bool = False,
) -> list[int]:
    """
    Build a chord by stacking thirds on the given scale degree.

    scale_notes_octave must be the 7 notes of a heptatonic scale for one
    octave (as returned by notes_in_octave from scales.py).  Notes that
    wrap past the 7th degree are automatically placed one octave higher.

    Example — C major, degree 5, no seventh:
      scale = [60,62,64,65,67,69,71]  (C4…B4)
      diatonic_chord(scale, 5) → [67, 71, 74]   G4 B4 D5  (G major)

    Example — C major, degree 2, with seventh:
      diatonic_chord(scale, 2, with_seventh=True) → [62, 65, 69, 72]  Dm7
    """
    n = len(scale_notes_octave)
    if n != 7:
        raise ValueError(
            f"diatonic_chord requires a 7-note (heptatonic) scale, got {n}. "
            "Use major, minor, or a church mode — not pentatonic or blues."
        )
    if not (1 <= degree <= 7):
        raise ValueError(f"Scale degree must be 1-7, got {degree}.")

    root_idx = degree - 1
    stacking_steps = [0, 2, 4, 6] if with_seventh else [0, 2, 4]

    notes: list[int] = []
    for step in stacking_steps:
        idx = (root_idx + step) % n
        octave_shifts = (root_idx + step) // n
        notes.append(scale_notes_octave[idx] + 12 * octave_shifts)

    return notes


def invert(notes: list[int], inversion: int) -> list[int]:
    """
    Rotate notes so the given inversion number is in the bass.

      inversion=0  root position     [C4, E4, G4]
      inversion=1  first inversion   [E4, G4, C5]
      inversion=2  second inversion  [G4, C5, E5]

    inversion is taken mod len(notes), so it wraps safely.
    """
    if not notes:
        return []
    n = len(notes)
    inv = inversion % n
    return notes[inv:] + [note + 12 for note in notes[:inv]]


def voice_chord(
    notes: list[int],
    inversion: int = 0,
    spread: str = 'close',
) -> list[int]:
    """
    Apply inversion then spread voicing to a chord.

    spread options:
      'close'  — all notes packed into the tightest possible range
      'open'   — alternate notes raised an octave for a wider, airier sound
      'drop2'  — close position, second-highest voice dropped an octave
                 (4-voice jazz standard voicing; ignored for triads)

    Returns a sorted list of MIDI note numbers.

    Example:
      voice_chord([60, 64, 67, 71], inversion=1, spread='drop2')
      → first-inversion Cmaj7 in drop-2 voicing
    """
    if spread not in _SPREADS:
        raise ValueError(f"spread must be one of {_SPREADS}, got '{spread}'.")

    # 1. Apply inversion
    inverted = invert(notes, inversion)

    # 2. Apply spread
    close = _close_position(inverted)

    if spread == 'close':
        return sorted(close)

    if spread == 'open':
        result = []
        for i, note in enumerate(close):
            result.append(note + 12 if i % 2 == 1 else note)
        return sorted(result)

    # drop2 — meaningful only for 4+ voices
    if spread == 'drop2':
        if len(close) < 4:
            return sorted(close)  # silently fall back for triads
        ordered = sorted(close)
        # Second-highest note = index -2
        ordered[-2] -= 12
        return sorted(ordered)

    return sorted(close)  # unreachable, but satisfies type checkers


def chord_name(root_midi: int, quality: str) -> str:
    """
    Return a human-readable chord symbol.

      chord_name(60, 'major')  → 'C'
      chord_name(62, 'min7')   → 'Dm7'
      chord_name(67, 'dom7')   → 'G7'
      chord_name(71, 'dim')    → 'Bdim'
    """
    if quality not in CHORD_SYMBOLS:
        raise ValueError(f"Unknown quality for display: '{quality}'.")
    return pitch_class_name(root_midi) + CHORD_SYMBOLS[quality]
