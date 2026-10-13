from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import mido
import numpy as np
import pytest
import soundfile as sf
from music_studio.common import StudioError, load_yaml, settings
from music_studio.composition import compose
from music_studio.mastering import analyze
from music_studio.mixing import process_audio
from music_studio.synthesis.fluidsynth import FluidSynth


def test_composition_timing_and_channels(tmp_path):
    plan = load_yaml("config/example.yaml")
    out = tmp_path / "score.mid"
    data = compose(plan, str(out))
    midi = mido.MidiFile(out)
    assert midi.type == 1 and midi.length == 16 and data["notes"] == 56
    channels = [{m.channel for m in t if not m.is_meta} for t in midi.tracks[1:]]
    assert channels == [{0}, {1}]
    assert all(sum(m.time for m in t) == 15360 for t in midi.tracks)


def test_meter_and_absolute_notes(tmp_path):
    data = compose({"bars": 8, "bpm": 90, "time_signature": [6, 8], "tracks": [
        {"notes": [{"beat": 0, "duration": 24, "pitch": 60}]}]}, str(tmp_path / "meter.mid"))
    assert abs(data["duration_seconds"] - 16) < .0001


@pytest.mark.parametrize("change", ["duration", "channel", "velocity", "pitch", "meter"])
def test_bad_plan_rejected(tmp_path, change):
    plan = deepcopy(load_yaml("config/example.yaml"))
    if change == "duration": plan["tracks"][0]["notes"][0]["duration"] = 10
    if change == "channel": plan["tracks"][1]["channel"] = 0
    if change == "velocity": plan["tracks"][0]["notes"][0]["velocity"] = 128
    if change == "pitch": plan["tracks"][0]["notes"][0]["pitch"] = 125
    if change == "meter": plan["time_signature"] = [4, 3]
    with pytest.raises(StudioError): compose(plan, str(tmp_path / "bad.mid"))
    assert not (tmp_path / "bad.mid").exists()


def test_existing_output_preserved(tmp_path):
    output = tmp_path / "existing.mid"
    output.write_bytes(b"keep me")
    with pytest.raises(StudioError, match="overwrite"):
        compose(load_yaml("config/example.yaml"), str(output))
    assert output.read_bytes() == b"keep me"


def test_sf2_registry_hash_and_missing_dll():
    config = deepcopy(settings())
    config["soundfonts"][0]["sha256"] = "0"*64
    with pytest.raises(StudioError) as exc: FluidSynth(config)
    assert exc.value.code == "SOUNDFONT_HASH_MISMATCH"
    config = deepcopy(settings())
    config["fluidsynth_library"] = "missing.dll"
    with pytest.raises(StudioError) as exc: FluidSynth(config)
    assert exc.value.code == "ENGINE_MISSING"


def test_analysis_detects_silence_clipping_and_stereo_fault(tmp_path):
    rate = 44100
    for name, audio, expected in [
        ("silence", np.zeros((rate, 2)), "SILENT"),
        ("clipped", np.ones((rate, 2)), "CLIPPING"),
        ("silent-channel", np.column_stack((np.sin(np.arange(rate)*.05)*.2, np.zeros(rate))), "SILENT_CHANNEL")]:
        path = tmp_path / (name + ".wav")
        sf.write(path, audio, rate, subtype="FLOAT")
        result = analyze(settings(), path)
        assert not result["quality_passed"] and expected in result["issues"]
        assert result["decode"]["full_decode_passed"]


def test_effects_change_audio_and_retain_headroom():
    rate = 44100
    tone = np.sin(2*np.pi*250*np.arange(rate)/rate) * .1
    source = np.column_stack((tone, tone*.8))
    out = process_audio(source, rate, load_yaml("config/mixing.yaml"))
    assert out.shape == source.shape and np.isfinite(out).all()
    assert not np.allclose(out, source)
    assert abs(np.max(np.abs(out))-10**(-3/20)) < 1e-8
    assert np.all(out[0] == 0) and np.all(out[-1] == 0)


def test_unknown_effect_fails():
    with pytest.raises(StudioError): process_audio(np.zeros((100, 2)), 44100, {"typo": 1})


@pytest.mark.parametrize("gain", [-6, 6])
def test_eq_measured_gain_at_centre(gain):
    rate = 44100
    tone = .1*np.sin(2*np.pi*1000*np.arange(rate)/rate)[:, None]
    out = process_audio(tone, rate, {"eq": [{"frequency": 1000, "q": 1, "gain_db": gain}]})
    measured_db = 20*np.log10(np.sqrt(np.mean(out[5000:]**2))/np.sqrt(np.mean(tone[5000:]**2)))
    assert abs(measured_db-gain) < .05


def test_delay_and_reverb_have_measured_tails():
    rate = 44100
    impulse = np.zeros((rate, 2)); impulse[0] = .1
    delayed = process_audio(impulse, rate, {"delay": {"seconds": .1, "wet": .5, "feedback": .3}})
    assert abs(delayed[4410, 0]-.05) < 1e-8
    assert abs(delayed[8820, 0]-.015) < 1e-8
    reverbed = process_audio(impulse, rate, {"reverb": {"seconds": .5, "wet": .2}})
    assert np.linalg.norm(reverbed[1000:15000]) > 1e-4
    assert np.max(np.abs(reverbed[30000:])) < 1e-8


def test_stereo_width_zero_collapses_to_mono():
    source = np.random.default_rng(42).normal(0, .01, (500, 2))
    out = process_audio(source, 44100, {"stereo_width": 0})
    assert np.allclose(out[:, 0], out[:, 1])
    assert np.allclose(out[:, 0], source.mean(axis=1))


def test_cli_errors_are_machine_readable(tmp_path):
    result = subprocess.run([sys.executable, "-m", "music_studio.cli", "render", "--input", "missing.mid", "--output", str(tmp_path/"x.wav")], capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert result.returncode == 2 and data["status"] == "failed" and data["error"]["code"] == "INPUT_MISSING"
    assert Path(data["log_path"]).is_file()
