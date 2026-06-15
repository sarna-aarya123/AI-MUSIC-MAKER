"""
genres.py
Genre-specific rule profiles that constrain generation.

Public API:
  GENRE_PROFILES   dict  genre_name → GenreProfile dict
  get_genre_profile(genre) → dict  (always returns something, never raises)
  list_genres()            → list[str]

A GenreProfile contains:
  preferred_scales    list[str]   scale names this genre most uses
  bpm_range           (int, int)  typical BPM window (min, max)
  typical_octave      int         chord octave anchor (3-5)
  with_seventh        bool        whether genre expects 7th chords by default
  spread              str         default voicing: 'close' | 'open' | 'drop2'
  chord_density       float       chords per bar (1.0 = one chord per bar)

Consumed by chord_service.py, melody_service.py, and drum_service.py.
No music_theory or midi imports — pure data.
"""

from __future__ import annotations
from typing import TypedDict


class GenreProfile(TypedDict):
    preferred_scales: list[str]
    bpm_range: tuple[int, int]
    typical_octave: int
    with_seventh: bool
    spread: str
    chord_density: float


GENRE_PROFILES: dict[str, GenreProfile] = {
    'pop': {
        'preferred_scales': ['major', 'minor'],
        'bpm_range':        (90, 130),
        'typical_octave':   4,
        'with_seventh':     False,
        'spread':           'close',
        'chord_density':    1.0,
    },
    'jazz': {
        'preferred_scales': ['major', 'dorian', 'harmonic_minor', 'melodic_minor'],
        'bpm_range':        (60, 200),
        'typical_octave':   4,
        'with_seventh':     True,
        'spread':           'drop2',
        'chord_density':    1.0,
    },
    'lo-fi': {
        'preferred_scales': ['major', 'minor', 'dorian'],
        'bpm_range':        (60, 90),
        'typical_octave':   4,
        'with_seventh':     True,
        'spread':           'close',
        'chord_density':    1.0,
    },
    'edm': {
        'preferred_scales': ['minor', 'harmonic_minor'],
        'bpm_range':        (120, 160),
        'typical_octave':   3,
        'with_seventh':     False,
        'spread':           'open',
        'chord_density':    0.5,    # whole notes typical
    },
    'classical': {
        'preferred_scales': ['major', 'minor', 'harmonic_minor'],
        'bpm_range':        (40, 160),
        'typical_octave':   4,
        'with_seventh':     False,
        'spread':           'open',
        'chord_density':    1.0,
    },
    'hip-hop': {
        'preferred_scales': ['minor', 'pentatonic_minor', 'dorian'],
        'bpm_range':        (70, 100),
        'typical_octave':   3,
        'with_seventh':     True,
        'spread':           'close',
        'chord_density':    0.5,
    },
    'rock': {
        'preferred_scales': ['major', 'minor', 'pentatonic_minor'],
        'bpm_range':        (100, 160),
        'typical_octave':   3,
        'with_seventh':     False,
        'spread':           'close',
        'chord_density':    1.0,
    },
    'blues': {
        'preferred_scales': ['blues', 'pentatonic_minor'],
        'bpm_range':        (60, 120),
        'typical_octave':   3,
        'with_seventh':     True,
        'spread':           'close',
        'chord_density':    1.0,
    },
    'ambient': {
        'preferred_scales': ['major', 'lydian', 'pentatonic_major'],
        'bpm_range':        (50, 90),
        'typical_octave':   4,
        'with_seventh':     True,
        'spread':           'open',
        'chord_density':    0.25,   # very sparse, one chord per 4 bars typical
    },
    'bossa nova': {
        'preferred_scales': ['major', 'dorian', 'melodic_minor'],
        'bpm_range':        (100, 140),
        'typical_octave':   4,
        'with_seventh':     True,
        'spread':           'drop2',
        'chord_density':    1.0,
    },
}

# Canonical alias map (handles common user inputs)
_ALIASES: dict[str, str] = {
    'lofi':       'lo-fi',
    'lo_fi':      'lo-fi',
    'hiphop':     'hip-hop',
    'hip_hop':    'hip-hop',
    'bossanova':  'bossa nova',
    'bossa_nova': 'bossa nova',
    'rnb':        'hip-hop',   # rough approximation
    'r&b':        'hip-hop',
    'electronic': 'edm',
    'dance':      'edm',
}

_DEFAULT_PROFILE: GenreProfile = {
    'preferred_scales': ['major', 'minor'],
    'bpm_range':        (80, 140),
    'typical_octave':   4,
    'with_seventh':     False,
    'spread':           'close',
    'chord_density':    1.0,
}


def get_genre_profile(genre: str) -> GenreProfile:
    """
    Return the GenreProfile for a genre name.
    Resolves common aliases. Returns the default profile if unrecognised
    (never raises) so generation always succeeds.

      get_genre_profile('jazz')   → { with_seventh: True, spread: 'drop2', ... }
      get_genre_profile('lofi')   → same as 'lo-fi'
      get_genre_profile('unknown')→ default profile
    """
    key = genre.strip().lower()
    key = _ALIASES.get(key, key)
    return GENRE_PROFILES.get(key, _DEFAULT_PROFILE)


def list_genres() -> list[str]:
    """Return sorted list of supported genre names."""
    return sorted(GENRE_PROFILES)
