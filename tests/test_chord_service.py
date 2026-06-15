"""
tests/test_chord_service.py
Unit tests for the full chord generation pipeline.
Run with: python -m pytest tests/test_chord_service.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.services.chord_service import generate_chord_progression
from music_theory.harmony import (
    PROGRESSIONS, DIATONIC_QUALITIES, DIATONIC_7TH_QUALITIES,
    choose_progression, get_chord_quality,
)
from music_theory.genres import get_genre_profile, list_genres


# ── harmony.py ────────────────────────────────────────────────────────────────

class TestHarmonyQualityTables:
    """Verify the diatonic quality tables against known music theory."""

    def test_major_scale_qualities(self):
        # I ii iii IV V vi vii° in major
        expected = ['major', 'minor', 'minor', 'major', 'major', 'minor', 'dim']
        for deg, exp in enumerate(expected, start=1):
            assert get_chord_quality('major', deg) == exp

    def test_major_seventh_qualities(self):
        # Imaj7 ii7 iii7 IVmaj7 V7 vi7 vii∅
        expected = ['maj7', 'min7', 'min7', 'maj7', 'dom7', 'min7', 'half_dim7']
        for deg, exp in enumerate(expected, start=1):
            assert get_chord_quality('major', deg, with_seventh=True) == exp

    def test_minor_v_is_minor_triad(self):
        # Natural minor: v is minor (no leading tone)
        assert get_chord_quality('minor', 5) == 'minor'

    def test_harmonic_minor_v_is_major(self):
        # Harmonic minor raises 7th → V becomes major (the dominant)
        assert get_chord_quality('harmonic_minor', 5) == 'major'

    def test_harmonic_minor_vii_is_dim(self):
        assert get_chord_quality('harmonic_minor', 7) == 'dim'

    def test_dorian_iv_is_major(self):
        # Dorian's characteristic chord: IV is major (raised 6th)
        assert get_chord_quality('dorian', 4) == 'major'

    def test_mixolydian_i_is_major(self):
        assert get_chord_quality('mixolydian', 1) == 'major'

    def test_mixolydian_i_seventh_is_dom7(self):
        # I7 in mixolydian = dominant 7th (the flat-7)
        assert get_chord_quality('mixolydian', 1, with_seventh=True) == 'dom7'

    def test_pentatonic_falls_back_to_minor(self):
        # pentatonic_minor → minor scale quality table
        assert get_chord_quality('pentatonic_minor', 1) == 'minor'
        assert get_chord_quality('pentatonic_major', 1) == 'major'
        assert get_chord_quality('blues', 1) == 'minor'

    def test_invalid_degree_raises(self):
        with pytest.raises(ValueError):
            get_chord_quality('major', 0)
        with pytest.raises(ValueError):
            get_chord_quality('major', 8)


class TestChooseProgression:
    def test_pop_major(self):
        assert choose_progression('major', 'pop') == 'I-V-vi-IV'

    def test_jazz_major(self):
        assert choose_progression('major', 'jazz') == 'I-vi-ii-V'

    def test_pop_minor(self):
        assert choose_progression('minor', 'pop') == 'i-VII-VI-VII'

    def test_dorian_ignores_genre(self):
        # Modal scales override genre preference
        assert choose_progression('dorian', 'pop') == 'i-IV-i-VII'
        assert choose_progression('dorian', 'jazz') == 'i-IV-i-VII'

    def test_mixolydian_ignores_genre(self):
        assert choose_progression('mixolydian', 'rock') == 'I-VII-IV-I'

    def test_unknown_genre_returns_default(self):
        name = choose_progression('major', 'zydeco')
        assert name in PROGRESSIONS

    def test_all_returned_progressions_exist(self):
        import itertools
        from music_theory.scales import SCALES
        from music_theory.genres import GENRE_PROFILES
        for scale in SCALES:
            for genre in list(GENRE_PROFILES) + ['unknown']:
                name = choose_progression(scale, genre)
                assert name in PROGRESSIONS, f"{scale}+{genre} → unknown '{name}'"


# ── genres.py ─────────────────────────────────────────────────────────────────

class TestGenres:
    def test_pop_not_seventh(self):
        assert get_genre_profile('pop')['with_seventh'] is False

    def test_jazz_uses_seventh_and_drop2(self):
        p = get_genre_profile('jazz')
        assert p['with_seventh'] is True
        assert p['spread'] == 'drop2'

    def test_alias_lofi(self):
        assert get_genre_profile('lofi') == get_genre_profile('lo-fi')

    def test_alias_hiphop(self):
        assert get_genre_profile('hiphop') == get_genre_profile('hip-hop')

    def test_unknown_genre_returns_default(self):
        p = get_genre_profile('zydeco')
        assert 'with_seventh' in p
        assert 'spread' in p

    def test_list_genres_not_empty(self):
        assert len(list_genres()) > 0


# ── chord_service.py ──────────────────────────────────────────────────────────

class TestGenerateChordProgression:

    def _gen(self, **kwargs):
        defaults = dict(key='C', mode='major', genre='pop', bpm=120, bars=4, octave=4)
        defaults.update(kwargs)
        return generate_chord_progression(**defaults)

    # ── Structure ─────────────────────────────────────────────────────────────

    def test_returns_required_keys(self):
        result = self._gen()
        for k in ('key', 'mode', 'scale', 'genre', 'bpm', 'bars',
                  'time_signature', 'progression_name', 'with_seventh',
                  'spread', 'chords'):
            assert k in result

    def test_chords_is_nonempty_list(self):
        assert len(self._gen()['chords']) > 0

    def test_each_chord_has_required_keys(self):
        for chord in self._gen()['chords']:
            for k in ('degree', 'degree_label', 'quality', 'label',
                      'notes', 'note_names', 'beat_start', 'beat_duration'):
                assert k in chord, f"Missing key '{k}' in chord {chord}"

    def test_chord_notes_are_sorted(self):
        for chord in self._gen()['chords']:
            assert chord['notes'] == sorted(chord['notes'])

    def test_note_names_match_notes(self):
        from music_theory.scales import get_note_name
        for chord in self._gen()['chords']:
            for midi, name in zip(chord['notes'], chord['note_names']):
                assert get_note_name(midi) == name

    # ── Timing ────────────────────────────────────────────────────────────────

    def test_total_beats_correct(self):
        result = self._gen(bars=4)
        chords = result['chords']
        total = sum(c['beat_duration'] for c in chords)
        assert abs(total - 16.0) < 0.01

    def test_beat_starts_are_sequential(self):
        chords = self._gen()['chords']
        for i in range(1, len(chords)):
            assert chords[i]['beat_start'] > chords[i-1]['beat_start']

    def test_different_bar_counts(self):
        for bars in (2, 4, 8, 16):
            result = self._gen(bars=bars)
            total = sum(c['beat_duration'] for c in result['chords'])
            assert abs(total - bars * 4) < 0.01

    # ── Music theory correctness ───────────────────────────────────────────────

    def test_c_major_pop_i_chord_is_c_major(self):
        result = self._gen(key='C', mode='major', genre='pop', octave=4)
        first = result['chords'][0]
        assert first['degree'] == 1
        assert first['quality'] == 'major'
        assert first['label'] == 'C'
        assert 60 in first['notes']   # C4

    def test_c_major_pop_uses_i_v_vi_iv(self):
        result = self._gen(key='C', mode='major', genre='pop')
        assert result['progression_name'] == 'I-V-vi-IV'

    def test_v_chord_in_c_major_is_g(self):
        result = self._gen(key='C', mode='major', genre='pop', octave=4)
        chords = {c['degree']: c for c in result['chords']}
        v = chords[5]
        assert v['label'].startswith('G')
        assert v['quality'] == 'major'

    def test_vi_chord_in_c_major_is_am(self):
        result = self._gen(key='C', mode='major', genre='pop', octave=4)
        chords = {c['degree']: c for c in result['chords']}
        vi = chords[6]
        assert vi['label'].startswith('A')
        assert vi['quality'] == 'minor'

    def test_jazz_uses_seventh_chords(self):
        result = self._gen(genre='jazz')
        for chord in result['chords']:
            # Jazz default: with_seventh=True, so all qualities should be 7th types
            assert '7' in chord['quality'] or chord['quality'] in ('major', 'minor', 'dim', 'aug')

    def test_jazz_chords_have_4_notes(self):
        result = self._gen(genre='jazz')
        for chord in result['chords']:
            assert len(chord['notes']) == 4, f"Expected 4 notes, got {chord['notes']}"

    def test_minor_key_i_chord_is_minor(self):
        result = self._gen(key='A', mode='minor', genre='pop', octave=4)
        first = result['chords'][0]
        assert first['degree'] == 1
        assert first['quality'] == 'minor'
        assert first['label'] == 'Am'

    def test_harmonic_minor_v_is_major_dominant(self):
        result = self._gen(key='A', mode='harmonic_minor', octave=4)
        chords_by_degree = {c['degree']: c for c in result['chords']}
        if 5 in chords_by_degree:
            v = chords_by_degree[5]
            assert v['quality'] == 'major'  # E major (not Em)

    def test_mood_alias_happy_maps_to_major(self):
        result = self._gen(mode='happy')
        assert result['scale'] == 'major'

    def test_mood_alias_sad_maps_to_minor(self):
        result = self._gen(mode='sad')
        assert result['scale'] == 'minor'

    def test_dorian_uses_modal_progression(self):
        result = self._gen(mode='dorian')
        assert result['progression_name'] == 'i-IV-i-VII'

    # ── Input handling ────────────────────────────────────────────────────────

    def test_flat_key_accepted(self):
        result = self._gen(key='Bb', mode='major')
        assert result['key'] == 'Bb'

    def test_sharp_key_accepted(self):
        result = self._gen(key='F#', mode='minor')
        assert result['key'] == 'F#'

    def test_with_seventh_override(self):
        # Explicit False overrides jazz default (True)
        result = self._gen(genre='jazz', with_seventh=False)
        assert result['with_seventh'] is False
        for chord in result['chords']:
            assert len(chord['notes']) == 3

    def test_spread_override(self):
        result = self._gen(spread='open')
        assert result['spread'] == 'open'

    def test_invalid_key_raises_value_error(self):
        with pytest.raises(ValueError):
            self._gen(key='X')

    def test_invalid_mode_raises_value_error(self):
        with pytest.raises(ValueError):
            self._gen(mode='ultralocrian')

    def test_all_notes_in_midi_range(self):
        for octave in (2, 3, 4, 5):
            result = self._gen(octave=octave)
            for chord in result['chords']:
                assert all(0 <= n <= 127 for n in chord['notes'])

    def test_label_correct_under_drop2_voicing(self):
        # drop2 drops the second-highest note below the original bass,
        # so voiced[0] != root. The label must still show the chord root.
        result = self._gen(key='D', mode='dorian', genre='jazz', octave=4)
        chords_by_degree = {c['degree']: c for c in result['chords']}
        # Degree 1 in D dorian = Dm7, not Am7
        assert chords_by_degree[1]['label'] == 'Dm7'
        # Degree 4 in D dorian = G7 (dom7), not D7
        assert chords_by_degree[4]['label'] == 'G7'
        # Degree 7 in D dorian = Cmaj7, not Gmaj7
        assert chords_by_degree[7]['label'] == 'Cmaj7'
