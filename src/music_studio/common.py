from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml

log = logging.getLogger("music_studio")


class StudioError(Exception):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code, self.details = code, details


def root_path() -> Path:
    return Path(os.environ.get("MUSIC_STUDIO_HOME", Path(__file__).resolve().parents[2])).resolve()


def resolve(value: str | Path) -> Path:
    p = Path(os.path.expandvars(str(value))).expanduser()
    return p.resolve() if p.is_absolute() else (root_path() / p).resolve()


def load_yaml(path: str | Path) -> dict:
    p = resolve(path)
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        raise StudioError("CONFIG_ERROR", f"Cannot read YAML: {p}", str(exc)) from exc
    if not isinstance(data, dict):
        raise StudioError("CONFIG_ERROR", f"Expected a YAML mapping: {p}")
    if data.get("schema_version", 1) != 1:
        raise StudioError("CONFIG_VERSION_UNSUPPORTED", "Only schema_version: 1 is supported")
    return data


def settings(path: str | None = None) -> dict:
    if path:
        return load_yaml(path)
    local = root_path() / "config/local.yaml"
    return load_yaml(local if local.exists() else "config/studio.yaml")


def new_output(value: str | Path) -> Path:
    p = resolve(value)
    if p.exists():
        raise StudioError("OUTPUT_EXISTS", f"Refusing to overwrite: {p}. Choose a new output path.")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, data: Any) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def run_process(args: list[str], timeout: float = 180) -> subprocess.CompletedProcess:
    log.info("Running %s", args[0])
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StudioError("PROCESS_ERROR", f"Could not run {args[0]}", str(exc)) from exc
    if result.returncode:
        raise StudioError("PROCESS_FAILED", f"{Path(args[0]).name} exited {result.returncode}", result.stderr[-4000:])
    return result


def required_file(value: str | Path, code: str = "INPUT_MISSING") -> Path:
    p = resolve(value)
    if not p.is_file():
        raise StudioError(code, f"File not found: {p}")
    return p


def number(value: Any, low: float, high: float, name: str) -> float:
    import math
    if isinstance(value, bool):
        raise StudioError("CONFIG_ERROR", f"{name} must be numeric")
    try:
        n = float(value)
    except (ValueError, TypeError) as exc:
        raise StudioError("CONFIG_ERROR", f"{name} must be numeric") from exc
    if not math.isfinite(n) or not low <= n <= high:
        raise StudioError("CONFIG_ERROR", f"{name} must be between {low} and {high}")
    return n


def integer(value: Any, low: int, high: int, name: str) -> int:
    n = number(value, low, high, name)
    if n != int(n):
        raise StudioError("CONFIG_ERROR", f"{name} must be an integer")
    return int(n)
