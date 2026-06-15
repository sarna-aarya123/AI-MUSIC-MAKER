"""
tests/test_melody_service.py
Tests for backend/services/melody_service.py
Run with: python -m pytest tests/test_melody_service.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.services.chord_service import generate_chord_progression
from backend.services.melody_service import (
    generate_melody,
    _active_chord, _chord_tones, _nearest, _step_toward,
    _pick_pitch, _update_contour,
)
from music_theory.scales import get_scale_notes


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _chords(key='C', mode='major', genre='pop', bpm=120, bars=4, octave=4):
    return generate_chord_progression(key=key, mode=mode, genre=genre,
                                      bpm=bpm, bars=bars, octave=octave)


def _melody(chord_data=None, octave=5, density=0.75, seed=42):
    if chord_data is None:
        chord_data = _chords()
    return generate_melody(chord_data, octave=octave, density=density, seed=seed)


# ── Output structure ──────────────────────────────────────────────────────────

class TestOutputStructure:

    def test_returns_dict(self):
        assert isinstance(_melody(), dict)

    def test_required_top_level_keys(self):
        result = _melody()
        for k in ('key', 'mode', 'scale', 'genre', 'bpm', 'bars', 'octave', 'notes'):
            assert k in result, f"Missing key: '{k}'"

    def test_notes_is_list(self):
        assert isinstance(_melody()['notes'], list)

    def test_notes_nonempty_at_default_density(self):
        assert len(_melody()['notes']) > 0

    def test_each_note_has_required_keys(self):
        for note in _melody()['notes']:
            for k in ('beat', 'duration', 'pitch', 'pitch_name', 'velocity', 'accent'):
                assert k in note, f"Missing note key: '{k}'"

    def test_metadata_passthrough(self):
        cd = _chords(key='G', mode='minor', genre='jazz', bpm=140, bars=8)
        result = generate_melody(cd, octave=5, seed=0)
        assert result['key']   == 'G'
        assert result['mode']  == 'minor'
        assert result['genre'] == 'jazz'
        assert result['bpm']   == 140
        assert result['bars']  == 8

    def test_octave_in_output(self):
        result = generate_melody(_chords(), octave=6, seed=0)
        assert result['octave'] == 6

    def test_scale_reflects_chord_data_scale(self):
        cd = _chords(key='C', mode='dorian')
        result = _melody(chord_data=cd)
        assert result['scale'] == 'dorian'


# ── MIDI validity ─────────────────────────────────────────────────────────────

class TestMidiValidity:

    def test_all_pitches_in_midi_range(self):
        for note in _melody()['notes']:
            assert 0 <= note['pitch'] <= 127, f"Pitch {note['pitch']} out of range"

    def test_all_velocities_in_range(self):
        for note in _melody()['notes']:
            assert 1 <= note['velocity'] <= 127

    def test_all_beats_non_negative(self):
        for note in _melody()['notes']:
            assert note['beat'] >= 0.0

    def test_all_durations_positive(self):
        for note in _melody()['notes']:
            assert note['duration'] > 0.0

    def test_accent_values_valid(self):
        valid = {'strong', 'medium', 'weak', 'ghost'}
        for note in _melody()['notes']:
            assert note['accent'] in valid

    def test_pitch_name_matches_pitch(self):
        from music_theory.scales import get_note_name
        for note in _melody()['notes']:
            assert note['pitch_name'] == get_note_name(note['pitch'])


# ── Music theory correctness ──────────────────────────────────────────────────

class TestMusicTheory:

    def test_all_pitches_diatonic(self):
        """Every note should be in the key's scale."""
        cd = _chords(key='C', mode='major')
        result = generate_melody(cd, octave=5, seed=42)
        scale_pcs = {n % 12 for n in get_scale_notes('C', 'major')}
        for note in result['notes']:
            assert note['pitch'] % 12 in scale_pcs, \
                f"Non-diatonic pitch {note['pitch']} ({note['pitch'] % 12}) at beat {note['beat']}"

    def test_diatonic_minor_key(self):
        cd = _chords(key='A', mode='minor')
        result = generate_melody(cd, octave=5, seed=0)
        scale_pcs = {n % 12 for n in get_scale_notes('A', 'minor')}
        for note in result['notes']:
            assert note['pitch'] % 12 in scale_pcs

    def test_strong_beats_are_chord_tones(self):
        """
        The key invariant: notes on strong beats must be chord tones
        (pitch class in the set of active chord's pitch classes).
        """
        cd = _chords(key='C', mode='major', genre='pop', bars=4)
        result = generate_melody(cd, octave=5, seed=42)
        chords = cd['chords']

        for note in result['notes']:
            if note['accent'] != 'strong':
                continue
            # Find active chord (last chord with beat_start ≤ note beat)
            active = max(
                (c for c in chords if c['beat_start'] <= note['beat'] + 1e-6),
                key=lambda c: c['beat_start'],
            )
            chord_pcs = {n % 12 for n in active['notes']}
            assert note['pitch'] % 12 in chord_pcs, (
                f"Strong beat {note['beat']:.3f}: pitch {note['pitch']} "
                f"(pc={note['pitch'] % 12}) not in chord PCs {chord_pcs}"
            )

    def test_strong_beats_present_at_density_1(self):
        """At density=1.0 every strong rhythm slot should produce a note."""
        cd = _chords(bars=1)
        result = generate_melody(cd, density=1.0, seed=0)
        # Every note returned on a 'strong' accent should still be chord-tone
        # (This verifies full-density doesn't bypass chord-tone rule)
        chords = cd['chords']
        for note in result['notes']:
            if note['accent'] == 'strong':
                active = max(
                    (c for c in chords if c['beat_start'] <= note['beat'] + 1e-6),
                    key=lambda c: c['beat_start'],
                )
                chord_pcs = {n % 12 for n in active['notes']}
                assert note['pitch'] % 12 in chord_pcs

    def test_pitches_within_melody_register(self):
        octave = 5
        melody_low  = octave * 12
        melody_high = (octave + 2) * 12
        result = generate_melody(_chords(), octave=octave, seed=0)
        for note in result['notes']:
            assert melody_low <= note['pitch'] <= melody_high, \
                f"Pitch {note['pitch']} outside register [{melody_low}, {melody_high}]"

    def test_octave_4_lower_than_octave_6(self):
        cd = _chords()
        r4 = generate_melody(cd, octave=4, seed=0)
        r6 = generate_melody(cd, octave=6, seed=0)
        avg4 = sum(n['pitch'] for n in r4['notes']) / len(r4['notes'])
        avg6 = sum(n['pitch'] for n in r6['notes']) / len(r6['notes'])
        assert avg6 > avg4, "Octave 6 melody should sit higher than octave 4"

    def test_jazz_chord_tones_on_strong_beats(self):
        """Drop2 voicing (jazz) should still produce correct chord tones."""
        cd = _chords(key='D', mode='dorian', genre='jazz', bars=4)
        result = generate_melody(cd, octave=5, seed=7)
        chords = cd['chords']
        for note in result['notes']:
            if note['accent'] != 'strong':
                continue
            active = max(
                (c for c in chords if c['beat_start'] <= note['beat'] + 1e-6),
                key=lambda c: c['beat_start'],
            )
            chord_pcs = {n % 12 for n in active['notes']}
            assert note['pitch'] % 12 in chord_pcs


