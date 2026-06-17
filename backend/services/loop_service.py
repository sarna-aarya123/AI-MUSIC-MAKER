"""
loop_service.py — Loop-Based Underground Beat Identity Engine
Generates motif + bass + texture stack for continuous looping playback.
No chord progressions, no structured song form.
"""
import random

# ── Genre parameter tables ────────────────────────────────────────────────────

GENRE_PARAMS = {
    'rage': {
        'bpm_range':      (150, 170),
        'scale':          [0, 1, 3, 5, 7, 8, 10],  # phrygian — aggressive
        'motif_n':        (2, 5),
        'loop_bars':      (1, 2),
        'texture_count':  (3, 5),
        'osc_types':      ['sawtooth', 'square', 'sawtooth'],
        'filter_range':   (400, 2200),
        'reverb_range':   (0.15, 0.40),
        'bass_intervals': [0, 3, 7],
        'portamento':     0.01,
    },
    'pluggnb': {
        'bpm_range':      (75, 92),
        'scale':          [0, 3, 5, 7, 10],         # minor pentatonic — melodic
        'motif_n':        (4, 7),
        'loop_bars':      (2, 4),
        'texture_count':  (2, 4),
        'osc_types':      ['sine', 'triangle'],
        'filter_range':   (120, 550),
        'reverb_range':   (0.55, 0.88),
        'bass_intervals': [0, 5, 7],
        'portamento':     0.08,
    },
    'dark_trap': {
        'bpm_range':      (130, 148),
        'scale':          [0, 2, 3, 5, 7, 8, 10],  # natural minor
        'motif_n':        (2, 5),
        'loop_bars':      (2, 4),
        'texture_count':  (2, 4),
        'osc_types':      ['sawtooth', 'triangle'],
        'filter_range':   (120, 500),
        'reverb_range':   (0.40, 0.70),
        'bass_intervals': [0, 3, 7],
        'portamento':     0.02,
    },
    'cloud': {
        'bpm_range':      (128, 144),
        'scale':          [0, 3, 5, 7, 10],         # minor pentatonic — floaty
        'motif_n':        (3, 6),
        'loop_bars':      (2, 4),
        'texture_count':  (3, 5),
        'osc_types':      ['sine', 'triangle'],
        'filter_range':   (500, 1800),
        'reverb_range':   (0.65, 0.92),
        'bass_intervals': [0, 5, 7],
        'portamento':     0.12,
    },
}

NOTE_MAP = {
    'C': 60, 'C#': 61, 'Db': 61, 'D': 62, 'D#': 63, 'Eb': 63,
    'E': 64, 'F': 65, 'F#': 66, 'Gb': 66, 'G': 67, 'G#': 68,
    'Ab': 68, 'A': 69, 'A#': 70, 'Bb': 70, 'B': 71,
}


# ── Public API ────────────────────────────────────────────────────────────────

def generate_loop(genre='rage', root='A', bpm=None, bars=4, seed=None):
    """
    Generate a complete loop identity: motif + bass + texture stack.

    Returns dict ready for JSON serialisation.
    """
    rng    = random.Random(seed)
    params = GENRE_PARAMS.get(genre, GENRE_PARAMS['rage'])

    tonal_center = NOTE_MAP.get(root, 69)

    # BPM
    if bpm is None:
        bpm = rng.randint(*params['bpm_range'])
    bpm = max(60, min(220, int(bpm)))

    # Loop length in beats (always a multiple of 4)
    loop_bars   = rng.randint(*params['loop_bars'])
    loop_bars   = min(loop_bars, max(1, bars))
    loop_length = loop_bars * 4

    motif    = _gen_motif(rng, params, tonal_center, loop_length)
    bass     = _gen_bass(rng, params, tonal_center, loop_length)
    textures = _gen_textures(rng, params, tonal_center)

    return {
        'motif':          motif,
        'bass':           bass,
        'textures':       textures,
        'bpm':            bpm,
        'loop_length':    loop_length,
        'tonal_center':   tonal_center,
        'root':           root,
        'genre':          genre,
        'variation_seed': rng.randint(0, 99999),
        'portamento':     params['portamento'],
    }


# ── Motif generation (rhythm-first) ──────────────────────────────────────────

