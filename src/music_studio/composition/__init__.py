"""Declarative, editable composition plan; no hidden model calls."""
from __future__ import annotations
import mido
from ..common import StudioError, integer, number, new_output


def compose(plan: dict, output: str | None = None) -> dict:
    bpm = number(plan.get("bpm", 120), 20, 300, "bpm")
    bars = integer(plan.get("bars", 8), 1, 1024, "bars")
    meter = plan.get("time_signature", [4, 4])
    if not isinstance(meter, list) or len(meter) != 2:
        raise StudioError("CONFIG_ERROR", "time_signature requires [numerator, denominator]")
    numerator = integer(meter[0], 1, 32, "numerator")
    denominator = integer(meter[1], 1, 32, "denominator")
    if denominator & (denominator - 1):
        raise StudioError("CONFIG_ERROR", "Time signature denominator must be a power of two")
    beats_per_bar = numerator * 4 / denominator
    total_beats = bars * beats_per_bar
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 16:
        raise StudioError("CONFIG_ERROR", "tracks requires 1 to 16 track mappings")
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    conductor = mido.MidiTrack()
    conductor.extend([mido.MetaMessage("track_name", name="Conductor"),
                      mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)),
                      mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator),
                      mido.MetaMessage("end_of_track", time=round(total_beats * 480))])
    midi.tracks.append(conductor)
    channels, note_count = set(), 0
    for i, spec in enumerate(tracks):
        if not isinstance(spec, dict):
            raise StudioError("CONFIG_ERROR", "Each track must be a mapping")
        channel = integer(spec.get("channel", i), 0, 15, "channel")
        if channel in channels:
            raise StudioError("CONFIG_ERROR", "Each independent track needs a unique MIDI channel")
        channels.add(channel)
        program = integer(spec.get("program", 0), 0, 127, "program (zero based)")
        bank = integer(spec.get("bank", 128 if channel == 9 else 0), 0, 16383, "bank")
        events = spec.get("notes", [])
        if not isinstance(events, list) or not events:
            raise StudioError("CONFIG_ERROR", "Each track requires a nonempty notes list")
        repeat = spec.get("repeat_each_bar", False)
        if not isinstance(repeat, bool):
            raise StudioError("CONFIG_ERROR", "repeat_each_bar must be true or false")
        shifts = spec.get("bar_transpose", [0])
        if not isinstance(shifts, list) or not shifts:
            raise StudioError("CONFIG_ERROR", "bar_transpose requires a nonempty integer list")
        shifts = [integer(x, -48, 48, "bar_transpose") for x in shifts]
        scheduled = []
        for bar in range(bars if repeat else 1):
            for event in events:
                if not isinstance(event, dict):
                    raise StudioError("CONFIG_ERROR", "Each note event must be a mapping")
                start = number(event.get("beat", 0), 0, total_beats, "beat")
                duration = number(event.get("duration", 1), 1/480, total_beats, "duration")
                if repeat and start + duration > beats_per_bar + 1e-8:
                    raise StudioError("CONFIG_ERROR", "Repeated note exceeds its bar")
                start += bar * beats_per_bar
                if start + duration > total_beats + 1e-8:
                    raise StudioError("CONFIG_ERROR", "Note exceeds composition length")
                pitches = event.get("pitches", [event.get("pitch", 60)])
                if not isinstance(pitches, list) or not pitches:
                    raise StudioError("CONFIG_ERROR", "pitches requires a nonempty list")
                velocity = integer(event.get("velocity", 80), 1, 127, "velocity")
                for pitch in pitches:
                    note = integer(pitch, 0, 127, "pitch") + (shifts[bar % len(shifts)] if repeat else 0)
                    integer(note, 0, 127, "transposed pitch")
                    scheduled.extend([(round(start * 480), 1, note, velocity),
                                      (round((start + duration) * 480), 0, note, 0)])
                    note_count += 1
        track = mido.MidiTrack()
        track.extend([mido.MetaMessage("track_name", name=str(spec.get("name", f"Track {i+1}"))),
                      mido.Message("control_change", channel=channel, control=0, value=bank // 128),
                      mido.Message("control_change", channel=channel, control=32, value=bank % 128),
                      mido.Message("program_change", channel=channel, program=program),
                      mido.Message("control_change", channel=channel, control=10,
                                   value=integer(spec.get("pan", 64), 0, 127, "pan"))])
        last = 0
        for tick, on, note, velocity in sorted(scheduled):
            track.append(mido.Message("note_on" if on else "note_off", channel=channel,
                                      note=note, velocity=velocity, time=tick-last))
            last = tick
        track.append(mido.MetaMessage("end_of_track", time=round(total_beats * 480)-last))
        midi.tracks.append(track)
    path = new_output(output or plan.get("output", "projects/composition.mid"))
    midi.save(path)
    return {"path": str(path), "bars": bars, "instrument_tracks": len(tracks), "notes": note_count,
            "bpm": bpm, "duration_seconds": midi.length, "composer": "declarative-v1"}
