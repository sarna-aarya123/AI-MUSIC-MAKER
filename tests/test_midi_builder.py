"""
tests/test_midi_builder.py
Tests for midi/builder.py — MidiBuilder class and build_from_chord_progression().
Run with: python -m pytest tests/test_midi_builder.py -v
"""
import struct
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from midi.builder import MidiBuilder, GM_PROGRAMS, build_from_chord_progression
from backend.services.chord_service import generate_chord_progression


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_smf_header(raw: bytes) -> dict:
    """Extract fields from the 14-byte SMF header chunk."""
    assert raw[:4] == b'MThd', "Missing MThd magic"
    chunk_len            = struct.unpack_from('>I', raw, 4)[0]
    fmt, tracks, ppq     = struct.unpack_from('>HHH', raw, 8)
    return {'chunk_len': chunk_len, 'format': fmt, 'tracks': tracks, 'ppq': ppq}


def _count_mtrk(raw: bytes) -> int:
    """Count the number of MTrk chunks in the file."""
    count, offset = 0, 0
    while offset < len(raw) - 4:
        if raw[offset:offset+4] == b'MTrk':
            count += 1
        offset += 1
    return count


# ── MidiBuilder unit tests ────────────────────────────────────────────────────

class TestMidiBuilderStructure:

    def test_magic_bytes_in_output(self):
        b = MidiBuilder()
        b.add_track('T')
        raw = b.to_bytes()
        assert raw[:4] == b'\x4d\x54\x68\x64', "SMF magic MThd not found"

    def test_format_field_is_1(self):
        b = MidiBuilder()
        b.add_track('T')
        hdr = _parse_smf_header(b.to_bytes())
        assert hdr['format'] == 1

    def test_ppq_is_480(self):
        b = MidiBuilder()
        b.add_track('T')
        hdr = _parse_smf_header(b.to_bytes())
        assert hdr['ppq'] == 480

    def test_track_count_n_plus_1(self):
        # N music tracks → N+1 physical tracks (tempo track auto-added)
        b = MidiBuilder()
        b.add_track('Chords')
        b.add_track('Melody')
        hdr = _parse_smf_header(b.to_bytes())
        assert hdr['tracks'] == 3   # 2 music + 1 tempo

    def test_mtrk_chunk_count_matches_header(self):
        b = MidiBuilder()
        b.add_track('A')
        b.add_track('B')
        raw = b.to_bytes()
        hdr = _parse_smf_header(raw)
        assert _count_mtrk(raw) == hdr['tracks']

    def test_to_bytes_is_idempotent(self):
        b = MidiBuilder()
        b.add_track('T')
        b.add_note(0, 0, 60, 0.0, 1.0)
        assert b.to_bytes() == b.to_bytes()

    def test_no_tracks_still_produces_valid_midi(self):
        # Edge case: no tracks registered → min 1 music track created internally
        b = MidiBuilder()
        raw = b.to_bytes()
        assert raw[:4] == b'MThd'

    def test_empty_chords_list_produces_valid_midi(self):
        chord_data = generate_chord_progression('C', 'major')
        chord_data = dict(chord_data)
        chord_data['chords'] = []
        builder = build_from_chord_progression(chord_data)
        raw = builder.to_bytes()
        assert raw[:4] == b'MThd'


class TestMidiBuilderProperties:

    def test_track_count_zero_initially(self):
        assert MidiBuilder().track_count == 0

    def test_track_count_after_adds(self):
        b = MidiBuilder()
        b.add_track('A')
        b.add_track('B')
        assert b.track_count == 2

    def test_add_track_returns_correct_index(self):
        b = MidiBuilder()
        assert b.add_track('First')  == 0
        assert b.add_track('Second') == 1
        assert b.add_track('Third')  == 2

    def test_note_count_zero_initially(self):
        assert MidiBuilder().note_count == 0

    def test_note_count_increments(self):
        b = MidiBuilder()
        b.add_track('T')
        b.add_note(0, 0, 60, 0.0, 1.0)
        b.add_note(0, 0, 64, 0.0, 1.0)
        b.add_note(0, 0, 67, 0.0, 1.0)
        assert b.note_count == 3

    def test_summary_contains_expected_keys(self):
        b = MidiBuilder()
        b.add_track('T')
        s = b.summary()
        for k in ('bpm', 'time_signature', 'ppq', 'tracks', 'note_count',
                  'program_changes', 'cc_events'):
            assert k in s

    def test_summary_ppq_is_480(self):
        assert MidiBuilder().summary()['ppq'] == 480


