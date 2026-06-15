"""
midi/drum_writer.py
Writes drum events from drum_service output to a MidiBuilder track.

All timing, velocity, and GM note numbers are pre-resolved by drum_service.
This writer contains no music-theory logic — it is a pure MIDI translator.

Public API
──────────
  DRUM_CHANNEL  int   9 (General MIDI percussion channel, 0-indexed)
  write_drums(builder, drum_data, track_name) -> int

Usage
─────
  from midi.builder    import MidiBuilder
  from midi.drum_writer import write_drums
  from backend.services.drum_service import generate_drums

  builder   = MidiBuilder()
  builder.set_tempo(120)
  drum_data = generate_drums('pop', bars=4, bpm=120, seed=42)
  track_idx = write_drums(builder, drum_data)
  builder.save('output.mid')
"""

from __future__ import annotations

from midi.builder import MidiBuilder

DRUM_CHANNEL: int = 9  # General MIDI percussion — fixed by the GM standard


def write_drums(
    builder: MidiBuilder,
    drum_data: dict,
    track_name: str = 'Drums',
) -> int:
    """
    Add a drum track to builder and write all events from drum_service output.

    Parameters
    ----------
    builder : MidiBuilder
        The MIDI builder to write into.  Caller is responsible for setting
        tempo and time signature before writing.
    drum_data : dict
        Output from drum_service.generate_drums().
        Must contain an 'events' list where each event has:
          beat, duration, velocity, pitch  (drum_type and accent are ignored here)
    track_name : str
        Label for the MIDI track.

    Returns
    -------
    int
        The 0-based track index assigned by MidiBuilder.add_track().
    """
    track_idx = builder.add_track(track_name)

    for ev in drum_data['events']:
        builder.add_note(
            track          = track_idx,
            channel        = DRUM_CHANNEL,
            pitch          = ev['pitch'],
            start_beat     = ev['beat'],
            duration_beats = ev['duration'],
            velocity       = ev['velocity'],
        )

    return track_idx
