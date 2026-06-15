"""
harmony.py
Functional harmony: progression templates and chord quality lookup.

Public API:
  PROGRESSIONS              dict  name → [scale degree ints]
  DIATONIC_QUALITIES        dict  scale → [triad quality per degree 1-7]
  DIATONIC_7TH_QUALITIES    dict  scale → [seventh quality per degree 1-7]
  CHORD_SCALE_FALLBACK      dict  non-heptatonic scale → heptatonic equivalent

  choose_progression(scale, genre)              → str (progression name)
  get_chord_quality(scale, degree, with_seventh) → str (quality key for chords.py)

All quality strings are keys of chords.CHORD_QUALITIES.
No I/O, no MIDI, no audio — pure theory tables and lookup logic.
"""

from __future__ import annotations

# ── Progression templates ──────────────────────────────────────────────────────
# Values are scale-degree sequences (1-based). The quality of each chord is
# determined at runtime via DIATONIC_QUALITIES / DIATONIC_7TH_QUALITIES so
# the same degree list works for any key.

PROGRESSIONS: dict[str, list[int]] = {
    # === Major / Ionian ===
    'I-V-vi-IV':        [1, 5, 6, 4],   # most popular pop
    'I-IV-V-I':         [1, 4, 5, 1],   # classic rock / classical
    'I-vi-IV-V':        [1, 6, 4, 5],   # 1950s / doo-wop
    'I-vi-ii-V':        [1, 6, 2, 5],   # jazz turnaround
    'I-V-IV-I':         [1, 5, 4, 1],   # rock anthem
    'I-IV-I-V':         [1, 4, 1, 5],   # gospel / blues major
    'ii-V-I':           [2, 5, 1],       # jazz cadence
    'I-V-vi-iii-IV':    [1, 5, 6, 3, 4],# extended pop
    # === Minor / Aeolian ===
    'i-VII-VI-VII':     [1, 7, 6, 7],   # natural minor loop
    'i-VI-III-VII':     [1, 6, 3, 7],   # natural minor / epic
    'i-iv-V-i':         [1, 4, 5, 1],   # harmonic minor cadence
    'i-iv-i-V':         [1, 4, 1, 5],   # minor blues
    'i-III-VII-VI':     [1, 3, 7, 6],   # descending minor
    'i-v-VI-VII':       [1, 5, 6, 7],   # minor rise
    # === Modal ===
    'i-IV-i-VII':       [1, 4, 1, 7],   # Dorian vamp
    'I-VII-IV-I':       [1, 7, 4, 1],   # Mixolydian rock
    'I-II-I-V':         [1, 2, 1, 5],   # Lydian float
    'i-II-i-VII':       [1, 2, 1, 7],   # Phrygian tension
}

# ── Diatonic chord quality tables ─────────────────────────────────────────────
# Verified by interval analysis: each entry is the quality of the diatonic
# chord built by stacking thirds at that scale degree.
# Index 0 = degree I, index 6 = degree VII.

DIATONIC_QUALITIES: dict[str, list[str]] = {
    #                        I         II        III       IV        V         VI        VII
    'major':          ['major',  'minor',  'minor',  'major',  'major',  'minor',  'dim'  ],
    'minor':          ['minor',  'dim',    'major',  'minor',  'minor',  'major',  'major'],
    'harmonic_minor': ['minor',  'dim',    'aug',    'minor',  'major',  'major',  'dim'  ],
    'melodic_minor':  ['minor',  'minor',  'aug',    'major',  'major',  'dim',    'dim'  ],
    'dorian':         ['minor',  'minor',  'major',  'major',  'minor',  'dim',    'major'],
    'phrygian':       ['minor',  'major',  'major',  'minor',  'dim',    'major',  'minor'],
    'lydian':         ['major',  'major',  'minor',  'dim',    'major',  'minor',  'minor'],
    'mixolydian':     ['major',  'minor',  'dim',    'major',  'minor',  'minor',  'major'],
    'locrian':        ['dim',    'major',  'minor',  'minor',  'major',  'major',  'minor'],
}

DIATONIC_7TH_QUALITIES: dict[str, list[str]] = {
    #                        I            II            III           IV            V             VI            VII
    'major':          ['maj7',      'min7',      'min7',      'maj7',      'dom7',      'min7',      'half_dim7'],
    'minor':          ['min7',      'half_dim7', 'maj7',      'min7',      'min7',      'maj7',      'dom7'     ],
    'harmonic_minor': ['min_maj7',  'half_dim7', 'aug_maj7',  'min7',      'dom7',      'maj7',      'dim7'     ],
    'melodic_minor':  ['min_maj7',  'min7',      'aug_maj7',  'dom7',      'dom7',      'half_dim7', 'half_dim7'],
    'dorian':         ['min7',      'min7',      'maj7',      'dom7',      'min7',      'half_dim7', 'maj7'     ],
    'phrygian':       ['min7',      'maj7',      'dom7',      'min7',      'half_dim7', 'maj7',      'min7'     ],
    'lydian':         ['maj7',      'dom7',      'min7',      'half_dim7', 'maj7',      'min7',      'min7'     ],
    'mixolydian':     ['dom7',      'min7',      'half_dim7', 'maj7',      'min7',      'min7',      'maj7'     ],
    'locrian':        ['half_dim7', 'maj7',      'min7',      'min7',      'maj7',      'dom7',      'min7'     ],
}

