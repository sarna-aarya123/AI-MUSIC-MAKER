"""
loop_service.py — Loop-Based Underground Beat Identity Engine
Generates motif + bass + texture stack for continuous looping playback.
No chord progressions, no structured song form.
"""
import random

# ── Note map ──────────────────────────────────────────────────────────────────
NOTE_MAP = {
    'C': 60, 'C#': 61, 'Db': 61, 'D': 62, 'D#': 63, 'Eb': 63,
    'E': 64, 'F': 65, 'F#': 66, 'Gb': 66, 'G': 67, 'G#': 68,
    'Ab': 68, 'A': 69, 'A#': 70, 'Bb': 70, 'B': 71,
}

# ── Rhythmic templates (beat positions within one 4-beat bar) ─────────────────
# Multiple templates per genre give variety across generations.
_RHYTHMS = {
    'rage': [
        [0.00, 0.25, 0.75, 1.00, 1.50, 2.00, 2.25, 2.75, 3.00, 3.50],
        [0.00, 0.50, 0.75, 1.50, 1.75, 2.00, 2.75, 3.00, 3.50, 3.75],
        [0.00, 0.25, 1.00, 1.25, 1.75, 2.00, 2.50, 2.75, 3.25, 3.75],
        [0.00, 0.75, 1.00, 1.75, 2.25, 2.75, 3.00, 3.50, 3.75],
    ],
    'pluggnb': [
        [0.00, 0.75, 1.50, 2.25, 3.00, 3.75],
        [0.00, 0.50, 1.25, 2.00, 2.75, 3.50],
        [0.25, 1.00, 2.00, 2.75, 3.50],
        [0.00, 1.00, 1.75, 2.75, 3.50],
    ],
    'dark_trap': [
        [0.00, 2.00, 3.50],
        [0.00, 1.50, 3.00],
        [0.00, 1.75, 2.50, 3.75],
        [0.50, 2.00, 3.75],
    ],
    'cloud': [
        [0.00, 0.50, 1.00, 1.50, 2.00, 2.50, 3.00, 3.50],
        [0.00, 0.50, 1.00, 2.00, 2.75, 3.25],
        [0.25, 0.75, 1.50, 2.00, 2.75, 3.50],
        [0.00, 0.75, 1.50, 2.25, 3.00, 3.75],
    ],
}

# ── Melodic contours (indices into scale array, 0 = root) ────────────────────
# Shape of pitch movement across the motif. Cycled if note count exceeds length.
_CONTOURS = {
    'rage': [
        [0, 2, 2, 1, 0, 2, 1, 0, 2, 0],    # hook: root-5th riff
        [2, 2, 1, 0, 2, 1, 0, 0, 2, 1],    # downward hook
        [0, 1, 0, 2, 0, 1, 0, 2, 0, 0],    # oscillating
        [1, 2, 1, 0, 1, 0, 2, 0, 1, 0],    # circling minor 3rd
    ],
    'pluggnb': [
        [0, 1, 3, 4, 3, 2, 1, 0],          # rise and resolve
        [2, 3, 5, 4, 3, 2, 0, 1],          # arc through scale
        [0, 2, 4, 3, 2, 1, 0, 2],          # flowing phrase
        [4, 3, 2, 1, 0, 1, 3, 4],          # valley shape
    ],
    'dark_trap': [
        [4, 2, 0],                           # chromatic descent
        [3, 1, 0],                           # minor drop
        [5, 3, 1, 0],                        # slow dark descent
        [0, 4, 1, 0],                        # minimal and moody
    ],
    'cloud': [
        [0, 2, 4, 2, 3, 4, 2, 1, 0, 2],    # cascading rise
        [2, 4, 3, 4, 2, 0, 2, 4, 3, 2],    # floating
        [0, 1, 2, 4, 3, 2, 4, 2, 0, 1],    # arpeggio sweep
        [4, 2, 0, 2, 4, 3, 2, 4, 2, 0],    # pentatonic wave
    ],
}

