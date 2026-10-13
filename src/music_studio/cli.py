from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import logging
import sys
import uuid
from .common import StudioError, settings, load_yaml, root_path, new_output, write_json, log


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="music-studio", description="Local MIDI/SF2 production and isolated generative music services. Output: JSON; logs: stderr and outputs/logs.")
    p.add_argument("--settings", help="Studio YAML registry (default config/local.yaml or config/studio.yaml)")
    p.add_argument("--verbose", action="store_true", help="Include debug details in the log")
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("doctor", help="Check actual core engine/library readiness")
    s.add_parser("list-engines", help="Report ready, disabled, unavailable or unimplemented engines")
    s.add_parser("list-instruments", help="Load registered SF2s and enumerate real banks/programs (zero based)")
    c = s.add_parser("compose", help="Create editable type-1 MIDI from a declarative plan; no model download")
    c.add_argument("--config", required=True, help="Composition YAML")
    c.add_argument("--output", help="Override MIDI output path (must not exist)")
    r = s.add_parser("render", help="Render MIDI with FluidSynth and registered SF2 to PCM24 stereo WAV")
    r.add_argument("--input", required=True, help="Source .mid")
    r.add_argument("--output", required=True, help="New .wav path")
    r.add_argument("--soundfont", help="Registered SoundFont id")
    r.add_argument("--sample-rate", type=int, default=44100, help="Hz (default 44100)")
    r.add_argument("--tail", type=float, default=2.0, help="Release tail seconds (default 2)")
    r.add_argument("--gain", type=float, default=.4, help="FluidSynth gain; reduce if clipping (default 0.4)")
    a = s.add_parser("analyze", help="Measure audio, check silence/clipping and fully decode with FFmpeg")
    a.add_argument("--input", required=True)
    a.add_argument("--report", help="Save measured JSON report (must not exist)")
    m = s.add_parser("mix", help="Apply EQ, reverb, delay, stereo width and fades to WAV")
    m.add_argument("--input", required=True)
    m.add_argument("--output", required=True)
    m.add_argument("--config", default="config/mixing.yaml", help="Effects YAML")
    e = s.add_parser("export", help="Convert audio to WAV, FLAC or MP3, then verify full decode")
    e.add_argument("--input", required=True)
    e.add_argument("--output", required=True)
    e.add_argument("--bitrate", choices=["128k", "192k", "256k", "320k"], default="192k", help="MP3 bitrate")
    g = s.add_parser("generate", help="Submit to independently deployed local ACE-Step REST API; requires enabled engine")
    g.add_argument("--config", required=True)
    g.add_argument("--output", help="Override WAV output path")
    return p


def execute(args, config: dict) -> dict:
    from .diagnostics import doctor, engines, instruments
    from .composition import compose
    from .synthesis.fluidsynth import render
    from .mastering import analyze
    from .mixing import mix
    from .export import convert
    from .generation.acestep import AceStep
    match args.command:
        case "doctor": return doctor(config)
        case "list-engines": return {"engines": engines(config)}
        case "list-instruments": return {"soundfonts": instruments(config)}
        case "compose": return compose(load_yaml(args.config), args.output)
        case "render": return render(config, args.input, args.output, args.soundfont, args.sample_rate, args.tail, args.gain)
        case "mix": return mix(args.input, args.output, load_yaml(args.config))
        case "export": return convert(config, args.input, args.output, args.bitrate)
        case "analyze":
            result = analyze(config, args.input)
            if args.report: write_json(new_output(args.report), result)
            return result
        case "generate":
            spec = config.get("generation", {})
            if spec.get("engine", "acestep-rest") != "acestep-rest":
                raise StudioError("ENGINE_UNKNOWN", f"No adapter for {spec.get('engine')}")
            plan = load_yaml(args.config)
            result = AceStep(spec).generate(plan, args.output or plan.get("output", "outputs/generated.wav"))
            result["analysis"] = analyze(config, result["path"])
            result["quality_passed"] = result["analysis"]["quality_passed"]
            return result
    raise StudioError("COMMAND_UNKNOWN", "Unknown command")


def main(argv: list[str] | None = None) -> int:
    run_id = str(uuid.uuid4())
    log_path = root_path() / "outputs/logs" / (run_id + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stderr), logging.FileHandler(log_path, encoding="utf-8")], force=True)
    command = None
    try:
        args = parser().parse_args(argv)
        command = args.command
        if args.verbose: logging.getLogger().setLevel(logging.DEBUG)
        log.info("Starting %s; run_id=%s", command, run_id)
        result = execute(args, settings(args.settings))
        passed = result.get("quality_passed", result.get("structured_pipeline_ready", True))
        code = 0 if passed else 3
        response = {"ok": bool(passed), "status": "succeeded" if passed else "failed", "result": result,
                    "error": None if passed else {"code": "QUALITY_OR_READINESS_FAILED", "message": "Inspect result checks/issues"}}
    except StudioError as exc:
        code = 2
        log.error("%s: %s", exc.code, exc)
        response = {"ok": False, "status": "failed", "result": None,
                    "error": {"code": exc.code, "message": str(exc), "details": exc.details}}
    except SystemExit as exc:
        # Help retains argparse's conventional text; invalid arguments receive JSON as well.
        if exc.code == 0: return 0
        code = 2
        response = {"ok": False, "status": "failed", "result": None, "error": {"code": "ARGUMENT_ERROR", "message": "Invalid CLI arguments; see --help"}}
    except KeyboardInterrupt:
        code = 130
        response = {"ok": False, "status": "interrupted", "result": None, "error": {"code": "INTERRUPTED", "message": "User interrupted operation"}}
    except Exception as exc:
        code = 2
        log.exception("Unexpected failure")
        response = {"ok": False, "status": "failed", "result": None, "error": {"code": "UNEXPECTED_ERROR", "message": str(exc), "type": type(exc).__name__}}
    response.update(schema_version=1, run_id=run_id, command=command,
                    timestamp=datetime.now(timezone.utc).isoformat(), log_path=str(log_path))
    write_json(log_path.with_suffix(".json"), response)
    print(json.dumps(response, ensure_ascii=True, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
