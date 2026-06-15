"""
tests/test_scales.py
Unit tests for music_theory/scales.py
Run with: python -m pytest tests/test_scales.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from music_theory.scales import (
    SCALES, MOOD_TO_SCALE,
    resolve_mode, get_scale_notes, notes_in_octave,
    get_note_name, get_midi_number, scale_degree,
)


# ── resolve_mode ──────────────────────────────────────────────────────────────

class TestResolveMode:
    def test_direct_scale_name(self):
        assert resolve_mode('major') == 'major'
        assert resolve_mode('dorian') == 'dorian'

    def test_case_insensitive(self):
        assert resolve_mode('Lydian') == 'lydian'
        assert resolve_mode('MAJOR') == 'major'

    def test_mood_alias(self):
        assert resolve_mode('happy') == 'major'
        assert resolve_mode('sad') == 'minor'
        assert resolve_mode('jazzy') == 'dorian'
        assert resolve_mode('soulful') == 'blues'

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown mode/mood"):
            resolve_mode('nonsense')


# ── get_scale_notes ───────────────────────────────────────────────────────────

class TestGetScaleNotes:
    def test_c_major_octave4(self):
        notes = get_scale_notes('C', 'major', octave_min=4, octave_max=4)
        assert notes == [60, 62, 64, 65, 67, 69, 71]  # C D E F G A B

    def test_a_minor_octave4(self):
        notes = get_scale_notes('A', 'minor', octave_min=4, octave_max=4)
        # A4=69, B4=71, C5=72, D5=74, E5=76, F5=77, G5=79
        assert 69 in notes  # A4
        assert 71 in notes  # B4

    def test_g_major_contains_fsharp(self):
        # G major octave window anchored at G3 → G3 A3 B3 C4 D4 E4 F#4
        # F#4 = MIDI 66 lands in the octave-3 window; octave-4 window gives F#5 = 78
        notes_oct3 = get_scale_notes('G', 'major', octave_min=3, octave_max=3)
        assert 66 in notes_oct3    # F#4 is a G-major scale tone
        assert 65 not in notes_oct3  # F natural is not in G major
        notes_oct4 = get_scale_notes('G', 'major', octave_min=4, octave_max=4)
        assert 78 in notes_oct4    # F#5 is the F# in the octave-4 window
        assert 66 not in notes_oct4  # F#4 is below the octave-4 window start (G4=67)

    def test_f_major_contains_bflat(self):
        # Bb4 = MIDI 70
        notes = get_scale_notes('F', 'major', octave_min=4, octave_max=4)
        assert 70 in notes   # Bb4
        assert 71 not in notes  # B natural not in F major

    def test_pentatonic_has_5_notes_per_octave(self):
        notes = get_scale_notes('C', 'pentatonic_major', octave_min=4, octave_max=4)
        assert len(notes) == 5

    def test_blues_has_6_notes_per_octave(self):
        notes = get_scale_notes('C', 'blues', octave_min=4, octave_max=4)
        assert len(notes) == 6

    def test_multi_octave_is_sorted(self):
        notes = get_scale_notes('C', 'major', octave_min=3, octave_max=5)
        assert notes == sorted(notes)

    def test_multi_octave_no_duplicates(self):
        notes = get_scale_notes('G', 'major', octave_min=3, octave_max=5)
        assert len(notes) == len(set(notes))

    def test_enharmonic_key_spelling(self):
        # Bb major and A# major should produce the same notes
        bb = get_scale_notes('Bb', 'major', octave_min=4, octave_max=4)
        asharp = get_scale_notes('A#', 'major', octave_min=4, octave_max=4)
        assert bb == asharp

    def test_mood_alias_accepted(self):
        happy = get_scale_notes('C', 'happy', octave_min=4, octave_max=4)
        major = get_scale_notes('C', 'major', octave_min=4, octave_max=4)
        assert happy == major

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown key"):
            get_scale_notes('X', 'major')

    def test_midi_bounds_respected(self):
        notes = get_scale_notes('B', 'major', octave_min=8, octave_max=9)
        assert all(0 <= n <= 127 for n in notes)


# ── notes_in_octave ───────────────────────────────────────────────────────────

class TestNotesInOctave:
    def test_same_as_get_scale_notes_single_octave(self):
        assert notes_in_octave('D', 'dorian', 4) == \
               get_scale_notes('D', 'dorian', octave_min=4, octave_max=4)


# ── get_note_name ─────────────────────────────────────────────────────────────

class TestGetNoteName:
    def test_middle_c(self):
        assert get_note_name(60) == 'C4'

    def test_a440(self):
        assert get_note_name(69) == 'A4'

    def test_sharps(self):
        assert get_note_name(61) == 'C#4'
        assert get_note_name(66) == 'F#4'

    def test_low_c(self):
        assert get_note_name(0) == 'C-1'

    def test_high_g(self):
        assert get_note_name(127) == 'G9'

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            get_note_name(-1)
        with pytest.raises(ValueError):
            get_note_name(128)


# ── get_midi_number ───────────────────────────────────────────────────────────

class TestGetMidiNumber:
    def test_middle_c(self):
        assert get_midi_number('C4') == 60

    def test_a440(self):
        assert get_midi_number('A4') == 69

    def test_sharp(self):
        assert get_midi_number('F#3') == 54

    def test_flat_resolves(self):
        assert get_midi_number('Bb4') == 70
        assert get_midi_number('Db5') == 73

    def test_lowest_note(self):
        assert get_midi_number('C-1') == 0

    def test_roundtrip(self):
        for midi in [0, 36, 60, 69, 100, 127]:
            assert get_midi_number(get_note_name(midi)) == midi

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            get_midi_number('Z4')
        with pytest.raises(ValueError):
            get_midi_number('C')  # no octave


# ── scale_degree ──────────────────────────────────────────────────────────────

class TestScaleDegree:
    def test_tonic_is_degree_1(self):
        assert scale_degree(60, 'C', 'major') == 1   # C4 in C major
        assert scale_degree(69, 'A', 'minor') == 1   # A4 in A minor

    def test_known_degrees(self):
        # C major: C=1 D=2 E=3 F=4 G=5 A=6 B=7
        expected = {60: 1, 62: 2, 64: 3, 65: 4, 67: 5, 69: 6, 71: 7}
        for midi, degree in expected.items():
            assert scale_degree(midi, 'C', 'major') == degree

    def test_chromatic_note_returns_none(self):
        assert scale_degree(61, 'C', 'major') is None   # C# not in C major
        assert scale_degree(63, 'C', 'major') is None   # D# not in C major

    def test_octave_independent(self):
        # G is degree 5 in C major regardless of octave
        assert scale_degree(55, 'C', 'major') == 5   # G3
        assert scale_degree(67, 'C', 'major') == 5   # G4
        assert scale_degree(79, 'C', 'major') == 5   # G5