# ── Texture archetypes ────────────────────────────────────────────────────────
_ARCHETYPES = {
    'aggressive': {
        'osc_pool':     ['sawtooth', 'square'],
        'filter_range': (700,  2200),
        'reverb_range': (0.10, 0.30),
        'gain_range':   (0.14, 0.22),
        'detune_range': (-30,  30),
        'filter_q':     (2.5,  6.0),
    },
    'dark': {
        'osc_pool':     ['sawtooth', 'sawtooth', 'square'],
        'filter_range': (160,  480),
        'reverb_range': (0.45, 0.70),
        'gain_range':   (0.10, 0.19),
        'detune_range': (-18,  18),
        'filter_q':     (1.0,  3.5),
    },
    'ambient': {
        'osc_pool':     ['sine', 'triangle'],
        'filter_range': (280,  800),
        'reverb_range': (0.78, 0.95),
        'gain_range':   (0.05, 0.11),
        'detune_range': (-5,   5),
        'filter_q':     (0.4,  1.2),
    },
    'airy': {
        'osc_pool':     ['triangle', 'sine', 'sawtooth'],
        'filter_range': (2000, 5500),
        'reverb_range': (0.65, 0.88),
        'gain_range':   (0.06, 0.13),
        'detune_range': (-10,  10),
        'filter_q':     (0.5,  1.8),
    },
    'wide': {
        'osc_pool':     ['sawtooth', 'square', 'triangle'],
        'filter_range': (500,  1800),
        'reverb_range': (0.38, 0.60),
        'gain_range':   (0.09, 0.17),
        'detune_range': (-45,  45),
        'filter_q':     (0.7,  2.5),
    },
}

# ── Genre definitions ─────────────────────────────────────────────────────────
GENRE_PARAMS = {
    'rage': {
        'bpm_range':          (135, 155),
        'loop_bars':          (1, 2),
        'scale':              [0, 3, 5, 7, 10],         # minor pentatonic
        'pitch_range':        (54, 69),                  # low-mid register, aggressive
        'motif_n':            (7, 10),
        'rhythm_key':         'rage',
        'contour_key':        'rage',
        'bass_intervals':     [0, 7, 10],
        'portamento':         0.015,
        'texture_archetypes': ['aggressive', 'aggressive', 'dark', 'dark', 'wide'],
        'texture_intervals':  [0, 7, 10, -12, 7],
        'texture_count':      (3, 5),
    },
    'pluggnb': {
        'bpm_range':          (65, 90),
        'loop_bars':          (2, 4),
        'scale':              [0, 2, 3, 5, 7, 9, 10],   # natural minor — melodic
        'pitch_range':        (62, 78),                  # mid register, dreamy
        'motif_n':            (6, 9),
        'rhythm_key':         'pluggnb',
        'contour_key':        'pluggnb',
        'bass_intervals':     [0, 3, 7, 10],
        'portamento':         0.045,
        'texture_archetypes': ['ambient', 'airy', 'wide', 'ambient', 'airy'],
        'texture_intervals':  [0, 3, 7, 10, 14],
        'texture_count':      (4, 6),
    },
    'dark_trap': {
        'bpm_range':          (120, 142),
        'loop_bars':          (2, 4),
        'scale':              [0, 1, 3, 5, 6, 8, 10],   # phrygian — ominous
        'pitch_range':        (48, 64),                  # low register, dark
        'motif_n':            (4, 6),
        'rhythm_key':         'dark_trap',
        'contour_key':        'dark_trap',
        'bass_intervals':     [0, 5, 1, 8],
        'portamento':         0.028,
        'texture_archetypes': ['dark', 'dark', 'wide', 'ambient', 'dark'],
        'texture_intervals':  [0, 1, 6, 10, -12],
        'texture_count':      (4, 6),
    },
    'cloud': {
        'bpm_range':          (72, 105),
        'loop_bars':          (2, 4),
        'scale':              [0, 2, 4, 7, 9],           # major pentatonic — bright
        'pitch_range':        (66, 84),                  # high register, airy
        'motif_n':            (8, 12),
        'rhythm_key':         'cloud',
        'contour_key':        'cloud',
        'bass_intervals':     [0, 4, 7, 9],
        'portamento':         0.055,
        'texture_archetypes': ['airy', 'ambient', 'wide', 'airy', 'ambient'],
        'texture_intervals':  [0, 4, 7, 9, 12],
        'texture_count':      (4, 6),
    },
}


