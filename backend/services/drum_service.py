"""
backend/services/drum_service.py
Generates structured drum events from genre-based rhythmic templates.

Relies entirely on music_theory/rhythm.py for timing: beat positions, swing,
durations, and per-voice accent levels come from generate_rhythm_pattern().
This service adds:
  · GM note number mapping (kick=36, snare=38, etc.)
  · Per-voice humanization with independent but deterministic seeds
  · Phrase-end fill variations (every N bars) for realism

Public API
──────────
  GM_DRUM_MAP  dict[str, int]  voice name → General MIDI note number
  generate_drums(genre, bars, bpm, seed, variation_bars) → dict

Input
  genre         'pop' | 'hip-hop' | 'jazz' | 'lo-fi' | 'edm' (aliases accepted)
  bars          number of bars to generate (≥ 1)
  bpm           tempo — stored in output, not used for timing (rhythm.py is beat-based)
  seed          RNG seed for reproducible humanization and fill randomness
  variation_bars apply a drum fill at the end of every N bars (0 = disabled)

Output
  {
    genre, bpm, bars,
    events: [
      { beat, duration, velocity, drum_type, pitch, accent }
      ...
    ]
  }

  drum_type  voice name ('kick', 'snare', 'hihat', ...)
  pitch      GM percussion note number for channel 9

Integration with midi/drum_writer.py
─────────────────────────────────────
  drum_writer receives the 'events' list and calls:

    builder.add_note(
        track          = drum_track_idx,
        channel        = 9,
        pitch          = ev['pitch'],
        start_beat     = ev['beat'],
        duration_beats = ev['duration'],
        velocity       = ev['velocity'],
    )

  The writer needs no knowledge of music theory or GM mapping — every value
  is resolved here.
"""

from __future__ import annotations

import random

from music_theory.rhythm import RhythmEvent, apply_humanization, generate_rhythm_pattern

# ── General MIDI drum note numbers (channel 9) ────────────────────────────────

GM_DRUM_MAP: dict[str, int] = {
    'kick':     36,   # Bass Drum 1
    'rim':      37,   # Side Stick
    'snare':    38,   # Acoustic Snare
    'clap':     39,   # Hand Clap
    'tom_lo':   41,   # Low Floor Tom
    'hihat':    42,   # Closed Hi-Hat
    'open_hat': 46,   # Open Hi-Hat
    'tom_mid':  47,   # Low-Mid Tom
    'crash':    49,   # Crash Cymbal 1
    'tom_hi':   50,   # High Tom
    'ride':     51,   # Ride Cymbal 1
}

# ── Fill templates ─────────────────────────────────────────────────────────────
# Added to the last bar of each phrase.
# Format: (beat_offset_within_bar, drum_type, accent)
# These notes are injected AFTER humanization, so their beat values are exact.

_FILL_TEMPLATES: dict[str, list[tuple[float, str, str]]] = {
    'pop': [
        # Classic rock fill: snare triplet into beat 4
        (3.25, 'snare', 'weak'),
        (3.5,  'snare', 'medium'),
        (3.75, 'snare', 'strong'),
    ],
    'hip-hop': [
        # Ghost + accented snare before the downbeat
        (3.5,  'snare', 'ghost'),
        (3.75, 'snare', 'medium'),
    ],
    'jazz': [
        # Sparse: single weak snare on the "and" of 4
        (3.5, 'snare', 'weak'),
    ],
    'lo-fi': [
        # Ultra-sparse: ghost on the last 16th
        (3.75, 'snare', 'ghost'),
    ],
    'edm': [
        # Hihat buildup + snare accent before phrase repeat
        (3.25,  'hihat', 'medium'),
        (3.5,   'hihat', 'strong'),
        (3.625, 'hihat', 'strong'),
        (3.75,  'hihat', 'strong'),
        (3.875, 'snare', 'medium'),
    ],
}

_ACCENT_VEL: dict[str, int] = {
    'strong': 94,
    'medium': 75,
    'weak':   55,
    'ghost':  28,
}

