from __future__ import annotations
import importlib.metadata as metadata
import platform
from .common import StudioError, resolve, required_file, run_process
from .synthesis.fluidsynth import FluidSynth
from .generation.acestep import AceStep


def engines(config: dict) -> list[dict]:
    result = []
    try:
        with FluidSynth(config) as synth:
            presets = synth.presets()
        version = run_process([str(required_file(config.get("fluidsynth_cli", ""))), "--version"], timeout=15).stdout.splitlines()[0]
        result.append({"id": "fluidsynth", "state": "ready", "version": version, "presets": len(presets), "api": "C API via ctypes"})
    except (StudioError, OSError) as exc:
        result.append({"id": "fluidsynth", "state": "unavailable", "reason": str(exc)})
    try:
        state = AceStep(config.get("generation", {})).health()
        result.append({"id": "acestep-rest", **state})
    except StudioError as exc:
        result.append({"id": "acestep-rest", "state": "unavailable", "reason": str(exc), "code": exc.code})
    result.append({"id": "sfizz", "state": "not_integrated", "reason": "SFZ requires a separate native renderer/host adapter"})
    return result


def instruments(config: dict) -> list[dict]:
    result = []
    for entry in config.get("soundfonts", []):
        item = {**entry, "exists": resolve(entry.get("path", "")).is_file()}
        if entry.get("format", "sf2") != "sf2":
            item.update(state="registry_only", render_supported=False)
        else:
            try:
                with FluidSynth(config, entry["id"]) as synth:
                    item.update(state="ready", render_supported=True, presets=synth.presets())
            except StudioError as exc:
                item.update(state="unavailable", reason=str(exc), code=exc.code)
        result.append(item)
    return result


def doctor(config: dict) -> dict:
    checks = []
    for name in ("ffmpeg", "ffprobe"):
        try:
            path = required_file(config.get(name, ""), "ENGINE_MISSING")
            version = run_process([str(path), "-version"], timeout=15).stdout.splitlines()[0]
            checks.append({"id": name, "state": "ready", "path": str(path), "version": version})
        except StudioError as exc:
            checks.append({"id": name, "state": "unavailable", "reason": str(exc)})
    engine_rows = engines(config)
    ready = all(c["state"] == "ready" for c in checks) and engine_rows[0]["state"] == "ready"
    return {"structured_pipeline_ready": ready, "python": platform.python_version(), "platform": platform.platform(),
            "checks": checks, "engines": engine_rows,
            "packages": {p: metadata.version(p) for p in ("ai-music-studio", "numpy", "scipy", "soundfile", "mido", "PyYAML", "pyloudnorm")},
            "scope": "Core readiness; run scripts/smoke-test.py for actual audio validation"}