# ── Lead instrument synth configs ────────────────────────────────────────────
INSTRUMENT_CONFIGS = {
    'bell': {
        'osc_type': 'triangle',
        'envelope': {'attack': 0.002, 'decay': 1.2, 'sustain': 0.0, 'release': 2.0},
        'filter_env': {'attack': 0.001, 'decay': 0.5, 'sustain': 0.0, 'release': 1.0,
                       'baseFrequency': 1200, 'octaves': 3.0},
        'filter_freq': 4500, 'filter_q': 2.0, 'portamento': 0.0,
    },
    'pluck': {
        'osc_type': 'sawtooth',
        'envelope': {'attack': 0.001, 'decay': 0.25, 'sustain': 0.0, 'release': 0.4},
        'filter_env': {'attack': 0.001, 'decay': 0.12, 'sustain': 0.0, 'release': 0.3,
                       'baseFrequency': 500, 'octaves': 3.5},
        'filter_freq': 2200, 'filter_q': 3.5, 'portamento': 0.008,
    },
    'saw_lead': {
        'osc_type': 'sawtooth',
        'envelope': {'attack': 0.005, 'decay': 0.12, 'sustain': 0.35, 'release': 0.55},
        'filter_env': {'attack': 0.003, 'decay': 0.10, 'sustain': 0.18, 'release': 0.40,
                       'baseFrequency': 700, 'octaves': 2.8},
        'filter_freq': 1600, 'filter_q': 3.8, 'portamento': 0.015,
    },
    'fm_lead': {
        'osc_type': 'fmsquare',
        'envelope': {'attack': 0.003, 'decay': 0.18, 'sustain': 0.25, 'release': 0.70},
        'filter_env': {'attack': 0.002, 'decay': 0.14, 'sustain': 0.20, 'release': 0.55,
                       'baseFrequency': 600, 'octaves': 2.5},
        'filter_freq': 2500, 'filter_q': 2.5, 'portamento': 0.02,
    },
    'glass': {
        'osc_type': 'sine',
        'envelope': {'attack': 0.015, 'decay': 0.9, 'sustain': 0.0, 'release': 1.8},
        'filter_env': {'attack': 0.008, 'decay': 0.4, 'sustain': 0.0, 'release': 0.8,
                       'baseFrequency': 2000, 'octaves': 2.0},
        'filter_freq': 6000, 'filter_q': 1.5, 'portamento': 0.0,
    },
    'square': {
        'osc_type': 'square',
        'envelope': {'attack': 0.003, 'decay': 0.08, 'sustain': 0.45, 'release': 0.35},
        'filter_env': {'attack': 0.002, 'decay': 0.07, 'sustain': 0.35, 'release': 0.28,
                       'baseFrequency': 400, 'octaves': 3.0},
        'filter_freq': 1000, 'filter_q': 4.5, 'portamento': 0.008,
    },
}

# ── Text description parser ───────────────────────────────────────────────────

def parse_description(text):
    """
    Extract sound profile from free-text description.
    Returns dict with genre_hint, lead_instrument, energy, brightness, space, density.
    Text keywords override dropdown values when present.
    """
    t = text.lower()
    profile = {
        'genre_hint':      None,
        'lead_instrument': None,
        'energy':          0.5,   # 0=soft .. 1=aggressive
        'brightness':      0.5,   # 0=dark  .. 1=bright
        'space':           0.5,   # 0=dry   .. 1=wet/reverb
        'density':         0.5,   # 0=sparse .. 1=dense
    }

    # Genre hints (checked in priority order — more specific first)
    if any(w in t for w in ['dark trap', 'dark_trap', 'ominous', 'sinister', 'evil']):
        profile['genre_hint'] = 'dark_trap'
    elif any(w in t for w in ['pluggnb', 'plug gnb', 'plug n b', 'summrs', 'autumn']):
        profile['genre_hint'] = 'pluggnb'
    elif any(w in t for w in ['cloud rap', 'cloud rap', 'dreamy', 'ethereal', 'float']):
        profile['genre_hint'] = 'cloud'
    elif any(w in t for w in ['rage', 'ken carson', 'yeat', 'destroy lonely', 'aggressive']):
        profile['genre_hint'] = 'rage'

    # Lead instrument (explicit keyword wins)
    if any(w in t for w in ['fm lead', 'fm synth', 'frequency mod']):
        profile['lead_instrument'] = 'fm_lead'
    elif any(w in t for w in ['saw lead', 'sawtooth', 'saw synth']):
        profile['lead_instrument'] = 'saw_lead'
    elif any(w in t for w in ['bell', 'bells', 'metallic', 'chime']):
        profile['lead_instrument'] = 'bell'
    elif any(w in t for w in ['pluck', 'plucky', 'pizz']):
        profile['lead_instrument'] = 'pluck'
    elif any(w in t for w in ['glass', 'crystal', 'crystalline', 'glassy']):
        profile['lead_instrument'] = 'glass'
    elif 'square' in t:
        profile['lead_instrument'] = 'square'

    # Energy
    if any(w in t for w in ['aggressive', 'hard', 'intense', 'heavy', 'loud', 'punchy']):
        profile['energy'] = 0.85
    elif any(w in t for w in ['soft', 'gentle', 'light', 'subtle', 'quiet', 'calm']):
        profile['energy'] = 0.20

    # Brightness
    if any(w in t for w in ['bright', 'crisp', 'sharp', 'piercing', 'high', 'airy']):
        profile['brightness'] = 0.85
    elif any(w in t for w in ['dark', 'warm', 'muddy', 'deep', 'low', 'sub']):
        profile['brightness'] = 0.20

    # Space
    if any(w in t for w in ['reverb', 'spacious', 'room', 'hall', 'ambient', 'airy',
                             'float', 'ethereal', 'dreamy', 'washed']):
        profile['space'] = 0.85
    elif any(w in t for w in ['dry', 'close', 'intimate', 'direct', 'tight']):
        profile['space'] = 0.15

    # Density
    if any(w in t for w in ['dense', 'busy', 'full', 'complex', 'many']):
        profile['density'] = 0.85
    elif any(w in t for w in ['sparse', 'minimal', 'simple', 'bare', 'empty']):
        profile['density'] = 0.20

    return profile