# Non-heptatonic scales cannot use diatonic_chord (which needs 7 notes).
# Map them to the closest heptatonic equivalent for chord generation.
CHORD_SCALE_FALLBACK: dict[str, str] = {
    'pentatonic_major': 'major',
    'pentatonic_minor': 'minor',
    'blues':            'minor',
}

# ── Progression selection ──────────────────────────────────────────────────────

_MODAL_SCALES = frozenset({'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian'})
_MAJOR_FAMILY = frozenset({'major', 'lydian', 'mixolydian', 'pentatonic_major'})

_MODAL_DEFAULTS: dict[str, str] = {
    'dorian':     'i-IV-i-VII',
    'phrygian':   'i-II-i-VII',
    'lydian':     'I-II-I-V',
    'mixolydian': 'I-VII-IV-I',
    'locrian':    'i-III-VII-VI',
}

# Genre → preferred progression name when scale is major-family
_GENRE_MAJOR: dict[str, str] = {
    'pop':        'I-V-vi-IV',
    'jazz':       'I-vi-ii-V',
    'lo-fi':      'I-vi-IV-V',
    'lofi':       'I-vi-IV-V',
    'edm':        'I-IV-V-I',
    'classical':  'I-IV-V-I',
    'hip-hop':    'I-IV-V-I',
    'hiphop':     'I-IV-V-I',
    'rock':       'I-V-IV-I',
    'blues':      'I-IV-I-V',
    'ambient':    'I-vi-IV-V',
    'bossa nova': 'ii-V-I',
    'bossanova':  'ii-V-I',
}

# Genre → preferred progression name when scale is minor-family
_GENRE_MINOR: dict[str, str] = {
    'pop':        'i-VII-VI-VII',
    'jazz':       'i-iv-V-i',
    'lo-fi':      'i-VI-III-VII',
    'lofi':       'i-VI-III-VII',
    'edm':        'i-VI-III-VII',
    'classical':  'i-iv-V-i',
    'hip-hop':    'i-VII-VI-VII',
    'hiphop':     'i-VII-VI-VII',
    'rock':       'i-III-VII-VI',
    'blues':      'i-iv-i-V',
    'ambient':    'i-VI-III-VII',
    'bossa nova': 'i-iv-V-i',
    'bossanova':  'i-iv-V-i',
}

def _normalize_genre(genre: str) -> str:
    return genre.lower().replace(' ', '').replace('-', '').replace('_', '')


def choose_progression(scale: str, genre: str) -> str:
    """
    Return the name of the most appropriate progression for a given
    scale + genre combination.

    Modal scales have fixed defaults that override genre preference because
    their characteristic sound comes from the mode itself.

      choose_progression('major', 'pop')      → 'I-V-vi-IV'
      choose_progression('minor', 'jazz')     → 'i-iv-V-i'
      choose_progression('dorian', 'pop')     → 'i-IV-i-VII'
      choose_progression('mixolydian', 'rock')→ 'I-VII-IV-I'
    """
    # Modal scales always use their characteristic progression
    if scale in _MODAL_DEFAULTS:
        return _MODAL_DEFAULTS[scale]

    # Resolve genre aliases
    g = _normalize_genre(genre)

    if scale in _MAJOR_FAMILY:
        # Try direct match, then strip hyphens/spaces, then default
        return _GENRE_MAJOR.get(genre.lower(), _GENRE_MAJOR.get(g, 'I-V-vi-IV'))
    else:
        return _GENRE_MINOR.get(genre.lower(), _GENRE_MINOR.get(g, 'i-VII-VI-VII'))


def get_chord_quality(scale: str, degree: int, with_seventh: bool = False) -> str:
    """
    Return the chord quality for a given scale degree.

      get_chord_quality('major', 5)               → 'major'  (V in major = major triad)
      get_chord_quality('major', 5, with_seventh) → 'dom7'   (V7 in major = G7)
      get_chord_quality('minor', 7)               → 'major'  (VII in natural minor)
      get_chord_quality('blues', 1)               → 'minor'  (falls back to minor scale)
    """
    if not (1 <= degree <= 7):
        raise ValueError(f"Scale degree must be 1-7, got {degree}.")

    effective = CHORD_SCALE_FALLBACK.get(scale, scale)
    table = DIATONIC_7TH_QUALITIES if with_seventh else DIATONIC_QUALITIES

    if effective not in table:
        raise ValueError(
            f"No chord quality table for scale '{scale}' "
            f"(effective: '{effective}'). "
            f"Supported: {sorted(table)}."
        )
    return table[effective][degree - 1]