def _gen_motif(rng, params, tonal_center, loop_length):
    scale  = params['scale']
    n      = rng.randint(*params['motif_n'])

    # Build pitch pool: 2 octaves centred just below tonal_center
    pitches = sorted({
        tonal_center + s + oct_shift
        for oct_shift in (-12, 0, 12)
        for s in scale
        if 42 <= tonal_center + s + oct_shift <= 84
    })
    if not pitches:
        pitches = [tonal_center]

    # Syncopated beat grid (16th-note resolution)
    grid = [round(i * 0.25, 3) for i in range(int(loop_length / 0.25))]
    beats = _pick_syncopated_beats(rng, grid, n)
    beats.sort()

    notes = []
    pitch_idx = len(pitches) // 2

    for i, beat in enumerate(beats):
        # Small-interval pitch motion (underground style)
        step = rng.choices(
            [-3, -2, -1, 0, 1, 2, 3],
            weights=[1, 2, 4, 3, 4, 2, 1],
        )[0]
        pitch_idx = max(0, min(len(pitches) - 1, pitch_idx + step))
        pitch     = pitches[pitch_idx]

        gap      = (beats[i + 1] - beat) if i + 1 < len(beats) else (loop_length - beat)
        duration = round(min(max(0.125, gap * 0.80), 1.5), 3)
        velocity = rng.randint(68, 108)

        notes.append({
            'phase_start':    round(beat / loop_length, 6),
            'phase_duration': round(duration / loop_length, 6),
            'pitch':          pitch,
            'velocity':       velocity,
        })

    return notes


def _pick_syncopated_beats(rng, grid, n):
    """
    Weighted random selection biased toward offbeats / 16th-note positions.
    """
    def weight(slot):
        pos = slot % 4
        if   pos == 0:                       return 1.2   # downbeat — least syncopated
        elif abs(pos - round(pos)) < 0.01:   return 2.0   # quarter beat
        elif abs(pos * 2 - round(pos * 2)) < 0.01: return 3.0  # eighth
        else:                                return 4.5   # 16th (most syncopated)

    pool     = [(s, weight(s)) for s in grid]
    chosen   = []

    for _ in range(min(n, len(pool))):
        if not pool:
            break
        total = sum(w for _, w in pool)
        r     = rng.random() * total
        cum   = 0.0
        for j, (slot, w) in enumerate(pool):
            cum += w
            if r <= cum:
                chosen.append(slot)
                # Remove slot and neighbours within 0.25 beats (avoid cluster)
                pool = [(s, ww) for s, ww in pool if abs(s - slot) >= 0.25]
                break

    return chosen


# ── Bass generation ───────────────────────────────────────────────────────────

def _gen_bass(rng, params, tonal_center, loop_length):
    root = tonal_center - 24    # two octaves down
    while root < 28:
        root += 12

    intervals = params['bass_intervals']

    if rng.random() < 0.45:
        # Static drone
        return [{
            'phase_start':    0.0,
            'phase_duration': 1.0,
            'pitch':          root,
            'velocity':       95,
        }]

    # Two-note pattern
    half      = loop_length / 2
    note2     = root + rng.choice(intervals[1:])
    dur_phase = round(half * 0.92 / loop_length, 6)   # 0.5 * 0.92 = 0.46
    return [
        {'phase_start': 0.0, 'phase_duration': dur_phase, 'pitch': root,  'velocity': 95},
        {'phase_start': 0.5, 'phase_duration': dur_phase, 'pitch': note2, 'velocity': 85},
    ]


# ── Texture stack generation ──────────────────────────────────────────────────

def _gen_textures(rng, params, tonal_center):
    n          = rng.randint(*params['texture_count'])
    osc_types  = params['osc_types']
    f_lo, f_hi = params['filter_range']
    r_lo, r_hi = params['reverb_range']

    # Pitch stack: root, minor 3rd, perfect 4th, perfect 5th, minor 7th
    stack_intervals = [0, 3, 5, 7, 10, -12, 12]

    # Spread pans
    pans = [-0.65, -0.30, 0.0, 0.30, 0.65]
    rng.shuffle(pans)

    textures = []
    for i in range(n):
        pitch = max(24, min(60, tonal_center + stack_intervals[i % len(stack_intervals)]))
        textures.append({
            'osc_type':    rng.choice(osc_types),
            'detune':      round(rng.uniform(-18, 18), 1),
            'filter_freq': round(rng.uniform(f_lo, f_hi), 1),
            'filter_q':    round(rng.uniform(0.4, 3.5), 2),
            'reverb_wet':  round(rng.uniform(r_lo, r_hi), 2),
            'pan':         round(pans[i], 2),
            'gain':        round(rng.uniform(0.07, 0.20), 3),
            'pitch':       pitch,
        })

    return textures
