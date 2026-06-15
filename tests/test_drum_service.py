"""
tests/test_drum_service.py

Unit tests for:
  backend/services/drum_service.py  — GM mapping, event generation, fills
  midi/drum_writer.py               — MidiBuilder integration on channel 9
"""

from __future__ import annotations

import pytest

from backend.services.drum_service import (
    GM_DRUM_MAP,
    _FILL_TEMPLATES,
    _apply_fill,
    _make_event,
    generate_drums,
)
from midi.builder import MidiBuilder
from midi.drum_writer import DRUM_CHANNEL, write_drums
from music_theory.rhythm import RhythmEvent


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def pop_4bar():
    return generate_drums('pop', bars=4, bpm=120, seed=0)


@pytest.fixture
def pop_4bar_no_fill():
    return generate_drums('pop', bars=4, bpm=120, seed=0, variation_bars=0)


@pytest.fixture
def builder_with_drums(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    write_drums(b, pop_4bar)
    return b


# ═══════════════════════════════════════════════════════════════════════════════
# GM_DRUM_MAP constants
# ═══════════════════════════════════════════════════════════════════════════════

def test_gm_kick():
    assert GM_DRUM_MAP['kick'] == 36

def test_gm_snare():
    assert GM_DRUM_MAP['snare'] == 38

def test_gm_hihat():
    assert GM_DRUM_MAP['hihat'] == 42

def test_gm_open_hat():
    assert GM_DRUM_MAP['open_hat'] == 46

def test_gm_ride():
    assert GM_DRUM_MAP['ride'] == 51

def test_gm_crash():
    assert GM_DRUM_MAP['crash'] == 49

def test_gm_rim():
    assert GM_DRUM_MAP['rim'] == 37

def test_gm_drum_map_all_in_gm_range():
    for name, note in GM_DRUM_MAP.items():
        assert 35 <= note <= 81, f"{name}: {note} outside GM drum range"


# ═══════════════════════════════════════════════════════════════════════════════
# Output structure
# ═══════════════════════════════════════════════════════════════════════════════

def test_output_top_level_keys(pop_4bar):
    assert {'genre', 'bpm', 'bars', 'events'} <= pop_4bar.keys()

def test_output_genre(pop_4bar):
    assert pop_4bar['genre'] == 'pop'

def test_output_bpm(pop_4bar):
    assert pop_4bar['bpm'] == 120

def test_output_bars(pop_4bar):
    assert pop_4bar['bars'] == 4

def test_output_events_is_list(pop_4bar):
    assert isinstance(pop_4bar['events'], list)

def test_output_events_nonempty(pop_4bar):
    assert len(pop_4bar['events']) > 0

def test_event_keys(pop_4bar):
    required = {'beat', 'duration', 'velocity', 'drum_type', 'pitch', 'accent'}
    for ev in pop_4bar['events']:
        assert required <= ev.keys(), f"Event missing keys: {required - ev.keys()}"


# ═══════════════════════════════════════════════════════════════════════════════
# MIDI validity
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_velocity_range(genre):
    data = generate_drums(genre, bars=4, seed=7)
    for ev in data['events']:
        assert 1 <= ev['velocity'] <= 127, f"velocity {ev['velocity']} out of range"

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_beats_nonnegative(genre):
    data = generate_drums(genre, bars=4, seed=7)
    for ev in data['events']:
        assert ev['beat'] >= 0, f"negative beat {ev['beat']}"

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_duration_positive(genre):
    data = generate_drums(genre, bars=4, seed=7)
    for ev in data['events']:
        assert ev['duration'] > 0, f"non-positive duration {ev['duration']}"

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_pitch_in_gm_drum_range(genre):
    data = generate_drums(genre, bars=4, seed=7)
    for ev in data['events']:
        assert 35 <= ev['pitch'] <= 81, f"pitch {ev['pitch']} outside GM drum range"

@pytest.mark.parametrize('genre', ['pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'])
def test_accent_valid(genre):
    valid = {'strong', 'medium', 'weak', 'ghost'}
    data = generate_drums(genre, bars=4, seed=7)
    for ev in data['events']:
        assert ev['accent'] in valid, f"unknown accent {ev['accent']!r}"

def test_events_sorted_by_beat(pop_4bar):
    beats = [ev['beat'] for ev in pop_4bar['events']]
    assert beats == sorted(beats)

def test_max_beat_within_total_length(pop_4bar):
    total_beats = 4 * 4  # bars=4, beats_per_bar=4
    for ev in pop_4bar['events']:
        assert ev['beat'] < total_beats, f"beat {ev['beat']} >= {total_beats}"


# ═══════════════════════════════════════════════════════════════════════════════
# GM pitch per drum_type
# ═══════════════════════════════════════════════════════════════════════════════

def test_kick_events_have_pitch_36(pop_4bar):
    kicks = [ev for ev in pop_4bar['events'] if ev['drum_type'] == 'kick']
    assert len(kicks) > 0
    for ev in kicks:
        assert ev['pitch'] == 36

def test_snare_events_have_pitch_38(pop_4bar):
    snares = [ev for ev in pop_4bar['events'] if ev['drum_type'] == 'snare']
    assert len(snares) > 0
    for ev in snares:
        assert ev['pitch'] == 38

def test_hihat_events_have_pitch_42(pop_4bar):
    hats = [ev for ev in pop_4bar['events'] if ev['drum_type'] == 'hihat']
    assert len(hats) > 0
    for ev in hats:
        assert ev['pitch'] == 42

def test_ride_events_have_pitch_51():
    data = generate_drums('jazz', bars=2, seed=0)
    rides = [ev for ev in data['events'] if ev['drum_type'] == 'ride']
    assert len(rides) > 0
    for ev in rides:
        assert ev['pitch'] == 51

def test_open_hat_events_have_pitch_46():
    data = generate_drums('edm', bars=2, seed=0)
    ohats = [ev for ev in data['events'] if ev['drum_type'] == 'open_hat']
    assert len(ohats) > 0
    for ev in ohats:
        assert ev['pitch'] == 46


# ═══════════════════════════════════════════════════════════════════════════════
# Genre-specific voice content
# ═══════════════════════════════════════════════════════════════════════════════

def test_pop_has_kick_snare_hihat():
    data = generate_drums('pop', bars=2, seed=0)
    types = {ev['drum_type'] for ev in data['events']}
    assert 'kick'  in types
    assert 'snare' in types
    assert 'hihat' in types

def test_hip_hop_has_ghost_snares():
    data = generate_drums('hip-hop', bars=4, seed=0)
    ghosts = [ev for ev in data['events'] if ev['drum_type'] == 'snare' and ev['accent'] == 'ghost']
    assert len(ghosts) > 0

def test_jazz_has_ride_not_hihat_grid():
    data = generate_drums('jazz', bars=4, seed=0)
    types = {ev['drum_type'] for ev in data['events']}
    assert 'ride' in types
    # Jazz uses hihat as foot (only 2 hits per bar, not a 8th-note grid)
    hihat_beats = sorted(ev['beat'] for ev in data['events'] if ev['drum_type'] == 'hihat')
    assert len(hihat_beats) <= 2 * 4   # at most 2 per bar

def test_edm_has_open_hat_and_four_on_floor():
    data = generate_drums('edm', bars=4, seed=0)
    types = {ev['drum_type'] for ev in data['events']}
    assert 'open_hat' in types
    kick_beats = [ev['beat'] for ev in data['events'] if ev['drum_type'] == 'kick']
    assert len(kick_beats) >= 4 * 4  # 4 kicks per bar = 16 over 4 bars (before humanization)

def test_lo_fi_has_ghost_hihats():
    data = generate_drums('lo-fi', bars=2, seed=0)
    ghost_hats = [ev for ev in data['events']
                  if ev['drum_type'] == 'hihat' and ev['accent'] == 'ghost']
    assert len(ghost_hats) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Bars scaling
# ═══════════════════════════════════════════════════════════════════════════════

def test_more_bars_more_events():
    d1 = generate_drums('pop', bars=1, bpm=120, seed=0, variation_bars=0)
    d4 = generate_drums('pop', bars=4, bpm=120, seed=0, variation_bars=0)
    assert len(d4['events']) > len(d1['events'])

def test_event_count_scales_with_bars():
    d1 = generate_drums('pop', bars=1, bpm=120, seed=0, variation_bars=0)
    d2 = generate_drums('pop', bars=2, bpm=120, seed=0, variation_bars=0)
    # 2 bars should have roughly twice the events of 1 bar
    assert len(d2['events']) == pytest.approx(len(d1['events']) * 2, abs=2)

def test_single_bar_generates_events():
    data = generate_drums('pop', bars=1, seed=0)
    assert len(data['events']) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Fill / variation system
# ═══════════════════════════════════════════════════════════════════════════════

def test_pop_fill_adds_exact_snare_beats():
    # pop fill template adds snare at 3.25, 3.5, 3.75 within bar 3
    # absolute beats with bars=4: 12 + 3.25 = 15.25, etc.
    data = generate_drums('pop', bars=4, bpm=120, seed=42, variation_bars=4)
    snare_beats = {ev['beat'] for ev in data['events'] if ev['drum_type'] == 'snare'}
    assert 15.25 in snare_beats
    assert 15.5  in snare_beats
    assert 15.75 in snare_beats

def test_fill_notes_absent_when_disabled():
    data = generate_drums('pop', bars=4, bpm=120, seed=42, variation_bars=0)
    snare_beats = {ev['beat'] for ev in data['events'] if ev['drum_type'] == 'snare'}
    # Fill notes are at exact float values 15.25, 15.5, 15.75
    assert 15.25 not in snare_beats
    assert 15.5  not in snare_beats
    assert 15.75 not in snare_beats

def test_fill_applied_every_n_bars():
    # bars=8, variation_bars=4 → fills at bars 3 and 7
    data = generate_drums('pop', bars=8, bpm=120, seed=42, variation_bars=4)
    snare_beats = {ev['beat'] for ev in data['events'] if ev['drum_type'] == 'snare'}
    # Bar 3 fill: absolute beats 12 + {3.25, 3.5, 3.75}
    assert 15.25 in snare_beats
    # Bar 7 fill: absolute beats 28 + {3.25, 3.5, 3.75}
    assert 31.25 in snare_beats

def test_variation_bars_zero_disables_all_fills():
    with_fill    = generate_drums('pop', bars=8, bpm=120, seed=0, variation_bars=4)
    without_fill = generate_drums('pop', bars=8, bpm=120, seed=0, variation_bars=0)
    # Fills add extra notes → with_fill should have more events
    assert len(with_fill['events']) != len(without_fill['events'])

def test_no_fill_when_bars_less_than_variation_bars():
    # bars=3, variation_bars=4 → no fills (incomplete phrase)
    data_no_fill = generate_drums('pop', bars=3, bpm=120, seed=0, variation_bars=4)
    data_disabled = generate_drums('pop', bars=3, bpm=120, seed=0, variation_bars=0)
    assert len(data_no_fill['events']) == len(data_disabled['events'])

def test_hip_hop_fill_adds_snare_in_fill_zone():
    # hip-hop fill: snare ghost at 3.5, medium at 3.75 → abs 15.5, 15.75
    data = generate_drums('hip-hop', bars=4, bpm=120, seed=42, variation_bars=4)
    snare_beats = {ev['beat'] for ev in data['events'] if ev['drum_type'] == 'snare'}
    assert 15.5  in snare_beats
    assert 15.75 in snare_beats

def test_edm_fill_adds_snare_at_3_875():
    # EDM fill adds snare at 3.875 within bar → abs 15.875
    data = generate_drums('edm', bars=4, bpm=120, seed=42, variation_bars=4)
    snare_beats = {ev['beat'] for ev in data['events'] if ev['drum_type'] == 'snare'}
    assert 15.875 in snare_beats

def test_fill_velocity_for_strong_accent():
    data = generate_drums('pop', bars=4, bpm=120, seed=0, variation_bars=4)
    # snare at 15.75 is 'strong' → velocity == 94 (no humanization on fill notes)
    strong_fill = [ev for ev in data['events']
                   if ev['drum_type'] == 'snare' and ev['beat'] == 15.75]
    assert len(strong_fill) == 1
    assert strong_fill[0]['velocity'] == 94
    assert strong_fill[0]['accent'] == 'strong'


# ═══════════════════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════════════════

def test_same_seed_produces_same_output():
    d1 = generate_drums('pop', bars=4, seed=99)
    d2 = generate_drums('pop', bars=4, seed=99)
    assert d1['events'] == d2['events']

def test_different_seeds_produce_different_velocities():
    d1 = generate_drums('jazz', bars=4, seed=1)
    d2 = generate_drums('jazz', bars=4, seed=2)
    v1 = [ev['velocity'] for ev in d1['events']]
    v2 = [ev['velocity'] for ev in d2['events']]
    assert v1 != v2

def test_none_seed_runs_without_error():
    data = generate_drums('pop', bars=2, seed=None)
    assert len(data['events']) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Genre aliases
# ═══════════════════════════════════════════════════════════════════════════════

def test_hiphop_alias_resolves():
    data = generate_drums('hiphop', bars=2, seed=0)
    assert data['genre'] == 'hip-hop'

def test_lofi_alias_resolves():
    data = generate_drums('lofi', bars=2, seed=0)
    assert data['genre'] == 'lo-fi'

def test_electronic_alias_resolves():
    data = generate_drums('electronic', bars=2, seed=0)
    assert data['genre'] == 'edm'

def test_unknown_genre_falls_back_to_pop():
    data = generate_drums('country', bars=2, seed=0)
    assert data['genre'] == 'pop'


# ═══════════════════════════════════════════════════════════════════════════════
# _make_event helper
# ═══════════════════════════════════════════════════════════════════════════════

def test_make_event_kick():
    ev = RhythmEvent(beat=0.0, duration=0.1, velocity=94, accent='strong')
    result = _make_event(ev, 'kick')
    assert result['drum_type'] == 'kick'
    assert result['pitch']     == 36
    assert result['beat']      == 0.0
    assert result['velocity']  == 94
    assert result['accent']    == 'strong'

def test_make_event_unknown_voice_falls_back_to_snare():
    ev = RhythmEvent(beat=1.0, duration=0.1, velocity=75, accent='medium')
    result = _make_event(ev, 'cowbell_special')
    assert result['pitch'] == GM_DRUM_MAP['snare']

def test_make_event_preserves_all_fields():
    ev = RhythmEvent(beat=2.5, duration=0.25, velocity=55, accent='weak')
    result = _make_event(ev, 'hihat')
    assert result['beat']      == 2.5
    assert result['duration']  == 0.25
    assert result['velocity']  == 55
    assert result['accent']    == 'weak'
    assert result['drum_type'] == 'hihat'
    assert result['pitch']     == 42


# ═══════════════════════════════════════════════════════════════════════════════
# _apply_fill helper
# ═══════════════════════════════════════════════════════════════════════════════

def test_apply_fill_adds_fill_notes():
    import random
    events = [{'beat': 0.0, 'duration': 0.1, 'velocity': 90, 'drum_type': 'kick', 'pitch': 36, 'accent': 'strong'}]
    rng = random.Random(0)
    result = _apply_fill(events, fill_bar=0, beats_per_bar=4, genre='pop', rng=rng)
    snare_beats = {ev['beat'] for ev in result if ev['drum_type'] == 'snare'}
    assert 3.25 in snare_beats
    assert 3.5  in snare_beats
    assert 3.75 in snare_beats

def test_apply_fill_thins_hats_in_fill_zone():
    import random
    # 20 hat events in the fill zone (beat 2.5 to 4.0 for beats_per_bar=4, bar=0)
    events = [
        {'beat': 2.5 + i * 0.1, 'duration': 0.1, 'velocity': 75,
         'drum_type': 'hihat', 'pitch': 42, 'accent': 'medium'}
        for i in range(15)
    ]
    rng = random.Random(0)
    result = _apply_fill(events, fill_bar=0, beats_per_bar=4, genre='pop', rng=rng)
    hat_count = sum(1 for ev in result if ev['drum_type'] == 'hihat')
    assert hat_count < 15  # some hats were dropped


# ═══════════════════════════════════════════════════════════════════════════════
# drum_writer.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_drum_channel_constant():
    assert DRUM_CHANNEL == 9

def test_write_drums_returns_int(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    idx = write_drums(b, pop_4bar)
    assert isinstance(idx, int)

def test_write_drums_track_index_is_zero_first_track(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    idx = write_drums(b, pop_4bar)
    assert idx == 0

def test_write_drums_increments_track_index(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    idx1 = write_drums(b, pop_4bar, track_name='Drums A')
    idx2 = write_drums(b, pop_4bar, track_name='Drums B')
    assert idx2 == idx1 + 1

def test_write_drums_adds_to_note_count(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    write_drums(b, pop_4bar)
    assert b.note_count == len(pop_4bar['events'])

def test_write_drums_empty_events_still_adds_track():
    b = MidiBuilder()
    b.set_tempo(120)
    drum_data = {'genre': 'pop', 'bpm': 120, 'bars': 1, 'events': []}
    idx = write_drums(b, drum_data)
    assert isinstance(idx, int)
    assert b.note_count == 0

def test_write_drums_produces_valid_midi(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    write_drums(b, pop_4bar)
    midi_bytes = b.to_bytes()
    assert midi_bytes[:4] == bytes.fromhex('4d546864')  # MThd

def test_write_drums_note_on_channel_9_in_midi_bytes(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    write_drums(b, pop_4bar)
    midi_bytes = b.to_bytes()
    # MIDI note-on channel 9 = status byte 0x99
    assert b'\x99' in midi_bytes

def test_write_drums_custom_track_name(pop_4bar):
    b = MidiBuilder()
    b.set_tempo(120)
    write_drums(b, pop_4bar, track_name='Kit A')
    assert b.track_count == 1

def test_write_drums_combined_with_other_tracks(pop_4bar):
    from midi.builder import build_from_chord_progression
    # Build chords first (uses chord_service output shape)
    chord_data = {
        'bpm': 120,
        'time_signature': (4, 4),
        'key': 'C',
        'mode': 'major',
        'scale': 'major',
        'chord_scale': 'major',
        'genre': 'pop',
        'bars': 4,
        'chords': [{
            'beat_start': 0.0,
            'root': 'C',
            'quality': 'maj',
            'notes': [60, 64, 67],
            'name': 'Cmaj',
            'beat_duration': 16.0,
        }],
    }
    b = build_from_chord_progression(chord_data)
    drum_idx = write_drums(b, pop_4bar)
    assert drum_idx == 1   # second track (after chords)
    assert b.note_count > len(pop_4bar['events'])   # chord + drum notes