# ── Public API ────────────────────────────────────────────────────────────────

def generate_loop(genre='rage', root='A', bpm=None, bars=4, seed=None,
                  description=None, lead_instrument=None):
    """
    Generate a complete loop identity: motif + bass + texture stack.
    description — free text; parsed keywords override genre/instrument dropdowns.
    lead_instrument — explicit override ('bell', 'pluck', 'saw_lead', 'fm_lead', 'glass', 'square').
    Returns dict ready for JSON serialisation.
    """
    rng = random.Random(seed)

    # Parse description; text keywords override dropdown values
    if description and description.strip():
        profile = parse_description(description)
        if profile['genre_hint']:
            genre = profile['genre_hint']
        if profile['lead_instrument'] and not lead_instrument:
            lead_instrument = profile['lead_instrument']
    else:
        profile = {}

    params = GENRE_PARAMS.get(genre, GENRE_PARAMS['rage'])
    scale  = params['scale']

    tonal_center = NOTE_MAP.get(root, 69)

    if bpm is None:
        bpm = rng.randint(*params['bpm_range'])
    bpm = max(60, min(220, int(bpm)))

    loop_bars   = min(bars, rng.randint(*params['loop_bars']))
    loop_length = loop_bars * 4

    motif    = _gen_motif(rng, params, tonal_center, loop_length, scale)
    bass     = _gen_bass(rng, params, tonal_center, loop_length)
    textures = _gen_textures(rng, params, tonal_center)

    synth_config = INSTRUMENT_CONFIGS.get(lead_instrument) if lead_instrument else None

    return {
        'motif':           motif,
        'bass':            bass,
        'textures':        textures,
        'bpm':             bpm,
        'loop_length':     loop_length,
        'tonal_center':    tonal_center,
        'root':            root,
        'genre':           genre,
        'scale':           scale,
        'variation_seed':  rng.randint(0, 99999),
        'portamento':      params['portamento'],
        'lead_instrument': lead_instrument,
        'synth_config':    synth_config,
        'sound_profile':   profile,
    }


# ── Motif generation ──────────────────────────────────────────────────────────

def _gen_motif(rng, params, tonal_center, loop_length, scale):
    rhythm_key  = params['rhythm_key']
    contour_key = params['contour_key']
    lo_pitch, hi_pitch = params['pitch_range']

    # Build beat grid: repeat template across all bars
    template    = rng.choice(_RHYTHMS[rhythm_key])
    bars_needed = int(loop_length / 4)
    raw_beats   = []

    for bar in range(bars_needed):
        offset = bar * 4.0
        for b in template:
            beat = b + offset
            # Bar 2+: occasional ±0.25 beat variation to break strict repetition
            if bar > 0 and rng.random() < 0.20:
                beat = beat + rng.choice([-0.25, 0.25])
            beat = round(beat / 0.25) * 0.25   # snap to 16th grid
            if 0.0 <= beat < loop_length:
                raw_beats.append(round(beat, 3))

    raw_beats = sorted(set(raw_beats))

    # Trim to desired note count
    n     = rng.randint(*params['motif_n'])
    beats = raw_beats[:n] if len(raw_beats) > n else raw_beats
    if not beats:
        beats = [0.0]

    # Build scale pitch pool within genre's pitch register.
    # Root offsets from tonal_center directly so pitch classes stay correct.
    root_pc   = tonal_center % 12
    scale_pitches = []
    for oct_offset in range(-24, 25, 12):
        for interval in scale:
            p = tonal_center + oct_offset + interval
            if lo_pitch <= p <= hi_pitch:
                scale_pitches.append(p)
    if not scale_pitches:
        scale_pitches = [tonal_center]
    scale_pitches.sort()

    center_pitch = (lo_pitch + hi_pitch) // 2
    contour      = rng.choice(_CONTOURS[contour_key])

    notes = []
    for i, beat in enumerate(beats):
        # Map contour index → scale degree → pitch class → nearest in-range pitch
        degree   = min(contour[i % len(contour)], len(scale) - 1)
        target_pc = (root_pc + scale[degree]) % 12
        candidates = [p for p in scale_pitches if p % 12 == target_pc] or scale_pitches

        # Prefer pitch closest to previous note for smooth melodic line
        ref = notes[-1]['pitch'] if notes else center_pitch
        pitch = min(candidates, key=lambda p: abs(p - ref))

        gap      = (beats[i + 1] - beat) if i + 1 < len(beats) else (loop_length - beat)
        duration = round(min(max(0.125, gap * 0.85), 2.0), 3)
        velocity = _accent_velocity(rng, beat)

        notes.append({
            'phase_start':    round(beat / loop_length, 6),
            'phase_duration': round(duration / loop_length, 6),
            'pitch':          pitch,
            'velocity':       velocity,
        })

    return notes