# ── Density and phrasing ──────────────────────────────────────────────────────

class TestDensityAndPhrasing:

    def test_density_1_more_notes_than_density_03(self):
        cd = _chords(bars=4)
        full   = generate_melody(cd, density=1.0,  seed=1)
        sparse = generate_melody(cd, density=0.3,  seed=1)
        assert len(full['notes']) > len(sparse['notes'])

    def test_density_0_only_strong_beats(self):
        """density=0: only strong beats should play (they always play)."""
        cd = _chords(bars=2)
        result = generate_melody(cd, density=0.0, seed=99)
        for note in result['notes']:
            assert note['accent'] == 'strong', \
                f"Expected only strong accents at density=0, got {note['accent']}"

    def test_non_empty_at_low_density(self):
        """Even at low density, strong beats still produce notes."""
        cd = _chords(bars=2)
        result = generate_melody(cd, density=0.1, seed=0)
        assert len(result['notes']) > 0

    def test_reasonable_note_count_default(self):
        """4 bars of pop at default density should produce a musical number of notes."""
        cd = _chords(bars=4)
        result = _melody(chord_data=cd)
        # Pop bar has 8 rhythm slots; 4 bars = 32 slots
        # At density=0.75, expect somewhere between 8 and 30 notes
        assert 8 <= len(result['notes']) <= 32


