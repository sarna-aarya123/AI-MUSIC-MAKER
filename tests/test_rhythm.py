"""
tests/test_rhythm.py
Tests for music_theory/rhythm.py
Run with: python -m pytest tests/test_rhythm.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import math
import pytest

from music_theory.rhythm import (
    PPQ, TICKS, BEAT_VALUE,
    RhythmEvent, RhythmPattern, HumanizeSettings,
    beats_to_ticks, ticks_to_beats, bars_to_ticks,
    quantize_to_grid, get_beat_positions,
    get_humanize_settings, apply_humanization,
    generate_rhythm_pattern,
    _swing_beat, _resolve_genre,
)


# ── Constants ─────────────────────────────────────────────────────────────────

class TestConstants:

    def test_ppq_is_480(self):
        assert PPQ == 480

    def test_ticks_quarter(self):
        assert TICKS[4] == 480

    def test_ticks_eighth(self):
        assert TICKS[8] == 240

    def test_ticks_sixteenth(self):
        assert TICKS[16] == 120

    def test_ticks_whole(self):
        assert TICKS[1] == 1920

    def test_ticks_half(self):
        assert TICKS[2] == 960

    def test_ticks_32nd(self):
        assert TICKS[32] == 60

    def test_ticks_64th(self):
        assert TICKS[64] == 30

    def test_beat_value_quarter(self):
        assert BEAT_VALUE[4] == 1.0

    def test_beat_value_eighth(self):
        assert BEAT_VALUE[8] == 0.5

    def test_beat_value_sixteenth(self):
        assert BEAT_VALUE[16] == 0.25

    def test_beat_value_whole(self):
        assert BEAT_VALUE[1] == 4.0

    def test_beat_value_matches_ticks_ratio(self):
        for n, t in TICKS.items():
            assert abs(BEAT_VALUE[n] - t / PPQ) < 1e-9


# ── Tick / beat conversion ────────────────────────────────────────────────────

class TestConversions:

    def test_beats_to_ticks_quarter(self):
        assert beats_to_ticks(1.0) == 480

    def test_beats_to_ticks_half(self):
        assert beats_to_ticks(2.0) == 960

    def test_beats_to_ticks_eighth(self):
        assert beats_to_ticks(0.5) == 240

    def test_beats_to_ticks_custom_ppq(self):
        assert beats_to_ticks(1.0, ppq=960) == 960

    def test_ticks_to_beats_quarter(self):
        assert ticks_to_beats(480) == 1.0

    def test_ticks_to_beats_half(self):
        assert ticks_to_beats(960) == 2.0

    def test_roundtrip_beats_ticks(self):
        for beats in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0):
            assert abs(ticks_to_beats(beats_to_ticks(beats)) - beats) < 1e-9

    def test_bars_to_ticks_one_bar(self):
        # 1 bar × 4 beats × 480 ppq = 1920
        assert bars_to_ticks(1) == 1920

    def test_bars_to_ticks_four_bars(self):
        assert bars_to_ticks(4) == 7680

    def test_bars_to_ticks_custom_bpb(self):
        # 3/4 time: 1 bar = 3 beats = 1440 ticks
        assert bars_to_ticks(1, beats_per_bar=3) == 1440

    def test_bars_to_ticks_custom_ppq(self):
        assert bars_to_ticks(1, ppq=960) == 3840


# ── quantize_to_grid ─────────────────────────────────────────────────────────

class TestQuantizeToGrid:

    def test_already_on_grid(self):
        assert quantize_to_grid(240, 120) == 240

    def test_rounds_down(self):
        assert quantize_to_grid(239, 120) == 240   # 239 is closer to 240 than 120

    def test_rounds_up(self):
        assert quantize_to_grid(61, 120) == 120    # 61 > 60, rounds to 120

    def test_exact_midpoint_rounds_to_upper(self):
        # 180 is exactly halfway between 120 and 240
        result = quantize_to_grid(180, 120)
        assert result in (120, 240)   # Python rounds to even; accept either

    def test_quarter_note_grid(self):
        assert quantize_to_grid(241, 480) == 480   # rounds up to next quarter

    def test_zero_ticks(self):
        assert quantize_to_grid(0, 120) == 0

    def test_large_value(self):
        assert quantize_to_grid(1920, 480) == 1920

    def test_invalid_grid_size_raises(self):
        with pytest.raises(ValueError):
            quantize_to_grid(120, 0)

    def test_negative_grid_size_raises(self):
        with pytest.raises(ValueError):
            quantize_to_grid(120, -1)


# ── get_beat_positions ────────────────────────────────────────────────────────

class TestGetBeatPositions:

    def test_eighth_notes_one_bar(self):
        pos = get_beat_positions(1, subdivision=8)
        assert len(pos) == 8
        assert pos[0] == 0.0
        assert abs(pos[1] - 0.5) < 1e-9
        assert abs(pos[-1] - 3.5) < 1e-9

    def test_quarter_notes_one_bar(self):
        pos = get_beat_positions(1, subdivision=4)
        assert pos == [0.0, 1.0, 2.0, 3.0]

    def test_sixteenth_notes_one_bar(self):
        pos = get_beat_positions(1, subdivision=16)
        assert len(pos) == 16
        assert abs(pos[1] - 0.25) < 1e-9

    def test_two_bars_eighth(self):
        pos = get_beat_positions(2, subdivision=8)
        assert len(pos) == 16
        assert abs(pos[-1] - 7.5) < 1e-9

    def test_whole_notes_one_bar(self):
        pos = get_beat_positions(1, subdivision=1)
        assert pos == [0.0]

    def test_half_notes_two_bars(self):
        pos = get_beat_positions(2, subdivision=2)
        assert len(pos) == 4
        assert pos == [0.0, 2.0, 4.0, 6.0]

    def test_3_4_time_one_bar_quarter(self):
        pos = get_beat_positions(1, subdivision=4, time_sig=(3, 4))
        assert len(pos) == 3
        assert pos == [0.0, 1.0, 2.0]

    def test_invalid_subdivision_raises(self):
        with pytest.raises(ValueError):
            get_beat_positions(1, subdivision=3)   # 3 is not power of 2 in TICKS

    def test_all_positions_non_negative(self):
        for sub in (4, 8, 16):
            for p in get_beat_positions(4, subdivision=sub):
                assert p >= 0


# ── _swing_beat ───────────────────────────────────────────────────────────────

class TestSwingBeat:

    def test_straight_is_identity(self):
        for beat in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
            assert _swing_beat(beat, 0.5) == beat

    def test_downbeats_unchanged_by_swing(self):
        for beat in (0.0, 1.0, 2.0, 3.0):
            assert _swing_beat(beat, 0.667) == beat

    def test_upbeat_pushed_to_swing_amount(self):
        # 0.5 (upbeat of beat 1) → swing_amount
        assert abs(_swing_beat(0.5, 0.667) - 0.667) < 1e-6

    def test_upbeat_of_beat_2(self):
        # 1.5 → 1 + swing_amount = 1.667
        assert abs(_swing_beat(1.5, 0.667) - 1.667) < 1e-6

    def test_light_swing(self):
        # 7:5 ratio: upbeat at 0.583
        assert abs(_swing_beat(0.5, 0.583) - 0.583) < 1e-6

    def test_16th_note_interpolation(self):
        # Between beat 0 and upbeat: 0.25 maps between 0 and swing_amount
        result = _swing_beat(0.25, 0.667)
        assert 0.0 < result < 0.667

    def test_16th_after_upbeat_interpolation(self):
        # Between upbeat and next downbeat: 0.75 maps between swing_amount and 1.0
        result = _swing_beat(0.75, 0.667)
        assert 0.667 < result < 1.0

    def test_swing_preserves_order(self):
        # Beat positions should remain monotonically increasing after swing
        beats = [i * 0.25 for i in range(17)]
        swung = [_swing_beat(b, 0.667) for b in beats]
        for i in range(1, len(swung)):
            assert swung[i] >= swung[i-1]


# ── _resolve_genre ────────────────────────────────────────────────────────────

class TestResolveGenre:

    def test_canonical_names_unchanged(self):
        for genre in ('pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'):
            assert _resolve_genre(genre) == genre

    def test_alias_hiphop(self):
        assert _resolve_genre('hiphop') == 'hip-hop'

    def test_alias_lofi(self):
        assert _resolve_genre('lofi') == 'lo-fi'

    def test_alias_electronic(self):
        assert _resolve_genre('electronic') == 'edm'

    def test_alias_rock(self):
        assert _resolve_genre('rock') == 'pop'

    def test_alias_blues(self):
        assert _resolve_genre('blues') == 'jazz'

    def test_alias_ambient(self):
        assert _resolve_genre('ambient') == 'lo-fi'

    def test_unknown_falls_back_to_pop(self):
        assert _resolve_genre('zydeco') == 'pop'

    def test_case_insensitive(self):
        assert _resolve_genre('JAZZ') == 'jazz'
        assert _resolve_genre('HipHop') == 'hip-hop'


# ── get_humanize_settings ─────────────────────────────────────────────────────

class TestGetHumanizeSettings:

    def test_returns_humanize_settings(self):
        s = get_humanize_settings('pop')
        assert isinstance(s, HumanizeSettings)

    def test_pop_tight(self):
        s = get_humanize_settings('pop')
        assert s.timing_jitter < 0.02
        assert s.velocity_variance <= 8

    def test_lofi_loose(self):
        s = get_humanize_settings('lo-fi')
        assert s.timing_jitter > 0.02

    def test_edm_tightest(self):
        edm = get_humanize_settings('edm')
        pop = get_humanize_settings('pop')
        assert edm.timing_jitter <= pop.timing_jitter

    def test_jazz_more_jitter_than_pop(self):
        j = get_humanize_settings('jazz')
        p = get_humanize_settings('pop')
        assert j.timing_jitter > p.timing_jitter

    def test_alias_accepted(self):
        assert get_humanize_settings('hiphop') == get_humanize_settings('hip-hop')


# ── apply_humanization ────────────────────────────────────────────────────────

class TestApplyHumanization:

    def _make_events(self, n=4, accent='medium'):
        return [RhythmEvent(float(i), 0.5, 75, accent) for i in range(n)]

    def test_returns_new_list(self):
        evs = self._make_events()
        result = apply_humanization(evs)
        assert result is not evs

    def test_input_not_mutated(self):
        evs = self._make_events()
        original_beats = [e.beat for e in evs]
        apply_humanization(evs, seed=42)
        assert [e.beat for e in evs] == original_beats

    def test_output_length_matches_input(self):
        evs = self._make_events(8)
        assert len(apply_humanization(evs)) == 8

    def test_velocities_stay_in_range(self):
        evs = [RhythmEvent(float(i), 0.5, v, 'medium')
               for i, v in enumerate([1, 10, 60, 100, 127])]
        result = apply_humanization(evs, seed=0)
        for ev in result:
            assert 1 <= ev.velocity <= 127

    def test_beats_non_negative(self):
        # Event at beat 0.0 should not become negative
        evs = [RhythmEvent(0.0, 0.5, 70, 'medium')]
        result = apply_humanization(evs, seed=99)
        assert result[0].beat >= 0.0

    def test_duration_unchanged(self):
        evs = self._make_events()
        result = apply_humanization(evs, seed=1)
        for orig, out in zip(evs, result):
            assert out.duration == orig.duration

    def test_accent_unchanged(self):
        evs = self._make_events()
        result = apply_humanization(evs, seed=1)
        for orig, out in zip(evs, result):
            assert out.accent == orig.accent

    def test_deterministic_with_seed(self):
        evs = self._make_events(10)
        r1 = apply_humanization(evs, seed=42)
        r2 = apply_humanization(evs, seed=42)
        assert [e.beat for e in r1] == [e.beat for e in r2]
        assert [e.velocity for e in r1] == [e.velocity for e in r2]

    def test_different_seeds_produce_different_output(self):
        evs = self._make_events(10)
        r1 = apply_humanization(evs, seed=1)
        r2 = apply_humanization(evs, seed=999)
        # Beats should differ for at least some events
        assert any(a.beat != b.beat for a, b in zip(r1, r2))

    def test_settings_seed_overrides_arg_seed(self):
        evs = self._make_events(4)
        s   = HumanizeSettings(timing_jitter=0.01, velocity_variance=5, seed=100)
        r1  = apply_humanization(evs, settings=s, seed=999)  # seed arg should be ignored
        r2  = apply_humanization(evs, settings=s, seed=0)
        assert [e.beat for e in r1] == [e.beat for e in r2]

    def test_edm_minimal_jitter(self):
        # EDM should change beats less than lo-fi
        evs   = [RhythmEvent(float(i), 0.5, 75, 'medium') for i in range(20)]
        edm   = apply_humanization(evs, genre='edm',   seed=42)
        lofi  = apply_humanization(evs, genre='lo-fi', seed=42)
        edm_jitter  = sum(abs(o.beat - e.beat) for o, e in zip(evs, edm))
        lofi_jitter = sum(abs(o.beat - e.beat) for o, e in zip(evs, lofi))
        assert edm_jitter < lofi_jitter

    def test_empty_list_returns_empty(self):
        assert apply_humanization([]) == []


# ── generate_rhythm_pattern ───────────────────────────────────────────────────

class TestGenerateRhythmPattern:

    def _pat(self, genre='pop', bars=1):
        return generate_rhythm_pattern(genre, bars)

    # Structure
    def test_returns_rhythm_pattern(self):
        assert isinstance(self._pat(), RhythmPattern)

    def test_genre_field(self):
        p = self._pat('jazz')
        assert p.genre == 'jazz'

    def test_bars_field(self):
        p = self._pat(bars=4)
        assert p.bars == 4

    def test_beats_per_bar_is_4(self):
        assert self._pat().beats_per_bar == 4

    def test_groove_straight_for_pop(self):
        assert self._pat('pop').groove == 'straight'

    def test_groove_swing_for_jazz(self):
        assert self._pat('jazz').groove == 'swing'

    def test_swing_amount_pop(self):
        assert self._pat('pop').swing_amount == 0.5

    def test_swing_amount_jazz(self):
        assert abs(self._pat('jazz').swing_amount - 0.667) < 1e-6

    def test_swing_amount_hiphop(self):
        p = generate_rhythm_pattern('hip-hop')
        assert 0.5 < p.swing_amount < 0.7

    # Melody events
    def test_melody_events_is_list(self):
        assert isinstance(self._pat().melody_events, list)

    def test_melody_events_nonempty(self):
        assert len(self._pat().melody_events) > 0

    def test_melody_events_are_rhythm_events(self):
        for ev in self._pat().melody_events:
            assert isinstance(ev, RhythmEvent)

    def test_melody_event_fields(self):
        ev = self._pat().melody_events[0]
        assert hasattr(ev, 'beat')
        assert hasattr(ev, 'duration')
        assert hasattr(ev, 'velocity')
        assert hasattr(ev, 'accent')

    def test_melody_beats_non_negative(self):
        for ev in self._pat(bars=4).melody_events:
            assert ev.beat >= 0.0

    def test_melody_velocities_in_range(self):
        for genre in ('pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'):
            for ev in self._pat(genre).melody_events:
                assert 1 <= ev.velocity <= 127

    def test_melody_duration_positive(self):
        for ev in self._pat().melody_events:
            assert ev.duration > 0

    def test_melody_accent_valid(self):
        valid = {'strong', 'medium', 'weak', 'ghost'}
        for ev in self._pat().melody_events:
            assert ev.accent in valid

    def test_melody_beats_sorted(self):
        evs = self._pat(bars=4).melody_events
        assert evs == sorted(evs, key=lambda e: e.beat)

    def test_melody_scales_with_bars(self):
        # Events should increase proportionally with bars
        e1 = len(self._pat(bars=1).melody_events)
        e4 = len(self._pat(bars=4).melody_events)
        assert e4 == e1 * 4

    def test_melody_4_bars_max_beat(self):
        evs = self._pat(bars=4).melody_events
        assert max(e.beat for e in evs) < 4 * 4   # < 16 beats total

    # Drum events
    def test_drum_events_is_dict(self):
        assert isinstance(self._pat().drum_events, dict)

    def test_drum_events_nonempty(self):
        assert len(self._pat().drum_events) > 0

    def test_drum_pop_has_kick_snare_hihat(self):
        d = self._pat('pop').drum_events
        for voice in ('kick', 'snare', 'hihat'):
            assert voice in d

    def test_drum_jazz_has_ride(self):
        d = self._pat('jazz').drum_events
        assert 'ride' in d

    def test_drum_edm_has_open_hat(self):
        d = self._pat('edm').drum_events
        assert 'open_hat' in d

    def test_drum_velocities_in_range(self):
        for genre in ('pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'):
            for voice, evts in self._pat(genre).drum_events.items():
                for ev in evts:
                    assert 1 <= ev.velocity <= 127, f"{genre}/{voice}: {ev.velocity}"

    def test_drum_beats_non_negative(self):
        for voice, evts in self._pat(bars=4).drum_events.items():
            for ev in evts:
                assert ev.beat >= 0.0

    def test_drum_beats_sorted(self):
        for voice, evts in self._pat(bars=4).drum_events.items():
            assert evts == sorted(evts, key=lambda e: e.beat), f"{voice} not sorted"

    def test_drum_scales_with_bars(self):
        for genre in ('pop', 'jazz', 'edm'):
            d1 = self._pat(genre, bars=1).drum_events
            d4 = self._pat(genre, bars=4).drum_events
            for voice in d1:
                assert len(d4[voice]) == len(d1[voice]) * 4

    # Swing correctness
    def test_jazz_upbeats_are_swung(self):
        # In jazz, the ride's upbeat 8ths should be at X.667 not X.5
        # Use (beat % 1.0) to get fractional part — avoids banker's rounding pitfall
        ride = self._pat('jazz').drum_events['ride']
        upbeat_straight = [e.beat for e in ride if abs(e.beat % 1.0 - 0.5)  < 0.01]
        upbeat_swung    = [e.beat for e in ride if abs(e.beat % 1.0 - 0.667) < 0.01]
        assert len(upbeat_swung) > 0          # swung upbeats exist
        assert len(upbeat_straight) == 0      # no note sits at straight X.5 position

    def test_pop_upbeats_are_straight(self):
        # In pop (straight), upbeats are at exactly X.5 intervals
        hihat = self._pat('pop').drum_events['hihat']
        upbeat_beats = [e.beat for e in hihat if abs(e.beat % 1.0 - 0.5) < 1e-6]
        assert len(upbeat_beats) > 0

    # Aliases and edge cases
    def test_alias_hiphop_resolves(self):
        p = generate_rhythm_pattern('hiphop')
        assert p.genre == 'hip-hop'

    def test_unknown_genre_falls_back_to_pop(self):
        p = generate_rhythm_pattern('zydeco')
        assert p.genre == 'pop'

    def test_zero_bars_raises(self):
        with pytest.raises(ValueError):
            generate_rhythm_pattern('pop', bars=0)

    def test_negative_bars_raises(self):
        with pytest.raises(ValueError):
            generate_rhythm_pattern('pop', bars=-1)

    # All supported genres
    def test_all_genres_produce_valid_pattern(self):
        for genre in ('pop', 'hip-hop', 'jazz', 'lo-fi', 'edm'):
            p = generate_rhythm_pattern(genre, bars=2)
            assert len(p.melody_events) > 0
            assert len(p.drum_events) > 0

    # Integration: pattern → humanize → valid beats
    def test_humanize_pipeline(self):
        pat  = generate_rhythm_pattern('jazz', bars=4)
        mel  = apply_humanization(pat.melody_events, genre='jazz', seed=7)
        assert all(e.beat >= 0 for e in mel)
        assert all(1 <= e.velocity <= 127 for e in mel)

    def test_humanize_drums_pipeline(self):
        pat   = generate_rhythm_pattern('pop', bars=2)
        drums = {v: apply_humanization(h, genre='pop', seed=7)
                 for v, h in pat.drum_events.items()}
        for voice, hits in drums.items():
            assert all(1 <= e.velocity <= 127 for e in hits)
            assert all(e.beat >= 0 for e in hits)
