from __future__ import annotations
import ctypes as c
import hashlib
import os
from pathlib import Path
import mido
import numpy as np
import soundfile as sf
from ..common import StudioError, required_file, new_output, integer, number, resolve


def soundfont_entry(config: dict, identifier: str | None = None) -> dict:
    identifier = identifier or config.get("default_soundfont")
    matches = [e for e in config.get("soundfonts", []) if e.get("id") == identifier]
    if len(matches) != 1:
        raise StudioError("SOUNDFONT_UNREGISTERED", f"SoundFont id not found or ambiguous: {identifier}")
    entry = matches[0]
    if entry.get("format", "sf2") != "sf2":
        raise StudioError("FORMAT_UNSUPPORTED", "Only SF2 rendering is implemented; SFZ is registry-only")
    path = required_file(entry.get("path", ""), "SOUNDFONT_MISSING")
    for field in ("license", "source", "author"):
        if not entry.get(field):
            raise StudioError("LICENSE_METADATA_MISSING", f"SoundFont requires {field}")
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    if entry.get("sha256") and digest.lower() != entry["sha256"].lower():
        raise StudioError("SOUNDFONT_HASH_MISMATCH", f"SoundFont differs from registry: {path}")
    return {**entry, "path": str(path), "sha256": digest}


class FluidSynth:
    def __init__(self, config: dict, soundfont: str | None = None, sample_rate: int = 44100, gain: float = .4):
        self.entry = soundfont_entry(config, soundfont)
        dll = required_file(config.get("fluidsynth_library", ""), "ENGINE_MISSING")
        self.directory = os.add_dll_directory(str(dll.parent)) if os.name == "nt" else None
        self.settings = self.synth = None
        try:
            self.lib = c.CDLL(str(dll))
        except OSError as exc:
            if self.directory:
                self.directory.close()
            raise StudioError("ENGINE_LOAD_FAILED", f"Cannot load FluidSynth: {dll}", str(exc)) from exc
        signatures = {
            "new_fluid_settings": (c.c_void_p, []),
            "delete_fluid_settings": (None, [c.c_void_p]),
            "fluid_settings_setnum": (c.c_int, [c.c_void_p, c.c_char_p, c.c_double]),
            "fluid_settings_setint": (c.c_int, [c.c_void_p, c.c_char_p, c.c_int]),
            "new_fluid_synth": (c.c_void_p, [c.c_void_p]),
            "delete_fluid_synth": (None, [c.c_void_p]),
            "fluid_synth_sfload": (c.c_int, [c.c_void_p, c.c_char_p, c.c_int]),
            "fluid_synth_get_sfont_by_id": (c.c_void_p, [c.c_void_p, c.c_int]),
            "fluid_sfont_iteration_start": (None, [c.c_void_p]),
            "fluid_sfont_iteration_next": (c.c_void_p, [c.c_void_p]),
            "fluid_preset_get_name": (c.c_char_p, [c.c_void_p]),
            "fluid_preset_get_banknum": (c.c_int, [c.c_void_p]),
            "fluid_preset_get_num": (c.c_int, [c.c_void_p]),
            "fluid_synth_write_float": (c.c_int, [c.c_void_p, c.c_int, c.c_void_p, c.c_int, c.c_int, c.c_void_p, c.c_int, c.c_int]),
        }
        for name, arity in {"noteon": 3, "noteoff": 2, "program_change": 2, "cc": 3,
                            "pitch_bend": 2, "channel_pressure": 2, "key_pressure": 3,
                            "all_notes_off": 1, "all_sounds_off": 1, "program_select": 4}.items():
            signatures[f"fluid_synth_{name}"] = (c.c_int, [c.c_void_p] + [c.c_int] * arity)
        for name, (restype, args) in signatures.items():
            f = getattr(self.lib, name)
            f.restype, f.argtypes = restype, args
        try:
            self.settings = self.lib.new_fluid_settings()
            if not self.settings:
                raise StudioError("ENGINE_LOAD_FAILED", "FluidSynth settings allocation failed")
            for name, value in [(b"synth.sample-rate", sample_rate), (b"synth.gain", gain)]:
                if self.lib.fluid_settings_setnum(self.settings, name, value) < 0:
                    raise StudioError("ENGINE_SETTINGS_FAILED", f"FluidSynth rejected {name!r}")
            for name, value in [(b"synth.reverb.active", 0), (b"synth.chorus.active", 0), (b"synth.polyphony", 256)]:
                self.lib.fluid_settings_setint(self.settings, name, value)
            self.synth = self.lib.new_fluid_synth(self.settings)
            if not self.synth:
                raise StudioError("ENGINE_LOAD_FAILED", "FluidSynth synth allocation failed")
            self.sfid = self.lib.fluid_synth_sfload(self.synth, str(self.entry["path"]).encode("utf-8"), 1)
            if self.sfid < 0:
                raise StudioError("SOUNDFONT_LOAD_FAILED", "FluidSynth could not load registered SF2")
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.synth:
            self.lib.delete_fluid_synth(self.synth)
            self.synth = None
        if self.settings:
            self.lib.delete_fluid_settings(self.settings)
            self.settings = None
        if self.directory:
            self.directory.close()
            self.directory = None

    def presets(self) -> list[dict]:
        font = self.lib.fluid_synth_get_sfont_by_id(self.synth, self.sfid)
        self.lib.fluid_sfont_iteration_start(font)
        result = []
        while preset := self.lib.fluid_sfont_iteration_next(font):
            result.append({"bank": self.lib.fluid_preset_get_banknum(preset),
                           "program": self.lib.fluid_preset_get_num(preset),
                           "name": self.lib.fluid_preset_get_name(preset).decode("utf-8", errors="replace")})
        return result

    def call(self, name: str, *args):
        if getattr(self.lib, "fluid_synth_" + name)(self.synth, *args) < 0:
            raise StudioError("SYNTH_EVENT_FAILED", f"FluidSynth rejected {name}{args}")

    def samples(self, frames: int) -> np.ndarray:
        left, right = np.empty(frames, np.float32), np.empty(frames, np.float32)
        if frames and self.lib.fluid_synth_write_float(self.synth, frames, left.ctypes.data, 0, 1,
                                                      right.ctypes.data, 0, 1) < 0:
            raise StudioError("RENDER_FAILED", "FluidSynth failed writing audio")
        return np.column_stack((left, right))