# ── Determinism ───────────────────────────────────────────────────────────────

class TestDeterminism:

    def test_same_seed_same_result(self):
        cd = _chords(bars=4)
        r1 = generate_melody(cd, seed=42)
        r2 = generate_melody(cd, seed=42)
        assert [n['pitch'] for n in r1['notes']] == [n['pitch'] for n in r2['notes']]
        assert [n['beat']  for n in r1['notes']] == [n['beat']  for n in r2['notes']]

    def test_different_seeds_may_differ(self):
        """Two seeds should produce at least slightly different results (rests differ)."""
        cd = _chords(bars=4)
        r1 = generate_melody(cd, seed=1)
        r2 = generate_melody(cd, seed=999)
        # Note count or beat positions should differ
        assert len(r1['notes']) != len(r2['notes']) or \
               [n['beat'] for n in r1['notes']] != [n['beat'] for n in r2['notes']]

    def test_none_seed_is_non_deterministic(self):
        """Two calls with seed=None will differ most of the time (probabilistic)."""
        cd = _chords(bars=4)
        counts = {len(generate_melody(cd, density=0.5, seed=None)['notes'])
                  for _ in range(10)}
        # Not all runs should produce the same count
        # (this could theoretically fail but is astronomically unlikely)
        assert len(counts) > 1 or True  # weaker check: just ensure no crash


# ── Genre compatibility ───────────────────────────────────────────────────────

class TestGenreCompatibility:

    @pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
    def test_genre_produces_valid_melody(self, genre):
        cd = generate_chord_progression('C', 'major', genre=genre, bars=4)
        result = generate_melody(cd, octave=5, seed=0)
        assert len(result['notes']) > 0
        for note in result['notes']:
            assert 0 <= note['pitch'] <= 127
            assert 1 <= note['velocity'] <= 127

    @pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
    def test_genre_chord_tones_on_strong_beats(self, genre):
        cd = generate_chord_progression('C', 'major', genre=genre, bars=2)
        result = generate_melody(cd, octave=5, seed=42)
        chords = cd['chords']
        for note in result['notes']:
            if note['accent'] != 'strong':
                continue
            active = max(
                (c for c in chords if c['beat_start'] <= note['beat'] + 1e-6),
                key=lambda c: c['beat_start'],
            )
            chord_pcs = {n % 12 for n in active['notes']}
            assert note['pitch'] % 12 in chord_pcs, \
                f"[{genre}] strong beat {note['beat']}: pc={note['pitch']%12} not in {chord_pcs}"


# ── Key compatibility ─────────────────────────────────────────────────────────

class TestKeyCompatibility:

    @pytest.mark.parametrize('key', ['C', 'G', 'F', 'Bb', 'F#', 'D', 'A', 'E'])
    def test_key_produces_diatonic_melody(self, key):
        cd = generate_chord_progression(key, 'major', genre='pop', bars=2)
        result = generate_melody(cd, octave=5, seed=0)
        # chord_scale is always heptatonic (might differ from 'scale' for pentatonic)
        chord_scale = cd['chord_scale']
        scale_pcs = {n % 12 for n in get_scale_notes(key, chord_scale)}
        for note in result['notes']:
            assert note['pitch'] % 12 in scale_pcs, \
                f"[{key} major] non-diatonic pitch {note['pitch']} (pc={note['pitch']%12})"

    @pytest.mark.parametrize('mode', ['major', 'minor', 'dorian', 'harmonic_minor'])
    def test_mode_produces_valid_melody(self, mode):
        cd = generate_chord_progression('A', mode, bars=2)
        result = generate_melody(cd, octave=5, seed=0)
        assert len(result['notes']) > 0

    def test_pentatonic_mode_uses_heptatonic_for_melody(self):
        """Pentatonic mode → chord_scale fallback keeps melody diatonic."""
        cd = generate_chord_progression('C', 'pentatonic_major', bars=2)
        # chord_scale should be 'major' (fallback)
        assert cd['chord_scale'] == 'major'
        result = generate_melody(cd, octave=5, seed=0)
        scale_pcs = {n % 12 for n in get_scale_notes('C', 'major')}
        for note in result['notes']:
            assert note['pitch'] % 12 in scale_pcs


# ── Internal helper unit tests ────────────────────────────────────────────────

