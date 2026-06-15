"""
backend/services/melody_service.py
Generates a diatonic melody over an existing chord progression.

Pitch selection is fully deterministic (no random note choices):
  · Strong beats  → nearest chord tone via voice leading
  · Medium beats  → chord tone or close diatonic neighbour
  · Weak beats    → diatonic step (passing/approach note)
  · Ghost beats   → diatonic step (same logic; very rarely played)

Optional seeded RNG controls only rest decisions (density parameter).
Swing and humanization are delegated entirely to music_theory/rhythm.

Public API
──────────
  generate_melody(chord_data, octave, density, seed) → dict

Input
  chord_data   : output of chord_service.generate_chord_progression()

Output
  {
    key, mode, scale, genre, bpm, bars, octave,
    notes: [
      { beat, duration, pitch, pitch_name, velocity, accent }
      …
    ]
  }

Integration with midi/melody_writer.py
───────────────────────────────────────
  melody_writer receives the 'notes' list from this service.
  For each note it calls:

    builder.add_note(
        track    = melody_track_idx,
        channel  = 0,
        pitch    = note['pitch'],
        start_beat = note['beat'],
        duration_beats = note['duration'],
        velocity = note['velocity'],
    )

  The writer does not need to know about chord theory or rhythm patterns;
  this service has already resolved every pitch and timing value.
"""

from __future__ import annotations

import random

from music_theory.scales import get_scale_notes, notes_in_octave, get_note_name
from music_theory.rhythm import generate_rhythm_pattern, apply_humanization

# ── Rest probability per accent (before density scaling) ──────────────────────
# strong is hardcoded to always play; others are scaled by density.
_BASE_PLAY_PROB: dict[str, float] = {
    'strong': 1.00,
    'medium': 0.90,
    'weak':   0.60,
    'ghost':  0.15,
}

# ── Internal helpers ───────────────────────────────────────────────────────────

def _active_chord(beat: float, chords: list[dict]) -> dict:
    """Return the chord whose beat_start is the last one ≤ beat."""
    active = chords[0]
    for chord in chords:
        if chord['beat_start'] <= beat:
            active = chord
    return active


def _chord_tones(chord: dict, scale_pool: list[int]) -> list[int]:
    """
    Return notes from scale_pool whose pitch class matches any note in chord['notes'].

    Works correctly with all voicing types (close, open, drop2) because it
    looks at pitch classes, not specific MIDI notes.
    """
    pcs = {n % 12 for n in chord['notes']}
    return [n for n in scale_pool if n % 12 in pcs]


def _nearest(candidates: list[int], pivot: int, bias_dir: int = 0) -> int:
    """
    Pick the candidate closest to pivot.

    bias_dir (+1 or -1): tiny bonus for notes in the preferred direction
    so voice leading produces slight melodic motion rather than repetition.
    A zero or same-pitch candidate gets a small penalty to encourage movement.
    """
    def score(c: int) -> float:
        dist = float(abs(c - pivot))
        if dist == 0:
            # Penalty beats any directionally-biased note within a 3rd (dist - 0.4 = 1.6 max),
            # but still loses to a plain step when there is no directional preference.
            return 1.8
        bonus = 0.4 if (c - pivot) * bias_dir > 0 else 0.0
        return dist - bonus
    return min(candidates, key=score)


def _step_toward(scale_pool: list[int], current: int, direction: int) -> int:
    """
    Return the next diatonic note one step in direction from current.
    At the register boundary, stays on the last available note.
    """
    if direction > 0:
        above = [n for n in scale_pool if n > current]
        return above[0] if above else scale_pool[-1]
    else:
        below = [n for n in scale_pool if n < current]
        return below[-1] if below else scale_pool[0]


def _pick_pitch(
    accent: str,
    chord_tones: list[int],
    scale_pool: list[int],
    prev: int,
    bias_dir: int,
) -> int:
    """
    Select a melody pitch using voice-leading rules.

    strong / medium → chord tone (harmonically anchored)
    weak   / ghost  → diatonic step (passing/approach motion)
    """
    if not chord_tones:
        chord_tones = scale_pool      # safe fallback; should not happen in practice

    if accent in ('strong', 'medium'):
        candidates = list(chord_tones)
        if accent == 'medium':
            # Also allow nearby scale neighbours (up to a 4th away)
            candidates += [n for n in scale_pool if abs(n - prev) <= 5]
        return _nearest(sorted(set(candidates)), prev, bias_dir=bias_dir)

    # weak / ghost: stepwise passing motion
    return _step_toward(scale_pool, prev, bias_dir)


def _update_contour(
    prev: int,
    new_pitch: int,
    direction: int,
    steps: int,
    max_steps: int = 4,
) -> tuple[int, int]:
    """
    Update melodic contour state after placing a note.
    Flips direction automatically after max_steps consecutive same-direction steps.

    Returns (new_direction, new_step_count).
    """
    if new_pitch > prev:
        direction, steps = (direction, steps + 1) if direction > 0 else (1, 1)
    elif new_pitch < prev:
        direction, steps = (direction, steps + 1) if direction < 0 else (-1, 1)
    # same pitch: no change

    if steps >= max_steps:
        direction = -direction
        steps = 0

    return direction, steps