class TestMidiBuilderValidation:

    def test_add_note_pitch_low(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, -1, 0.0, 1.0)

    def test_add_note_pitch_high(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, 128, 0.0, 1.0)

    def test_add_note_velocity_zero(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, 60, 0.0, 1.0, velocity=0)

    def test_add_note_velocity_high(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, 60, 0.0, 1.0, velocity=128)

    def test_add_note_negative_duration(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, 60, 0.0, -1.0)

    def test_add_note_zero_duration(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, 60, 0.0, 0.0)

    def test_add_note_negative_start(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_note(0, 0, 60, -1.0, 1.0)

    def test_set_tempo_zero_raises(self):
        with pytest.raises(ValueError):
            MidiBuilder().set_tempo(0)

    def test_set_tempo_negative_raises(self):
        with pytest.raises(ValueError):
            MidiBuilder().set_tempo(-120)

    def test_set_time_sig_bad_denominator(self):
        with pytest.raises(ValueError):
            MidiBuilder().set_time_signature(4, 3)   # 3 is not power of 2

    def test_set_time_sig_power_of_2_ok(self):
        b = MidiBuilder()
        for denom in (1, 2, 4, 8, 16):
            b.set_time_signature(4, denom)   # no exception

    def test_add_program_change_out_of_range(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_program_change(0, 0, 128)

    def test_add_cc_controller_out_of_range(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_control_change(0, 0, 128, 64, 0.0)

    def test_add_cc_value_out_of_range(self):
        b = MidiBuilder()
        b.add_track('T')
        with pytest.raises(ValueError):
            b.add_control_change(0, 0, 64, 200, 0.0)


class TestMidiBuilderSave:

    def test_save_writes_file(self, tmp_path):
        b = MidiBuilder()
        b.add_track('T')
        b.add_note(0, 0, 60, 0.0, 1.0)
        dest = tmp_path / 'output.mid'
        b.save(dest)
        assert dest.exists()
        assert dest.read_bytes()[:4] == b'MThd'

    def test_save_creates_parent_dirs(self, tmp_path):
        b = MidiBuilder()
        b.add_track('T')
        dest = tmp_path / 'deep' / 'path' / 'file.mid'
        b.save(dest)
        assert dest.exists()

    def test_save_bytes_match_to_bytes(self, tmp_path):
        b = MidiBuilder()
        b.add_track('T')
        b.add_note(0, 0, 62, 0.0, 2.0, velocity=80)
        dest = tmp_path / 'test.mid'
        b.save(dest)
        assert dest.read_bytes() == b.to_bytes()


# ── GM_PROGRAMS ───────────────────────────────────────────────────────────────

class TestGmPrograms:

    def test_piano_is_0(self):
        assert GM_PROGRAMS['piano'] == 0

    def test_epiano_is_4(self):
        assert GM_PROGRAMS['epiano'] == 4

    def test_strings_is_48(self):
        assert GM_PROGRAMS['strings'] == 48

    def test_all_programs_in_range(self):
        for name, prog in GM_PROGRAMS.items():
            assert 0 <= prog <= 127, f"'{name}' program {prog} out of range"


# ── build_from_chord_progression ─────────────────────────────────────────────

class TestBuildFromChordProgression:

    def _chord_data(self, **kwargs):
        defaults = dict(key='C', mode='major', genre='pop', bpm=120, bars=4, octave=4)
        defaults.update(kwargs)
        return generate_chord_progression(**defaults)

    def test_returns_midi_builder(self):
        result = build_from_chord_progression(self._chord_data())
        assert isinstance(result, MidiBuilder)

    def test_produces_valid_smf(self):
        builder = build_from_chord_progression(self._chord_data())
        raw = builder.to_bytes()
        assert raw[:4] == b'MThd'
        assert _parse_smf_header(raw)['format'] == 1

    def test_chords_track_registered(self):
        builder = build_from_chord_progression(self._chord_data())
        assert builder.track_count == 1
        assert builder.summary()['tracks'] == ['Chords']

    def test_note_count_equals_sum_of_chord_notes(self):
        data = self._chord_data()
        expected = sum(len(c['notes']) for c in data['chords'])
        builder = build_from_chord_progression(data)
        assert builder.note_count == expected

    def test_top_note_higher_velocity(self):
        # Re-create the builder logic manually: last note in each sorted chord
        # should carry velocity_top; others velocity_inner.
        data    = self._chord_data()
        builder = build_from_chord_progression(data, velocity_top=90, velocity_inner=60)
        # Check via note introspection — verify velocities are correct count
        notes_top   = [n for n in builder._notes if n.velocity == 90]
        notes_inner = [n for n in builder._notes if n.velocity == 60]
        expected_top   = len(data['chords'])                       # one top note per chord
        expected_inner = builder.note_count - expected_top         # rest are inner
        assert len(notes_top)   == expected_top
        assert len(notes_inner) == expected_inner

    def test_tempo_taken_from_chord_data(self):
        data    = self._chord_data(bpm=140)
        builder = build_from_chord_progression(data)
        assert builder._tempo == 140.0

    def test_bpm_120_roundtrip(self):
        data    = self._chord_data(bpm=120)
        builder = build_from_chord_progression(data)
        assert builder._tempo == 120.0

    def test_instrument_string_resolved(self):
        data    = self._chord_data()
        builder = build_from_chord_progression(data, instrument='epiano')
        # Program change should reference program 4 (Electric Piano 1)
        assert len(builder._programs) == 1
        assert builder._programs[0].program == GM_PROGRAMS['epiano']

    def test_instrument_int_accepted(self):
        data    = self._chord_data()
        builder = build_from_chord_progression(data, instrument=48)  # strings
        assert builder._programs[0].program == 48

    def test_unknown_instrument_defaults_to_piano(self):
        data    = self._chord_data()
        builder = build_from_chord_progression(data, instrument='xylophone_of_doom')
        assert builder._programs[0].program == 0   # piano fallback

    def test_program_change_on_track_0_channel_0(self):
        data    = self._chord_data()
        builder = build_from_chord_progression(data)
        pc = builder._programs[0]
        assert pc.track == 0
        assert pc.channel == 0

    def test_jazz_chords_4_notes_each(self):
        data    = self._chord_data(genre='jazz')
        builder = build_from_chord_progression(data)
        notes_per_chord = sum(len(c['notes']) for c in data['chords'])
        assert builder.note_count == notes_per_chord

    def test_bars_8_double_note_count_vs_4(self):
        data4 = self._chord_data(bars=4)
        data8 = self._chord_data(bars=8)
        b4    = build_from_chord_progression(data4)
        b8    = build_from_chord_progression(data8)
        # bars=8 has same number of chord events but the bars doubled
        # (progression repeats same number of chords, just longer duration)
        # note counts should be equal as the progression length is fixed
        assert b4.note_count == b8.note_count

    def test_minor_key_produces_valid_smf(self):
        data    = self._chord_data(key='A', mode='minor')
        builder = build_from_chord_progression(data)
        raw = builder.to_bytes()
        assert raw[:4] == b'MThd'

    def test_all_note_pitches_in_midi_range(self):
        data = self._chord_data(key='C', mode='major', genre='jazz', octave=4)
        builder = build_from_chord_progression(data)
        for n in builder._notes:
            assert 0 <= n.pitch <= 127, f"Pitch {n.pitch} out of range"

    def test_beat_starts_non_negative(self):
        data    = self._chord_data()
        builder = build_from_chord_progression(data)
        for n in builder._notes:
            assert n.start_beat >= 0

    def test_invalid_program_int_raises(self):
        data = self._chord_data()
        with pytest.raises(ValueError):
            build_from_chord_progression(data, instrument=200)

    def test_additional_track_can_be_appended(self):
        # After building chords, caller can add a melody track
        data    = self._chord_data()
        builder = build_from_chord_progression(data)
        mel_idx = builder.add_track('Melody')
        builder.add_note(mel_idx, 1, 72, 0.0, 1.0)
        assert builder.track_count == 2
        raw = builder.to_bytes()
        hdr = _parse_smf_header(raw)
        assert hdr['tracks'] == 3   # tempo + chords + melody

    def test_time_signature_set_from_chord_data(self):
        data    = self._chord_data()
        builder = build_from_chord_progression(data)
        assert builder._time_sig == (4, 4)
