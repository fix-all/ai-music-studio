"""Real SF2 validation. Retains MIDI, audio, CLI envelopes and a measured summary."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
import numpy as np
import soundfile as sf
import mido
from music_studio.common import root_path, settings, write_json, load_yaml
from music_studio.composition import compose
from music_studio.synthesis.fluidsynth import render


def main() -> int:
    root = root_path()
    folder = root / "outputs" / ("validation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    results, checks = {}, {}
    summary = {"schema_version": 1, "kind": "functional fixture; no commissioned music", "folder": str(folder), "results": results, "checks": checks}

    def cli(name, *args, expected=0):
        proc = subprocess.run([sys.executable, "-m", "music_studio.cli", *args], cwd=root, capture_output=True, text=True, timeout=180)
        (folder / (name + ".stdout.json")).write_text(proc.stdout, encoding="utf-8")
        (folder / (name + ".stderr.log")).write_text(proc.stderr, encoding="utf-8")
        if proc.returncode != expected:
            raise RuntimeError(f"{name}: exit={proc.returncode}; inspect retained logs")
        envelope = json.loads(proc.stdout)
        results[name] = envelope
        return envelope["result"] if envelope["ok"] else envelope

    try:
        cli("doctor", "doctor")
        instrument_rows = cli("instruments", "list-instruments")["soundfonts"]
        checks["real_sf2_presets_loaded"] = len(instrument_rows[0]["presets"]) >= 128
        midi_path, dry, mixed = folder / "validation.mid", folder / "dry.wav", folder / "mixed.wav"
        composition = cli("compose", "compose", "--config", "config/example.yaml", "--output", str(midi_path))
        midi = mido.MidiFile(midi_path)
        checks["eight_bars"] = composition["bars"] >= 8 and abs(midi.length - 16) < 1e-6
        checks["independent_tracks"] = len([t for t in midi.tracks if any(m.type == "note_on" for m in t)]) >= 2
        checks["independent_channels"] = len({m.channel for t in midi.tracks for m in t if m.type == "note_on"}) >= 2
        cli("render", "render", "--input", str(midi_path), "--output", str(dry), "--tail", "2")
        dry_info = cli("analyze-dry", "analyze", "--input", str(dry))
        checks["dry_audio_quality"] = dry_info["quality_passed"] and dry_info["decode"]["full_decode_passed"]
        checks["duration_rate_channels"] = abs(dry_info["duration_seconds"]-18) < 1/44100 and dry_info["sample_rate"] == 44100 and dry_info["channels"] == 2
        cli("mix", "mix", "--input", str(dry), "--output", str(mixed), "--config", "config/mixing.yaml")
        final_info = cli("analyze-mixed", "analyze", "--input", str(mixed))
        checks["mixed_audio_quality"] = final_info["quality_passed"]
        for ext in ("mp3", "flac"):
            out = folder / ("validation." + ext)
            cli("export-" + ext, "export", "--input", str(mixed), "--output", str(out))
            info = cli("analyze-" + ext, "analyze", "--input", str(out))
            checks[ext + "_quality_and_decode"] = info["quality_passed"] and info["decode"]["full_decode_passed"]
            checks[ext + "_duration"] = abs(info["duration_seconds"]-18) < .1
        disabled = cli("generate-disabled", "generate", "--config", "config/generation.yaml", expected=2)
        checks["missing_model_honest_failure"] = disabled["error"]["code"] == "ENGINE_DISABLED" and not (root / "outputs/generation-test.wav").exists()
        # Controlled probes isolate velocity, note duration, release and simultaneous notes.
        probes = {}
        for name, velocity, duration, pitches in [("soft", 40, .2, [60]), ("loud", 110, .2, [60]),
                                                  ("long", 40, .8, [60]), ("poly", 80, .8, [60, 64, 67])]:
            probe_midi, probe_wav = folder / (name + ".mid"), folder / (name + ".wav")
            plan = {"bpm": 120, "bars": 1, "tracks": [{"program": 0, "notes": [
                {"beat": 0, "duration": duration*2, "pitches": pitches, "velocity": velocity}]}]}
            compose(plan, str(probe_midi))
            render(settings(), str(probe_midi), str(probe_wav), tail=1)
            probes[name], rate = sf.read(probe_wav, always_2d=True)
        def rms(name, start, end):
            return float(np.sqrt(np.mean(probes[name][round(start*rate):round(end*rate)]**2)))
        measured = {"soft_rms": rms("soft", 0, .18), "loud_rms": rms("loud", 0, .18),
                    "short_after_noteoff_rms": rms("soft", .4, .7), "long_sustained_rms": rms("long", .4, .7),
                    "release_tail_rms": rms("soft", .22, .4)}
        checks["velocity_changes_audio"] = measured["loud_rms"] > measured["soft_rms"]*1.5
        checks["note_duration_changes_audio"] = measured["long_sustained_rms"] > measured["short_after_noteoff_rms"]*1.5
        checks["release_tail_audible"] = measured["release_tail_rms"] > 1e-6
        block = probes["poly"][round(.05*rate):round(.7*rate)].mean(axis=1)
        spec = np.abs(np.fft.rfft(block*np.hanning(len(block))))
        freqs = np.fft.rfftfreq(len(block), 1/rate)
        tone_ratios = {}
        for pitch in (60, 64, 67):
            hz = 440*2**((pitch-69)/12)
            band = spec[np.abs(freqs-hz) < 4].max()
            floor = np.median(spec[(np.abs(freqs-hz) > 10) & (np.abs(freqs-hz) < 25)])
            tone_ratios[str(pitch)] = float(band/max(floor, 1e-12))
        checks["polyphony_three_pitches_present"] = all(x > 3 for x in tone_ratios.values())
        results["controlled_sf2_probes"] = {**measured, "pitch_band_to_nearby_floor_ratios": tone_ratios}
        summary["passed"] = all(checks.values())
        summary["playback_scope"] = "Containers probed and full files decoded by FFmpeg; human listening/device playback not claimed"
        summary["files"] = [{"path": str(p), "bytes": p.stat().st_size,
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                            for p in folder.iterdir() if p.suffix in (".mid", ".wav", ".mp3", ".flac")]
    except Exception as exc:
        summary.update(passed=False, failure=str(exc))
    write_json(folder / "summary.json", summary)
    print(json.dumps({"passed": summary["passed"], "summary": str(folder / "summary.json"), "checks": checks}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
