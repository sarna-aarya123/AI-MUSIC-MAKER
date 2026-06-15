"""
tests/test_chords.py
Unit tests for music_theory/chords.py
Run with: python -m pytest tests/test_chords.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from music_theory.chords import (
    CHORD_QUALITIES, CHORD_SYMBOLS,
    build_chord, build_triad, build_seventh,
    diatonic_chord, invert, voice_chord,
    chord_name, pitch_class_name,
)
from music_theory.scales import notes_in_octave


# ── pitch_class_name ──────────────────────────────────────────────────────────

class TestPitchClassName:
    def test_c(self):
        assert pitch_class_name(60) == 'C'

    def test_fsharp(self):
        assert pitch_class_name(66) == 'F#'

    def test_octave_independent(self):
        assert pitch_class_name(48) == pitch_class_name(60) == pitch_class_name(72)  # all C


# ── build_chord ───────────────────────────────────────────────────────────────

class TestBuildChord:
    def test_c_major_triad(self):
        assert build_chord(60, 'major') == [60, 64, 67]

    def test_c_minor_triad(self):
        assert build_chord(60, 'minor') == [60, 63, 67]

    def test_g_dominant7(self):
        # G4=67 + intervals [0,4,7,10] = [67,71,74,77]
        assert build_chord(67, 'dom7') == [67, 71, 74, 77]

    def test_d_minor7(self):
        # D4=62 + [0,3,7,10] = [62,65,69,72]
        assert build_chord(62, 'min7') == [62, 65, 69, 72]

    def test_b_diminished(self):
        # B4=71 + [0,3,6] = [71,74,77]
        assert build_chord(71, 'dim') == [71, 74, 77]

    def test_root_is_first_note(self):
        for quality in CHORD_QUALITIES:
            notes = build_chord(60, quality)
            assert notes[0] == 60

    def test_notes_are_ascending(self):
        for quality in CHORD_QUALITIES:
            notes = build_chord(60, quality)
            assert notes == sorted(notes)

    def test_unknown_quality_raises(self):
        with pytest.raises(ValueError, match="Unknown chord quality"):
            build_chord(60, 'superlocrian')


# ── build_triad / build_seventh ───────────────────────────────────────────────

class TestBuildTriadAndSeventh:
    def test_triad_has_3_notes(self):
        assert len(build_triad(60, 'major')) == 3
        assert len(build_triad(60, 'maj7')) == 3   # strips 4th note

    def test_seventh_has_4_notes(self):
        assert len(build_seventh(60, 'maj7')) == 4
        assert len(build_seventh(60, 'dom7')) == 4

    def test_seventh_falls_back_to_triad_if_short(self):
        # 'major' only has 3 intervals, build_seventh should still return 3
        assert len(build_seventh(60, 'major')) == 3

    def test_triad_matches_first_three_of_chord(self):
        assert build_triad(60, 'maj7') == build_chord(60, 'maj7')[:3]


# ── diatonic_chord ────────────────────────────────────────────────────────────

class TestDiatonicChord:
    @pytest.fixture
    def c_major(self):
        return notes_in_octave('C', 'major', 4)   # [60,62,64,65,67,69,71]

    def test_degree_1_is_major(self, c_major):
        chord = diatonic_chord(c_major, 1)
        assert chord == [60, 64, 67]   # C E G

    def test_degree_2_is_minor(self, c_major):
        chord = diatonic_chord(c_major, 2)
        assert chord == [62, 65, 69]   # D F A

    def test_degree_5_is_major(self, c_major):
        chord = diatonic_chord(c_major, 5)
        assert chord == [67, 71, 74]   # G B D5

    def test_degree_7_is_diminished(self, c_major):
        chord = diatonic_chord(c_major, 7)
        assert chord == [71, 74, 77]   # B D5 F5

    def test_with_seventh_degree1(self, c_major):
        chord = diatonic_chord(c_major, 1, with_seventh=True)
        assert chord == [60, 64, 67, 71]   # Cmaj7

    def test_with_seventh_degree2(self, c_major):
        chord = diatonic_chord(c_major, 2, with_seventh=True)
        assert chord == [62, 65, 69, 72]   # Dm7

    def test_with_seventh_degree5(self, c_major):
        chord = diatonic_chord(c_major, 5, with_seventh=True)
        assert chord == [67, 71, 74, 77]   # G7

    def test_high_degree_wraps_to_next_octave(self, c_major):
        # Degree 6 wraps: A4, C5, E5
        chord = diatonic_chord(c_major, 6)
        assert chord == [69, 72, 76]

    def test_degree_7_wrap_seventh(self, c_major):
        # B4, D5, F5, A5
        chord = diatonic_chord(c_major, 7, with_seventh=True)
        assert chord == [71, 74, 77, 81]

    def test_wrong_scale_length_raises(self):
        penta = notes_in_octave('C', 'pentatonic_major', 4)
        with pytest.raises(ValueError, match="7-note"):
            diatonic_chord(penta, 1)

    def test_invalid_degree_raises(self, c_major):
        with pytest.raises(ValueError, match="degree must be 1-7"):
            diatonic_chord(c_major, 0)
        with pytest.raises(ValueError, match="degree must be 1-7"):
            diatonic_chord(c_major, 8)

    def test_all_7_degrees_return_3_notes(self, c_major):
        for deg in range(1, 8):
            assert len(diatonic_chord(c_major, deg)) == 3

    def test_all_7_degrees_return_4_notes_with_seventh(self, c_major):
        for deg in range(1, 8):
            assert len(diatonic_chord(c_major, deg, with_seventh=True)) == 4


# ── invert ────────────────────────────────────────────────────────────────────

class TestInvert:
    def test_root_position_unchanged(self):
        assert invert([60, 64, 67], 0) == [60, 64, 67]

    def test_first_inversion(self):
        assert invert([60, 64, 67], 1) == [64, 67, 72]   # E G C5

    def test_second_inversion(self):
        assert invert([60, 64, 67], 2) == [67, 72, 76]   # G C5 E5

    def test_third_inversion_four_note(self):
        # Cmaj7: C4 E4 G4 B4 → 3rd inv: B4 C5 E5 G5
        assert invert([60, 64, 67, 71], 3) == [71, 72, 76, 79]

    def test_inversion_wraps_modulo(self):
        # Inversion 3 on a triad is same as inversion 0
        assert invert([60, 64, 67], 3) == invert([60, 64, 67], 0)

    def test_empty_list(self):
        assert invert([], 1) == []


# ── voice_chord ───────────────────────────────────────────────────────────────

class TestVoiceChord:
    def test_close_root_position(self):
        result = voice_chord([60, 64, 67], inversion=0, spread='close')
        assert result == sorted(result)           # ascending
        assert max(result) - min(result) <= 12    # within one octave

    def test_open_wider_than_close(self):
        close = voice_chord([60, 64, 67, 71], spread='close')
        open_ = voice_chord([60, 64, 67, 71], spread='open')
        assert max(open_) - min(open_) > max(close) - min(close)

    def test_drop2_second_highest_is_lower(self):
        close = voice_chord([60, 64, 67, 71], spread='close')
        drop2 = voice_chord([60, 64, 67, 71], spread='drop2')
        # Drop-2 should span a wider range
        assert max(drop2) - min(drop2) > max(close) - min(close)

    def test_drop2_falls_back_for_triads(self):
        # No crash, returns a valid sorted list
        result = voice_chord([60, 64, 67], spread='drop2')
        assert result == sorted(result)

    def test_inversion_changes_bass(self):
        root = voice_chord([60, 64, 67], inversion=0, spread='close')
        first = voice_chord([60, 64, 67], inversion=1, spread='close')
        assert min(root) != min(first)

    def test_all_notes_present_as_pitch_classes(self):
        original_pcs = {n % 12 for n in [60, 64, 67, 71]}
        for spread in ('close', 'open', 'drop2'):
            result = voice_chord([60, 64, 67, 71], spread=spread)
            result_pcs = {n % 12 for n in result}
            assert result_pcs == original_pcs

    def test_invalid_spread_raises(self):
        with pytest.raises(ValueError, match="spread must be one of"):
            voice_chord([60, 64, 67], spread='wide')


# ── chord_name ────────────────────────────────────────────────────────────────

class TestChordName:
    def test_major(self):
        assert chord_name(60, 'major') == 'C'

    def test_minor(self):
        assert chord_name(62, 'minor') == 'Dm'

    def test_dom7(self):
        assert chord_name(67, 'dom7') == 'G7'

    def test_maj7(self):
        assert chord_name(60, 'maj7') == 'Cmaj7'

    def test_sharp_root(self):
        assert chord_name(61, 'minor') == 'C#m'

    def test_unknown_quality_raises(self):
        with pytest.raises(ValueError):
            chord_name(60, 'unknown')

    def test_all_qualities_have_symbol(self):
        for q in CHORD_QUALITIES:
            name = chord_name(60, q)
            assert name.startswith('C')  # root is C for all