def render(config: dict, input_path: str, output_path: str, soundfont: str | None = None,
           sample_rate: int = 44100, tail: float = 2.0, gain: float = .4) -> dict:
    source = required_file(input_path)
    target = new_output(output_path)
    if target.suffix.lower() != ".wav":
        raise StudioError("FORMAT_UNSUPPORTED", "render produces WAV; use export for other formats")
    sample_rate = integer(sample_rate, 8000, 192000, "sample_rate")
    tail = number(tail, .05, 30, "tail")
    gain = number(gain, .001, 2, "gain")
    midi = mido.MidiFile(source)
    if midi.type == 2 or midi.length <= 0 or midi.length > 3600:
        raise StudioError("MIDI_UNSUPPORTED", "Need synchronous MIDI lasting 0 to 3600 seconds")
    note_count = sum(m.type == "note_on" and m.velocity > 0 for t in midi.tracks for m in t)
    if not note_count:
        raise StudioError("MIDI_EMPTY", "MIDI contains no audible note-on messages")
    unsupported = set()
    with FluidSynth(config, soundfont, sample_rate, gain) as synth:
        available = {(p["bank"], p["program"]) for p in synth.presets()}
        bank_msb = [0] * 16
        bank_lsb = [0] * 16
        bank_msb[9] = 1
        with sf.SoundFile(str(target), "x", samplerate=sample_rate, channels=2, subtype="PCM_24", format="WAV") as audio:
            seconds, frame = 0.0, 0
            def flush(count):
                while count:
                    n = min(4096, count)
                    block = synth.samples(n)
                    if not np.isfinite(block).all() or np.max(np.abs(block)) >= 1:
                        raise StudioError("RENDER_CLIPPING", "Raw render clips or contains nonfinite samples; lower --gain")
                    audio.write(block)
                    count -= n
            for msg in midi:
                seconds += msg.time
                next_frame = round(seconds * sample_rate)
                flush(next_frame-frame)
                frame = next_frame
                if msg.is_meta:
                    continue
                ch = getattr(msg, "channel", 0)
                match msg.type:
                    case "note_on": synth.call("noteon", ch, msg.note, msg.velocity)
                    case "note_off": synth.call("noteoff", ch, msg.note)
                    case "program_change":
                        bank = bank_msb[ch]*128 + bank_lsb[ch]
                        if (bank, msg.program) not in available:
                            raise StudioError("INSTRUMENT_MISSING", f"SF2 has no bank={bank}, program={msg.program}; inspect list-instruments")
                        synth.call("program_select", ch, synth.sfid, bank, msg.program)
                    case "control_change":
                        if msg.control == 0: bank_msb[ch] = msg.value
                        if msg.control == 32: bank_lsb[ch] = msg.value
                        synth.call("cc", ch, msg.control, msg.value)
                    case "pitchwheel": synth.call("pitch_bend", ch, msg.pitch + 8192)
                    case "aftertouch": synth.call("channel_pressure", ch, msg.value)
                    case "polytouch": synth.call("key_pressure", ch, msg.note, msg.value)
                    case _: unsupported.add(msg.type)
            for ch in range(16):
                synth.call("cc", ch, 64, 0)
                synth.call("all_notes_off", ch)
            flush(round(tail * sample_rate))
    return {"path": str(target), "sample_rate": sample_rate, "channels": 2, "notes": note_count,
            "midi_seconds": midi.length, "tail_seconds": tail, "soundfont": soundfont or config.get("default_soundfont"),
            "soundfont_sha256": synth.entry["sha256"], "unsupported_messages": sorted(unsupported)}