_HAT_VOICES: frozenset[str] = frozenset({'hihat', 'open_hat', 'ride'})


# ── Internal helpers ───────────────────────────────────────────────────────────

def _make_event(ev: RhythmEvent, voice: str) -> dict:
    return {
        'beat':      ev.beat,
        'duration':  ev.duration,
        'velocity':  ev.velocity,
        'drum_type': voice,
        'pitch':     GM_DRUM_MAP.get(voice, GM_DRUM_MAP['snare']),
        'accent':    ev.accent,
    }


def _apply_fill(
    events: list[dict],
    fill_bar: int,
    beats_per_bar: int,
    genre: str,
    rng: random.Random,
) -> list[dict]:
    """
    In the last 1.5 beats of fill_bar, thin out hat/ride hits (50% drop),
    then inject genre-specific fill notes.  Fill note beats are exact (no jitter).
    """
    bar_start = float(fill_bar * beats_per_bar)
    fill_zone = bar_start + beats_per_bar - 1.5   # last 1.5 beats

    result: list[dict] = []
    for ev in events:
        if ev['beat'] >= fill_zone and ev['drum_type'] in _HAT_VOICES:
            if rng.random() < 0.5:
                continue   # drop 50% of hat hits in the fill zone
        result.append(ev)

    fill_template = _FILL_TEMPLATES.get(genre, _FILL_TEMPLATES['pop'])
    for offset, drum_type, accent in fill_template:
        if drum_type in GM_DRUM_MAP:
            result.append({
                'beat':      bar_start + offset,
                'duration':  0.1,
                'velocity':  _ACCENT_VEL[accent],
                'drum_type': drum_type,
                'pitch':     GM_DRUM_MAP[drum_type],
                'accent':    accent,
            })

    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_drums(
    genre: str = 'pop',
    bars: int = 4,
    bpm: int = 120,
    seed: int | None = None,
    variation_bars: int = 4,
) -> dict:
    """
    Generate drum events for a given genre and number of bars.

    Parameters
    ----------
    genre : str
        Genre name.  Aliases ('hiphop', 'lofi', 'electronic', etc.) are resolved
        internally by rhythm.generate_rhythm_pattern().
    bars : int
        Number of bars to generate (>=1).
    bpm : int
        Tempo stored in output for downstream tempo-setting; not used here.
    seed : int | None
        RNG seed for reproducible humanization and fill randomness.
        Each voice gets an independent seed offset so voices vary naturally
        while remaining fully deterministic when a top-level seed is given.
    variation_bars : int
        Apply a drum fill at the last bar of every N-bar phrase.
        0 disables fills entirely.  Fills start when bars >= variation_bars.

    Returns
    -------
    dict
        genre, bpm, bars,
        events: list of { beat, duration, velocity, drum_type, pitch, accent }
        Events are sorted by beat, then drum_type.
    """
    pattern = generate_rhythm_pattern(genre, bars)
    canon   = pattern.genre   # canonical resolved key ('pop', 'hip-hop', ...)

    # Humanise each voice with an offset seed for independent variation
    all_events: list[dict] = []
    for i, (voice, hits) in enumerate(pattern.drum_events.items()):
        voice_seed = (seed + i) if seed is not None else None
        humanized  = apply_humanization(hits, genre=canon, seed=voice_seed)
        for ev in humanized:
            all_events.append(_make_event(ev, voice))

    # Apply fill variations at the end of each N-bar phrase
    if variation_bars > 0:
        fill_bars = [
            (i + 1) * variation_bars - 1
            for i in range(bars // variation_bars)
        ]
        if fill_bars:
            rng = random.Random(seed)
            for fill_bar in fill_bars:
                all_events = _apply_fill(
                    all_events, fill_bar, pattern.beats_per_bar, canon, rng
                )

    all_events.sort(key=lambda e: (e['beat'], e['drum_type']))

    return {
        'genre':  canon,
        'bpm':    bpm,
        'bars':   bars,
        'events': all_events,
    }