def _accent_velocity(rng, beat):
    """Musical velocity: accent downbeats, humanize all notes."""
    pos = beat % 4
    if pos < 0.01:          base = 100   # downbeat
    elif abs(pos - 2.0) < 0.01: base = 92    # backbeat
    elif pos % 1.0 < 0.01:  base = 84   # quarter pulse
    else:                    base = 74   # 8th / 16th (offbeat)
    return max(55, min(115, base + rng.randint(-7, 7)))


# ── Bass generation ───────────────────────────────────────────────────────────

def _gen_bass(rng, params, tonal_center, loop_length):
    root = tonal_center - 24
    while root < 28:
        root += 12

    intervals  = params['bass_intervals']
    rhythm_key = params['rhythm_key']

    if rhythm_key == 'dark_trap':
        # Single heavy sub drone — maximum weight
        return [{
            'phase_start':    0.0,
            'phase_duration': 1.0,
            'pitch':          root,
            'velocity':       108,
        }]

    if rhythm_key == 'cloud':
        # Gentle two-note movement following the scale
        note2     = root + rng.choice(intervals[1:])
        dur_phase = round(0.5 * 0.90, 6)
        return [
            {'phase_start': 0.0, 'phase_duration': dur_phase, 'pitch': root,  'velocity': 88},
            {'phase_start': 0.5, 'phase_duration': dur_phase, 'pitch': note2, 'velocity': 80},
        ]

    # rage / pluggnb: 45% drone, 55% two-note
    if rng.random() < 0.45:
        return [{
            'phase_start':    0.0,
            'phase_duration': 1.0,
            'pitch':          root,
            'velocity':       98 if rhythm_key == 'rage' else 88,
        }]

    note2     = root + rng.choice(intervals[1:])
    dur_phase = round(0.5 * 0.92, 6)
    vel1      = 98 if rhythm_key == 'rage' else 88
    vel2      = 88 if rhythm_key == 'rage' else 80
    return [
        {'phase_start': 0.0, 'phase_duration': dur_phase, 'pitch': root,  'velocity': vel1},
        {'phase_start': 0.5, 'phase_duration': dur_phase, 'pitch': note2, 'velocity': vel2},
    ]


# ── Texture stack generation ──────────────────────────────────────────────────

def _gen_textures(rng, params, tonal_center):
    archetypes = params['texture_archetypes']
    intervals  = params['texture_intervals']
    count      = rng.randint(*params['texture_count'])

    pans = [-0.80, -0.50, 0.0, 0.50, 0.80, -0.65, 0.65]
    rng.shuffle(pans)

    textures = []
    for i in range(min(count, len(archetypes))):
        arch_name = archetypes[i]
        arch      = _ARCHETYPES[arch_name]

        interval = intervals[i % len(intervals)]
        pitch    = max(24, min(72, tonal_center + interval))
        # Occasional octave spread for harmonic richness
        if rng.random() < 0.22:
            pitch = max(24, min(72, pitch + 12))

        textures.append({
            'osc_type':    rng.choice(arch['osc_pool']),
            'detune':      round(rng.uniform(*arch['detune_range']), 1),
            'filter_freq': round(rng.uniform(*arch['filter_range']), 1),
            'filter_q':    round(rng.uniform(*arch['filter_q']), 2),
            'reverb_wet':  round(rng.uniform(*arch['reverb_range']), 2),
            'pan':         round(pans[i % len(pans)], 2),
            'gain':        round(rng.uniform(*arch['gain_range']), 3),
            'pitch':       pitch,
            'archetype':   arch_name,
        })

    return textures
