from pathlib import Path
import mido
from ..common import StudioError


def inspect_midi(path: Path) -> dict:
    midi = mido.MidiFile(path)
    if midi.type == 2:
        raise StudioError("MIDI_UNSUPPORTED", "Type 2 asynchronous MIDI is not supported")
    return {"type": midi.type, "ticks_per_beat": midi.ticks_per_beat, "duration_seconds": midi.length,
            "tracks": [{"name": t.name, "note_on_count": sum(m.type == "note_on" and m.velocity > 0 for m in t)}
                       for t in midi.tracks]}
