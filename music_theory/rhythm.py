"""
music_theory/rhythm.py
Timing, groove, and rhythmic structure for music generation.

No MIDI writing, no audio processing — pure timing and pattern logic.
All beat positions are floats (quarter notes), compatible with MidiBuilder.add_note().

Public API
──────────
Constants
  PPQ              int              480 — must match midi/builder.MidiBuilder.PPQ
  TICKS            dict[int, int]   subdivision → tick count at PPQ=480
  BEAT_VALUE       dict[int, float] subdivision → beat count (e.g. 8 → 0.5)

Data types
  RhythmEvent      dataclass        one rhythmic placement (beat, duration, velocity, accent)
  RhythmPattern    dataclass        full N-bar pattern: melody_events + drum_events
  HumanizeSettings dataclass        timing_jitter, velocity_variance, optional seed

Utility functions
  beats_to_ticks(beats, ppq)            → int
  ticks_to_beats(ticks, ppq)            → float
  bars_to_ticks(bars, bpb, ppq)         → int
  quantize_to_grid(ticks, grid_size)    → int
  get_beat_positions(bars, subdiv, ts)  → list[float]

Pattern functions
  generate_rhythm_pattern(genre, bars)             → RhythmPattern
  apply_humanization(events, settings, genre, seed)→ list[RhythmEvent]
  get_humanize_settings(genre)                     → HumanizeSettings

Supported genres: pop · hip-hop · jazz · lo-fi · edm
Common aliases:   hiphop, lofi, electronic, dance, rock, blues, ambient, …

How downstream writers consume this module
──────────────────────────────────────────
melody_writer:
  pattern = generate_rhythm_pattern(genre, bars)
  events  = apply_humanization(pattern.melody_events, genre=genre, seed=42)
  # events[i].beat      → start_beat for MidiBuilder.add_note()
  # events[i].duration  → duration_beats  (writer may shorten for articulation)
  # events[i].velocity  → velocity
  # writer maps events to scale pitches; accent drives pitch choice (strong → chord tones)

drum_writer:
  pattern = generate_rhythm_pattern(genre, bars)
  for voice, hits in pattern.drum_events.items():
      hits = apply_humanization(hits, genre=genre, seed=42)
      gm_note = GM_DRUM_MAP[voice]   # e.g. kick=36, snare=38, hihat=42
      for ev in hits:
          builder.add_note(drum_track, 9, gm_note, ev.beat, ev.duration, ev.velocity)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# ── Constants ──────────────────────────────────────────────────────────────────

PPQ: int = 480  # ticks per quarter note — must match midi/builder.MidiBuilder.PPQ

# Subdivision sizes in ticks
TICKS: dict[int, int] = {
    1:  PPQ * 4,    # whole note    1920
    2:  PPQ * 2,    # half note      960
    4:  PPQ,        # quarter note   480
    8:  PPQ // 2,   # eighth note    240
    16: PPQ // 4,   # sixteenth      120
    32: PPQ // 8,   # 32nd note       60
    64: PPQ // 16,  # 64th note       30
}

# Subdivision sizes in beats (quarter notes)
BEAT_VALUE: dict[int, float] = {n: t / PPQ for n, t in TICKS.items()}

# Accent → base MIDI velocity (midpoint of each range; humanization adds variance)
_ACCENT_BASE: dict[str, int] = {
    'strong': 94,   # range 88-100: downbeats, primary hits
    'medium': 75,   # range 68-82:  regular notes, upbeats
    'weak':   55,   # range 48-62:  passing notes, offbeats
    'ghost':  28,   # range 20-36:  ghost notes, felt more than heard
}

# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class RhythmEvent:
    """One rhythmic placement in a pattern."""
    beat:     float  # position in beats from pattern start (0-indexed)
    duration: float  # note duration in beats
    velocity: int    # MIDI velocity 1-127
    accent:   str    # 'strong' | 'medium' | 'weak' | 'ghost'


@dataclass
class RhythmPattern:
    """
    Multi-bar rhythm plan consumed by melody_writer and drum_writer.
    Both event lists have beat positions expanded across all bars and
    swing already applied. Call apply_humanization() before MIDI writing.
    """
    genre:         str
    groove:        str                           # 'straight' | 'swing'
    swing_amount:  float                         # 0.5 = none, 0.667 = full triplet
    bars:          int
    beats_per_bar: int                           # 4 for 4/4
    melody_events: list[RhythmEvent]             # timing slots for melody pitches
    drum_events:   dict[str, list[RhythmEvent]]  # voice → hit events


@dataclass
class HumanizeSettings:
    """Controls the amount of human-feel randomness added to rhythm events."""
    timing_jitter:     float       # max ± beat offset (0.02 ≈ 10 ms at 120 BPM)
    velocity_variance: int         # max ± velocity shift
    seed: int | None = None        # set for deterministic / reproducible output


# ── Genre profiles ─────────────────────────────────────────────────────────────

_GENRE_GROOVE: dict[str, str] = {
    'pop':     'straight',
    'hip-hop': 'swing',
    'jazz':    'swing',
    'lo-fi':   'swing',
    'edm':     'straight',
}

# Position of the "and" (upbeat 8th) within each beat pair
#   0.5   = straight (50 / 50)
#   0.583 = light shuffle (~7 : 5)
#   0.667 = full triplet swing (~2 : 1)
_GENRE_SWING: dict[str, float] = {
    'pop':     0.5,
    'hip-hop': 0.583,
    'jazz':    0.667,
    'lo-fi':   0.583,
    'edm':     0.5,
}

_HUMANIZE_DEFAULTS: dict[str, HumanizeSettings] = {
    'pop':     HumanizeSettings(timing_jitter=0.010, velocity_variance=5),
    'hip-hop': HumanizeSettings(timing_jitter=0.020, velocity_variance=10),
    'jazz':    HumanizeSettings(timing_jitter=0.025, velocity_variance=12),
    'lo-fi':   HumanizeSettings(timing_jitter=0.040, velocity_variance=15),
    'edm':     HumanizeSettings(timing_jitter=0.005, velocity_variance=3),
}

# Maps common user-facing names to the 5 supported template keys
_GENRE_ALIASES: dict[str, str] = {
    'hiphop':     'hip-hop',
    'hip_hop':    'hip-hop',
    'lofi':       'lo-fi',
    'lo_fi':      'lo-fi',
    'electronic': 'edm',
    'dance':      'edm',
    'techno':     'edm',
    'house':      'edm',
    'rock':       'pop',
    'classical':  'pop',
    'blues':      'jazz',
    'bossa nova': 'jazz',
    'bossanova':  'jazz',
    'ambient':    'lo-fi',
    'r&b':        'hip-hop',
    'rnb':        'hip-hop',
}

# ── Per-bar pattern templates ──────────────────────────────────────────────────
# Format: (beat_position_within_bar, duration_in_beats, accent)
# Beat positions are in straight time; swing is applied at generation time.
# Drum durations are short (0.1) — only onset matters for GM percussion.
# Melody durations are suggestions; melody_writer may adjust for articulation.

_MELODY_TEMPLATES: dict[str, list[tuple[float, float, str]]] = {
    'pop': [
        # 8th-note grid; downbeats accented
        (0.0, 0.45, 'strong'), (0.5, 0.45, 'weak'),
        (1.0, 0.45, 'medium'), (1.5, 0.45, 'weak'),
        (2.0, 0.45, 'strong'), (2.5, 0.45, 'weak'),
        (3.0, 0.45, 'medium'), (3.5, 0.45, 'weak'),
    ],
    'hip-hop': [
        # Syncopated 16th-note pockets; upbeats anticipate the next beat
        (0.0,  0.45, 'strong'),
        (0.75, 0.25, 'weak'),
        (1.0,  0.45, 'medium'),
        (1.75, 0.25, 'ghost'),
        (2.0,  0.45, 'strong'),
        (2.5,  0.25, 'weak'),
        (3.0,  0.70, 'medium'),
    ],
    'jazz': [
        # Swung 8th notes; upbeats land at 0.667 beat after swing transform
        (0.0, 0.45, 'medium'), (0.5, 0.45, 'weak'),
        (1.0, 0.45, 'strong'), (1.5, 0.45, 'weak'),
        (2.0, 0.45, 'medium'), (2.5, 0.45, 'weak'),
        (3.0, 0.45, 'strong'), (3.5, 0.45, 'weak'),
    ],
    'lo-fi': [
        # Sparse, laid-back; long notes with ghost-note accents
        (0.0, 0.9,  'medium'),
        (1.0, 0.45, 'weak'),
        (2.0, 0.9,  'medium'),
        (3.0, 0.45, 'weak'),
        (3.5, 0.45, 'ghost'),
    ],
    'edm': [
        # 16th-note arpeggiation; every bar downbeat is strong
        (0.0,  0.22, 'strong'), (0.25, 0.22, 'medium'),
        (0.5,  0.22, 'medium'), (0.75, 0.22, 'weak'),
        (1.0,  0.22, 'strong'), (1.25, 0.22, 'medium'),
        (1.5,  0.22, 'medium'), (1.75, 0.22, 'weak'),
        (2.0,  0.22, 'strong'), (2.25, 0.22, 'medium'),
        (2.5,  0.22, 'medium'), (2.75, 0.22, 'weak'),
        (3.0,  0.22, 'strong'), (3.25, 0.22, 'medium'),
        (3.5,  0.22, 'medium'), (3.75, 0.22, 'weak'),
    ],
}

_DRUM_TEMPLATES: dict[str, dict[str, list[tuple[float, float, str]]]] = {
    'pop': {
        # Classic 8th-hat rock/pop beat
        'kick':  [(0.0, 0.1, 'strong'), (2.0, 0.1, 'strong')],
        'snare': [(1.0, 0.1, 'strong'), (3.0, 0.1, 'strong')],
        'hihat': [
            (0.0, 0.1, 'medium'), (0.5, 0.1, 'medium'),
            (1.0, 0.1, 'medium'), (1.5, 0.1, 'medium'),
            (2.0, 0.1, 'medium'), (2.5, 0.1, 'medium'),
            (3.0, 0.1, 'medium'), (3.5, 0.1, 'medium'),
        ],
    },
    'hip-hop': {
        # Boom-bap: syncopated kick, ghost-note snare
        'kick': [
            (0.0,  0.1, 'strong'),
            (0.75, 0.1, 'medium'),
            (2.5,  0.1, 'strong'),
        ],
        'snare': [
            (1.0,  0.1, 'strong'),
            (3.0,  0.1, 'strong'),
            (0.5,  0.1, 'ghost'),   # ghost on the "e" of beat 1
            (1.75, 0.1, 'ghost'),   # ghost on the "a" of beat 2
            (2.75, 0.1, 'ghost'),   # ghost on the "a" of beat 3
        ],
        'hihat': [
            (0.0, 0.1, 'medium'), (0.5, 0.1, 'medium'),
            (1.0, 0.1, 'medium'), (1.5, 0.1, 'medium'),
            (2.0, 0.1, 'medium'), (2.5, 0.1, 'medium'),
            (3.0, 0.1, 'medium'), (3.5, 0.1, 'medium'),
        ],
    },
    'jazz': {
        # Ride-based jazz comp: swung 8ths on ride, foot hihat on 2 & 4
        'ride': [
            (0.0, 0.1, 'medium'), (0.5, 0.1, 'weak'),
            (1.0, 0.1, 'strong'), (1.5, 0.1, 'weak'),
            (2.0, 0.1, 'medium'), (2.5, 0.1, 'weak'),
            (3.0, 0.1, 'strong'), (3.5, 0.1, 'weak'),
        ],
        'hihat': [(1.0, 0.1, 'weak'), (3.0, 0.1, 'weak')],   # foot hihat on 2 & 4
        'kick':  [(0.0, 0.1, 'weak')],                         # feathered kick on 1
        'snare': [(1.0, 0.1, 'medium'), (3.0, 0.1, 'medium')],
    },
    'lo-fi': {
        # Loose hip-hop variant; sparse kicks, ghost hats
        'kick':  [(0.0, 0.1, 'medium'), (2.25, 0.1, 'weak')],
        'snare': [(1.0, 0.1, 'medium'), (3.0,  0.1, 'weak')],
        'hihat': [
            (0.0, 0.1, 'weak'),  (0.5, 0.1, 'ghost'),
            (1.0, 0.1, 'weak'),  (1.5, 0.1, 'ghost'),
            (2.0, 0.1, 'weak'),  (2.5, 0.1, 'ghost'),
            (3.0, 0.1, 'weak'),  (3.5, 0.1, 'ghost'),
        ],
    },
    'edm': {
        # 4-on-the-floor with 16th hihat grid and off-beat open hat
        'kick': [
            (0.0, 0.1, 'strong'), (1.0, 0.1, 'strong'),
            (2.0, 0.1, 'strong'), (3.0, 0.1, 'strong'),
        ],
        'snare': [(1.0, 0.1, 'strong'), (3.0, 0.1, 'strong')],
        'hihat': [
            (0.0,  0.1, 'medium'), (0.25, 0.1, 'medium'),
            (0.5,  0.1, 'medium'), (0.75, 0.1, 'medium'),
            (1.0,  0.1, 'medium'), (1.25, 0.1, 'medium'),
            (1.5,  0.1, 'medium'), (1.75, 0.1, 'medium'),
            (2.0,  0.1, 'medium'), (2.25, 0.1, 'medium'),
            (2.5,  0.1, 'medium'), (2.75, 0.1, 'medium'),
            (3.0,  0.1, 'medium'), (3.25, 0.1, 'medium'),
            (3.5,  0.1, 'medium'), (3.75, 0.1, 'medium'),
        ],
        'open_hat': [
            (0.5, 0.1, 'medium'), (1.5, 0.1, 'medium'),
            (2.5, 0.1, 'medium'), (3.5, 0.1, 'medium'),
        ],
    },
}

# ── Internal helpers ───────────────────────────────────────────────────────────

def _resolve_genre(genre: str) -> str:
    """Map alias or unrecognised genre to one of the 5 template keys."""
    key = genre.strip().lower()
    key = _GENRE_ALIASES.get(key, key)
    return key if key in _DRUM_TEMPLATES else 'pop'


def _accent_to_velocity(accent: str) -> int:
    return _ACCENT_BASE.get(accent, 75)


def _swing_beat(beat: float, swing_amount: float) -> float:
    """
    Remap a beat position with 8th-note swing.

    Within each integer beat boundary [N, N+1):
      [N, N+0.5)   → [N, N+swing_amount)    first 8th — stretched
      [N+0.5, N+1) → [N+swing_amount, N+1)  second 8th — compressed

    Downbeats (integer positions) are never moved.
    swing_amount=0.5  → identity (no swing).
    swing_amount=0.667→ full triplet swing.

    Also handles 16th-note positions via linear interpolation within each 8th.
    """
    if swing_amount == 0.5:
        return beat
    whole = math.floor(beat)
    frac  = beat - whole
    if frac < 0.5:
        new_frac = frac * (swing_amount / 0.5)
    else:
        new_frac = swing_amount + (frac - 0.5) * ((1.0 - swing_amount) / 0.5)
    return round(whole + new_frac, 10)


def _expand_template(
    template: list[tuple[float, float, str]],
    bars: int,
    beats_per_bar: int,
    swing_amount: float,
) -> list[RhythmEvent]:
    """
    Repeat a one-bar (beat, duration, accent) template for N bars.
    Applies swing to beat positions, then returns events sorted by beat.
    """
    events: list[RhythmEvent] = []
    for bar in range(bars):
        offset = float(bar * beats_per_bar)
        for beat_in_bar, duration, accent in template:
            swung = _swing_beat(beat_in_bar, swing_amount)
            events.append(RhythmEvent(
                beat     = round(offset + swung, 6),
                duration = duration,
                velocity = _accent_to_velocity(accent),
                accent   = accent,
            ))
    events.sort(key=lambda e: e.beat)
    return events


# ── Public API ─────────────────────────────────────────────────────────────────

def beats_to_ticks(beats: float, ppq: int = PPQ) -> int:
    """Convert a beat count to MIDI ticks.  1 beat = ppq ticks."""
    return round(beats * ppq)


def ticks_to_beats(ticks: int, ppq: int = PPQ) -> float:
    """Convert MIDI ticks to beats."""
    return ticks / ppq


def bars_to_ticks(bars: int, beats_per_bar: int = 4, ppq: int = PPQ) -> int:
    """Convert a bar count to MIDI ticks (default 4/4, PPQ=480)."""
    return bars * beats_per_bar * ppq


def quantize_to_grid(ticks: int, grid_size: int) -> int:
    """
    Snap a tick value to the nearest grid boundary.

      quantize_to_grid(241, 120)  →  240   (nearest 1/16 at PPQ=480)
      quantize_to_grid(130, 240)  →  240   (nearest 1/8)
      quantize_to_grid(61,  120)  →   60   (rounds to nearest)
    """
    if grid_size <= 0:
        raise ValueError(f"grid_size must be > 0, got {grid_size}.")
    return round(ticks / grid_size) * grid_size


def get_beat_positions(
    bars: int,
    subdivision: int = 8,
    time_sig: tuple[int, int] = (4, 4),
) -> list[float]:
    """
    Return every grid position in beats for a subdivision across N bars.

    subdivision is the note value denominator (4=quarter, 8=eighth, 16=16th …).
    In 4/4 time the step size = 4 / subdivision beats.

      get_beat_positions(1, 8)  → [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
      get_beat_positions(1, 4)  → [0.0, 1.0, 2.0, 3.0]
      get_beat_positions(2, 16) → 32 positions: 0.0, 0.25, 0.5 … 7.75
    """
    if subdivision not in TICKS:
        raise ValueError(
            f"subdivision must be one of {sorted(TICKS.keys())}, got {subdivision}."
        )
    beats_per_bar = time_sig[0] * (4.0 / time_sig[1])
    step          = 4.0 / subdivision
    total         = int(round(bars * beats_per_bar / step))
    return [round(i * step, 10) for i in range(total)]


def get_humanize_settings(genre: str) -> HumanizeSettings:
    """Return default humanization settings for the given genre."""
    return _HUMANIZE_DEFAULTS[_resolve_genre(genre)]


def apply_humanization(
    events: list[RhythmEvent],
    settings: HumanizeSettings | None = None,
    genre: str = 'pop',
    seed: int | None = None,
) -> list[RhythmEvent]:
    """
    Add random timing jitter and velocity variance to a list of RhythmEvent.
    Returns a new list — the input is not mutated.

    Timing  : beat ± timing_jitter  (clamped to ≥ 0)
    Velocity: velocity ± velocity_variance  (clamped to 1-127)

    Determinism: set seed here or via HumanizeSettings.seed.
    HumanizeSettings.seed takes precedence when both are provided.

    Example:
        raw    = generate_rhythm_pattern('jazz', bars=4).melody_events
        cooked = apply_humanization(raw, genre='jazz', seed=42)
    """
    if settings is None:
        settings = get_humanize_settings(genre)

    effective_seed = settings.seed if settings.seed is not None else seed
    rng = random.Random(effective_seed)

    result: list[RhythmEvent] = []
    for ev in events:
        jitter    = rng.uniform(-settings.timing_jitter, settings.timing_jitter)
        vel_delta = rng.randint(-settings.velocity_variance, settings.velocity_variance)
        result.append(RhythmEvent(
            beat     = round(max(0.0, ev.beat + jitter), 6),
            duration = ev.duration,
            velocity = max(1, min(127, ev.velocity + vel_delta)),
            accent   = ev.accent,
        ))
    return result


def generate_rhythm_pattern(genre: str, bars: int = 1) -> RhythmPattern:
    """
    Build a RhythmPattern for N bars of the given genre.

    Swing is applied to beat positions at generation time.
    Call apply_humanization() on the returned event lists before MIDI writing.

    melody_events   — beat slots for melody_writer to fill with pitches
    drum_events     — per-voice hit timings for drum_writer

    Supported genre keys: 'pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'
    Aliases also accepted; unknown genres fall back to 'pop'.

    Example:
        pat   = generate_rhythm_pattern('jazz', bars=4)
        mel   = apply_humanization(pat.melody_events, genre='jazz', seed=42)
        drums = {v: apply_humanization(h, genre='jazz', seed=42)
                 for v, h in pat.drum_events.items()}
    """
    if bars < 1:
        raise ValueError(f"bars must be >= 1, got {bars}.")

    canon         = _resolve_genre(genre)
    beats_per_bar = 4

    melody_events = _expand_template(
        _MELODY_TEMPLATES[canon], bars, beats_per_bar, _GENRE_SWING[canon]
    )
    drum_events = {
        voice: _expand_template(hits, bars, beats_per_bar, _GENRE_SWING[canon])
        for voice, hits in _DRUM_TEMPLATES[canon].items()
    }

    return RhythmPattern(
        genre         = canon,
        groove        = _GENRE_GROOVE[canon],
        swing_amount  = _GENRE_SWING[canon],
        bars          = bars,
        beats_per_bar = beats_per_bar,
        melody_events = melody_events,
        drum_events   = drum_events,
    )