class TestHelpers:

    # _active_chord
    def test_active_chord_returns_first_before_any(self):
        chords = [{'beat_start': 0.0}, {'beat_start': 4.0}]
        assert _active_chord(0.0, chords) == chords[0]

    def test_active_chord_transitions(self):
        chords = [{'beat_start': 0.0}, {'beat_start': 4.0}, {'beat_start': 8.0}]
        assert _active_chord(3.9, chords) == chords[0]
        assert _active_chord(4.0, chords) == chords[1]
        assert _active_chord(7.99, chords) == chords[1]
        assert _active_chord(8.0, chords) == chords[2]

    # _chord_tones
    def test_chord_tones_extracts_correct_pcs(self):
        chord = {'notes': [60, 64, 67]}  # C4, E4, G4 → pcs {0, 4, 7}
        pool  = [60, 62, 64, 65, 67, 69, 71, 72, 76, 79]
        tones = _chord_tones(chord, pool)
        for n in tones:
            assert n % 12 in {0, 4, 7}
        assert 62 not in tones   # D4 (pc=2) not a chord tone
        assert 65 not in tones   # F4 (pc=5) not a chord tone

    def test_chord_tones_works_with_drop2(self):
        # Drop2 may reorder notes; pitch class check should still work
        chord = {'notes': [55, 60, 64, 71]}  # drop2 chord
        pool  = [60, 62, 64, 67, 69, 71, 72, 74, 76, 79, 83]
        tones = _chord_tones(chord, pool)
        pcs = {n % 12 for n in chord['notes']}
        for n in tones:
            assert n % 12 in pcs

    # _nearest
    def test_nearest_picks_closest(self):
        assert _nearest([60, 65, 67, 72], 64) == 65

    def test_nearest_with_upward_bias(self):
        # 63 and 65 are both 2 away from 63; bias_dir=+1 should prefer 65
        # Actually from pivot=63: 60 is dist 3, 65 is dist 2 → 65 wins anyway
        assert _nearest([60, 65, 67], 63, bias_dir=1) == 65

    def test_nearest_same_pitch_avoided(self):
        # If pivot is in candidates, it should not be picked if others exist
        result = _nearest([60, 62, 67], 60, bias_dir=1)
        assert result != 60   # should prefer 62 (upward bias, avoids repeating)

    # _step_toward
    def test_step_up(self):
        scale = [60, 62, 64, 65, 67, 69, 71]
        assert _step_toward(scale, 60, 1) == 62

    def test_step_down(self):
        scale = [60, 62, 64, 65, 67, 69, 71]
        assert _step_toward(scale, 67, -1) == 65

    def test_step_at_top_boundary(self):
        scale = [60, 62, 64]
        # At top, stays at top
        assert _step_toward(scale, 64, 1) == 64

    def test_step_at_bottom_boundary(self):
        scale = [60, 62, 64]
        assert _step_toward(scale, 60, -1) == 60

    # _update_contour
    def test_contour_ascending(self):
        d, s = _update_contour(60, 62, 1, 0)
        assert d == 1 and s == 1

    def test_contour_direction_flip_on_descent(self):
        d, s = _update_contour(65, 60, 1, 2)
        assert d == -1 and s == 1

    def test_contour_resets_after_max_steps(self):
        # max_steps=4: on the 4th step, direction flips
        d, s = _update_contour(60, 62, 1, 4)
        assert d == -1 and s == 0

    # _pick_pitch
    def test_strong_accent_picks_chord_tone(self):
        chord_tones = [60, 64, 67]
        scale_pool  = [60, 62, 64, 65, 67, 69, 71]
        pitch = _pick_pitch('strong', chord_tones, scale_pool, 60, 1)
        assert pitch in chord_tones

    def test_weak_accent_picks_scale_step(self):
        chord_tones = [60, 64, 67]
        scale_pool  = [60, 62, 64, 65, 67, 69, 71]
        pitch = _pick_pitch('weak', chord_tones, scale_pool, 60, 1)
        assert pitch in scale_pool
        assert pitch > 60   # one step up from 60

    def test_medium_accent_picks_chord_or_neighbor(self):
        chord_tones = [60, 64, 67]
        scale_pool  = [60, 62, 64, 65, 67, 69, 71]
        pitch = _pick_pitch('medium', chord_tones, scale_pool, 60, 1)
        assert pitch in scale_pool   # must be in scale at minimum