def _should_play(accent: str, density: float, rng: random.Random) -> bool:
    """Decide whether a rhythm slot produces a note or a rest."""
    if accent == 'strong':
        return True
    return rng.random() < _BASE_PLAY_PROB.get(accent, 0.5) * density


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_melody(
    chord_data: dict,
    octave: int = 5,
    density: float = 0.75,
    seed: int | None = None,
) -> dict:
    """
    Generate a diatonic melody over a chord progression.

    Parameters
    ----------
    chord_data : dict
        Output from chord_service.generate_chord_progression().
        Provides key, mode, scale, genre, bpm, bars, chords, chord_scale.
    octave : int
        Melody register centre. Melody spans [C(octave-1), C(octave+1)].
        Default 5 → roughly C4–C6 (comfortable singing/lead range).
    density : float
        Fraction of rhythm slots that become notes (0.0–1.0).
        Strong beats always play regardless of density.
        0.75 = moderate phrasing with natural rests.
    seed : int | None
        Seed for the RNG that controls rest decisions.
        Pitch selection is always deterministic (no seed effect on pitches).

    Returns
    -------
    dict
        key, mode, scale, genre, bpm, bars, octave,
        notes: list of { beat, duration, pitch, pitch_name, velocity, accent }
    """
    key         = chord_data['key']
    chord_scale = chord_data['chord_scale']   # always heptatonic (chord_service guarantee)
    genre       = chord_data['genre']
    chords      = chord_data['chords']
    bars        = chord_data['bars']

    # ── Melody register ──────────────────────────────────────────────────────
    # Span two octaves centred on the target, clamped to a safe MIDI range.
    # C at octave n has MIDI number (n+1)*12, so:
    #   melody_low  = (octave-1+1)*12 = octave*12       → C(octave-1)
    #   melody_high = (octave+1+1)*12 = (octave+2)*12   → C(octave+1)
    melody_low  = max(48, octave * 12)           # never below C3
    melody_high = min(96, (octave + 2) * 12)     # never above C7

    scale_pool = [
        n for n in get_scale_notes(
            key, chord_scale,
            octave_min=max(2, octave - 1),
            octave_max=min(7, octave + 1),
        )
        if melody_low <= n <= melody_high
    ]

    if not scale_pool:
        raise ValueError(
            f"No scale notes in melody register "
            f"key={key!r} scale={chord_scale!r} octave={octave}."
        )

    # ── Initial pitch: tonic at target octave ────────────────────────────────
    root_at_octave = notes_in_octave(key, chord_scale, octave)
    if root_at_octave and melody_low <= root_at_octave[0] <= melody_high:
        prev_pitch = root_at_octave[0]
    else:
        centre     = (melody_low + melody_high) // 2
        prev_pitch = min(scale_pool, key=lambda n: abs(n - centre))

    # ── Rhythm timing from rhythm module ─────────────────────────────────────
    pattern = generate_rhythm_pattern(genre, bars)
    events  = apply_humanization(pattern.melody_events, genre=genre, seed=seed)

    # ── Contour state ────────────────────────────────────────────────────────
    contour_dir  = 1   # start ascending
    steps_in_dir = 0

    rng = random.Random(seed)
    notes: list[dict] = []

    for ev in events:
        if not _should_play(ev.accent, density, rng):
            continue

        active      = _active_chord(ev.beat, chords)
        chord_tones = _chord_tones(active, scale_pool)

        # Effective direction: flip after too many consecutive steps,
        # or when approaching a register boundary.
        eff_dir = contour_dir
        if steps_in_dir >= 4:
            eff_dir = -contour_dir
        if prev_pitch <= melody_low + 2 and eff_dir < 0:
            eff_dir = 1
        if prev_pitch >= melody_high - 2 and eff_dir > 0:
            eff_dir = -1

        pitch = _pick_pitch(ev.accent, chord_tones, scale_pool, prev_pitch, eff_dir)
        pitch = max(melody_low, min(melody_high, pitch))   # hard clamp

        contour_dir, steps_in_dir = _update_contour(
            prev_pitch, pitch, contour_dir, steps_in_dir
        )
        prev_pitch = pitch

        notes.append({
            'beat':       ev.beat,
            'duration':   ev.duration,
            'pitch':      pitch,
            'pitch_name': get_note_name(pitch),
            'velocity':   ev.velocity,
            'accent':     ev.accent,
        })

    return {
        'key':    key,
        'mode':   chord_data['mode'],
        'scale':  chord_data['scale'],
        'genre':  genre,
        'bpm':    chord_data['bpm'],
        'bars':   bars,
        'octave': octave,
        'notes':  notes,
    }
