"""
tests/test_composition_service.py

Unit + integration tests for:
  backend/services/composition_service.py  (compose)
  midi/melody_writer.py                    (write_melody)
"""

from __future__ import annotations

import pytest

from backend.services.chord_service import generate_chord_progression
from backend.services.composition_service import compose
from midi.builder import MidiBuilder
from midi.melody_writer import MELODY_CHANNEL, write_melody
from music_theory.rhythm import PPQ


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def chord_data():
    return generate_chord_progression('C', 'major', genre='pop', bpm=120, bars=4)


@pytest.fixture(scope='module')
def composition(chord_data):
    return compose(chord_data, seed=42)


@pytest.fixture(scope='module')
def no_drums(chord_data):
    return compose(chord_data, seed=0, include_drums=False)


@pytest.fixture(scope='module')
def no_melody(chord_data):
    return compose(chord_data, seed=0, include_melody=False)


@pytest.fixture(scope='module')
def chords_only(chord_data):
    return compose(chord_data, seed=0, include_melody=False, include_drums=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Top-level output structure
# ═══════════════════════════════════════════════════════════════════════════════

def test_output_has_all_required_keys(composition):
    required = {
        'key', 'mode', 'scale', 'genre', 'bpm', 'bars',
        'time_signature', 'ppq', 'total_beats',
        'parts', 'tracks',
        'chord_data', 'melody_data', 'drum_data',
        'midi_bytes', 'summary',
    }
    assert required <= composition.keys()

def test_ppq_is_480(composition):
    assert composition['ppq'] == 480

def test_ppq_matches_rhythm_constant(composition):
    assert composition['ppq'] == PPQ

def test_total_beats_is_bars_times_4(composition, chord_data):
    assert composition['total_beats'] == chord_data['bars'] * 4.0

def test_total_beats_type(composition):
    assert isinstance(composition['total_beats'], float)

def test_default_parts_are_all_three(composition):
    assert set(composition['parts']) == {'chords', 'melody', 'drums'}

def test_parts_order(composition):
    assert composition['parts'] == ['chords', 'melody', 'drums']

def test_tracks_keys_match_parts(composition):
    assert set(composition['tracks'].keys()) == set(composition['parts'])

def test_chords_track_is_zero(composition):
    assert composition['tracks']['chords'] == 0

def test_melody_track_is_one(composition):
    assert composition['tracks']['melody'] == 1

def test_drums_track_is_two(composition):
    assert composition['tracks']['drums'] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata passthrough from chord_data
# ═══════════════════════════════════════════════════════════════════════════════

def test_key_passthrough(composition, chord_data):
    assert composition['key'] == chord_data['key']

def test_mode_passthrough(composition, chord_data):
    assert composition['mode'] == chord_data['mode']

def test_scale_passthrough(composition, chord_data):
    assert composition['scale'] == chord_data['scale']

def test_genre_passthrough(composition, chord_data):
    assert composition['genre'] == chord_data['genre']

def test_bpm_passthrough(composition, chord_data):
    assert composition['bpm'] == chord_data['bpm']

def test_bars_passthrough(composition, chord_data):
    assert composition['bars'] == chord_data['bars']

def test_time_signature_passthrough(composition, chord_data):
    assert composition['time_signature'] == chord_data['time_signature']

def test_chord_data_echoed_intact(composition, chord_data):
    assert composition['chord_data'] is chord_data


# ═══════════════════════════════════════════════════════════════════════════════
# Constituent part data
# ═══════════════════════════════════════════════════════════════════════════════

def test_melody_data_is_dict(composition):
    assert isinstance(composition['melody_data'], dict)

def test_melody_data_has_notes(composition):
    assert 'notes' in composition['melody_data']
    assert len(composition['melody_data']['notes']) > 0

def test_drum_data_is_dict(composition):
    assert isinstance(composition['drum_data'], dict)

def test_drum_data_has_events(composition):
    assert 'events' in composition['drum_data']
    assert len(composition['drum_data']['events']) > 0

def test_melody_data_genre_matches(composition):
    assert composition['melody_data']['genre'] == composition['genre']

def test_drum_data_genre_matches(composition):
    assert composition['drum_data']['genre'] == composition['genre']

def test_drum_data_bars_matches(composition):
    assert composition['drum_data']['bars'] == composition['bars']


# ═══════════════════════════════════════════════════════════════════════════════
# Beat grid alignment
# ═══════════════════════════════════════════════════════════════════════════════

def test_melody_beats_within_total(composition):
    total = composition['total_beats']
    for note in composition['melody_data']['notes']:
        assert note['beat'] < total, f"Melody note at beat {note['beat']} >= {total}"

def test_drum_beats_within_total(composition):
    total = composition['total_beats']
    for ev in composition['drum_data']['events']:
        assert ev['beat'] < total, f"Drum event at beat {ev['beat']} >= {total}"

def test_chord_beats_within_total(composition):
    total = composition['total_beats']
    for chord in composition['chord_data']['chords']:
        assert chord['beat_start'] < total


# ═══════════════════════════════════════════════════════════════════════════════
# MIDI bytes
# ═══════════════════════════════════════════════════════════════════════════════

def test_midi_bytes_type(composition):
    assert isinstance(composition['midi_bytes'], bytes)

def test_midi_bytes_starts_with_mthd(composition):
    assert composition['midi_bytes'][:4] == bytes.fromhex('4d546864')

def test_midi_bytes_nonempty(composition):
    assert len(composition['midi_bytes']) > 100

def test_channel_9_note_on_in_midi(composition):
    # Status byte 0x99 = note-on on channel 9 (General MIDI drums)
    assert b'\x99' in composition['midi_bytes']


# ═══════════════════════════════════════════════════════════════════════════════
# MIDI summary
# ═══════════════════════════════════════════════════════════════════════════════

def test_summary_is_dict(composition):
    assert isinstance(composition['summary'], dict)

def test_summary_track_count_three(composition):
    assert len(composition['summary']['tracks']) == 3

def test_summary_note_count_positive(composition):
    assert composition['summary']['note_count'] > 0

def test_summary_note_count_equals_all_parts(composition):
    chord_notes  = sum(len(c['notes']) for c in composition['chord_data']['chords'])
    melody_notes = len(composition['melody_data']['notes'])
    drum_events  = len(composition['drum_data']['events'])
    expected = chord_notes + melody_notes + drum_events
    assert composition['summary']['note_count'] == expected


# ═══════════════════════════════════════════════════════════════════════════════
# Optional parts — include_melody=False
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_melody_parts_list(no_melody):
    assert 'melody' not in no_melody['parts']

def test_no_melody_data_is_none(chord_data):
    result = compose(chord_data, seed=0, include_melody=False)
    assert result['melody_data'] is None

def test_no_melody_track_count_two(chord_data):
    result = compose(chord_data, seed=0, include_melody=False)
    assert len(result['summary']['tracks']) == 2

def test_no_melody_tracks_dict(chord_data):
    result = compose(chord_data, seed=0, include_melody=False)
    assert 'melody' not in result['tracks']
    assert 'chords' in result['tracks']
    assert 'drums'  in result['tracks']


# ═══════════════════════════════════════════════════════════════════════════════
# Optional parts — include_drums=False
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_drums_parts_list(no_drums):
    assert 'drums' not in no_drums['parts']

def test_no_drums_data_is_none(no_drums):
    assert no_drums['drum_data'] is None

def test_no_drums_track_count_two(no_drums):
    assert len(no_drums['summary']['tracks']) == 2

def test_no_drums_no_channel_9(no_drums):
    # Without drums there should be no note-on on channel 9
    assert b'\x99' not in no_drums['midi_bytes']

def test_no_drums_tracks_dict(no_drums):
    assert 'drums'  not in no_drums['tracks']
    assert 'chords' in no_drums['tracks']
    assert 'melody' in no_drums['tracks']


# ═══════════════════════════════════════════════════════════════════════════════
# Optional parts — chords only
# ═══════════════════════════════════════════════════════════════════════════════

def test_chords_only_parts(chords_only):
    assert chords_only['parts'] == ['chords']

def test_chords_only_track_count_one(chords_only):
    assert len(chords_only['summary']['tracks']) == 1

def test_chords_only_melody_none(chords_only):
    assert chords_only['melody_data'] is None

def test_chords_only_drums_none(chords_only):
    assert chords_only['drum_data'] is None

def test_chords_only_valid_midi(chords_only):
    assert chords_only['midi_bytes'][:4] == bytes.fromhex('4d546864')


# ═══════════════════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════════════════

def test_same_seed_produces_identical_midi(chord_data):
    r1 = compose(chord_data, seed=99)
    r2 = compose(chord_data, seed=99)
    assert r1['midi_bytes'] == r2['midi_bytes']

def test_same_seed_produces_identical_melody_notes(chord_data):
    r1 = compose(chord_data, seed=7)
    r2 = compose(chord_data, seed=7)
    assert r1['melody_data']['notes'] == r2['melody_data']['notes']

def test_same_seed_produces_identical_drum_events(chord_data):
    r1 = compose(chord_data, seed=7)
    r2 = compose(chord_data, seed=7)
    assert r1['drum_data']['events'] == r2['drum_data']['events']

def test_different_seeds_produce_different_melody(chord_data):
    r1 = compose(chord_data, seed=1)
    r2 = compose(chord_data, seed=2)
    v1 = [n['velocity'] for n in r1['melody_data']['notes']]
    v2 = [n['velocity'] for n in r2['melody_data']['notes']]
    assert v1 != v2

def test_different_seeds_produce_different_drums(chord_data):
    r1 = compose(chord_data, seed=1)
    r2 = compose(chord_data, seed=2)
    b1 = [e['beat'] for e in r1['drum_data']['events']]
    b2 = [e['beat'] for e in r2['drum_data']['events']]
    assert b1 != b2


# ═══════════════════════════════════════════════════════════════════════════════
# Genre parametrisation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_all_genres_produce_valid_output(genre):
    cd = generate_chord_progression('D', 'minor', genre=genre, bpm=100, bars=4)
    result = compose(cd, seed=0)
    assert result['midi_bytes'][:4] == bytes.fromhex('4d546864')
    assert result['summary']['note_count'] > 0
    assert result['genre'] == cd['genre']

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_all_genres_beat_alignment(genre):
    cd = generate_chord_progression('G', 'major', genre=genre, bpm=120, bars=4)
    result = compose(cd, seed=0)
    total = result['total_beats']
    for note in result['melody_data']['notes']:
        assert note['beat'] < total
    for ev in result['drum_data']['events']:
        assert ev['beat'] < total


# ═══════════════════════════════════════════════════════════════════════════════
# Instruments
# ═══════════════════════════════════════════════════════════════════════════════

def test_chord_instrument_string(chord_data):
    result = compose(chord_data, chord_instrument='epiano', seed=0)
    assert result['midi_bytes'][:4] == bytes.fromhex('4d546864')

def test_melody_instrument_string(chord_data):
    result = compose(chord_data, melody_instrument='flute', seed=0)
    assert result['midi_bytes'][:4] == bytes.fromhex('4d546864')

def test_chord_instrument_int(chord_data):
    result = compose(chord_data, chord_instrument=48, seed=0)   # 48 = strings
    assert result['midi_bytes'][:4] == bytes.fromhex('4d546864')


# ═══════════════════════════════════════════════════════════════════════════════
# Melody density
# ═══════════════════════════════════════════════════════════════════════════════

def test_density_1_more_notes_than_density_0(chord_data):
    full  = compose(chord_data, melody_density=1.0, seed=42, include_drums=False)
    spare = compose(chord_data, melody_density=0.0, seed=42, include_drums=False)
    assert (len(full['melody_data']['notes'])
            >= len(spare['melody_data']['notes']))


# ═══════════════════════════════════════════════════════════════════════════════
# Drum variation bars
# ═══════════════════════════════════════════════════════════════════════════════

def test_variation_bars_zero_no_fill(chord_data):
    # Pop fill adds snare at 15.25; with variation_bars=0 it should be absent
    result = compose(chord_data, seed=42, drum_variation_bars=0, include_melody=False)
    snare_beats = {ev['beat'] for ev in result['drum_data']['events']
                   if ev['drum_type'] == 'snare'}
    assert 15.25 not in snare_beats

def test_variation_bars_4_adds_fill(chord_data):
    result = compose(chord_data, seed=42, drum_variation_bars=4, include_melody=False)
    snare_beats = {ev['beat'] for ev in result['drum_data']['events']
                   if ev['drum_type'] == 'snare'}
    assert 15.25 in snare_beats


# ═══════════════════════════════════════════════════════════════════════════════
# midi/melody_writer.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_melody_channel_constant():
    assert MELODY_CHANNEL == 1

def test_write_melody_returns_int(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    idx = write_melody(b, md)
    assert isinstance(idx, int)

def test_write_melody_track_index_is_zero_first(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    idx = write_melody(b, md)
    assert idx == 0

def test_write_melody_note_count_matches(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    write_melody(b, md)
    assert b.note_count == len(md['notes'])

def test_write_melody_valid_midi(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    write_melody(b, md)
    assert b.to_bytes()[:4] == bytes.fromhex('4d546864')

def test_write_melody_instrument_string(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    write_melody(b, md, instrument='flute')
    assert b.to_bytes()[:4] == bytes.fromhex('4d546864')

def test_write_melody_instrument_int(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    write_melody(b, md, instrument=73)   # 73 = flute GM number
    assert b.to_bytes()[:4] == bytes.fromhex('4d546864')

def test_write_melody_empty_notes():
    b  = MidiBuilder()
    b.set_tempo(120)
    idx = write_melody(b, {'notes': []})
    assert isinstance(idx, int)
    assert b.note_count == 0

def test_write_melody_custom_channel(chord_data):
    from backend.services.melody_service import generate_melody
    md = generate_melody(chord_data, seed=0)
    b  = MidiBuilder()
    b.set_tempo(120)
    write_melody(b, md, channel=2)
    assert b.to_bytes()[:4] == bytes.fromhex('4d546864')
