"""Measured quality gates; no claim of automatic artistic mastering."""
from pathlib import Path
import math
import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly
import soundfile as sf
from ..common import StudioError, required_file
from ..export import verify_decode


def db(value: float) -> float | None:
    return 20 * math.log10(value) if value > 0 else None


def analyze(config: dict, source: str | Path, decode: bool = True) -> dict:
    path = required_file(source)
    try:
        info = sf.info(path)
        if info.duration > 3600:
            raise StudioError("AUDIO_TOO_LONG", "Analysis is limited to 1 hour")
        audio, rate = sf.read(path, dtype="float64", always_2d=True)
    except (RuntimeError, sf.LibsndfileError) as exc:
        raise StudioError("AUDIO_DECODE_FAILED", f"Cannot read {path}", str(exc)) from exc
    if not audio.size:
        raise StudioError("AUDIO_EMPTY", "No audio frames")
    if not np.isfinite(audio).all():
        raise StudioError("AUDIO_NONFINITE", "Audio has NaN or infinity")
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    channel_rms = np.sqrt(np.mean(audio ** 2, axis=0))
    true_peak = float(np.max(np.abs(resample_poly(audio, 4, 1, axis=0))))
    lufs = None
    if len(audio) / rate >= .4 and audio.shape[1] <= 5:
        loudness = float(pyln.Meter(rate).integrated_loudness(audio))
        lufs = loudness if math.isfinite(loudness) else None
    issues = []
    if rms < 1e-5: issues.append("SILENT")
    if np.any(channel_rms < 1e-6): issues.append("SILENT_CHANNEL")
    clipped = int(np.sum(np.abs(audio) >= 0.99997))
    if clipped: issues.append("CLIPPING")
    if true_peak >= 1: issues.append("INTERSAMPLE_PEAK")
    if len(audio) / rate < .1: issues.append("TOO_SHORT")
    return {"path": str(path), "format": info.format, "subtype": info.subtype, "duration_seconds": len(audio)/rate,
            "sample_rate": rate, "channels": audio.shape[1], "frames": len(audio),
            "sample_peak": peak, "sample_peak_dbfs": db(peak), "rms_dbfs": db(rms),
            "true_peak_dbtp_estimate": db(true_peak), "true_peak_method": "4x scipy resample_poly (estimate)",
            "integrated_lufs": lufs, "clipped_samples": clipped, "channel_rms": channel_rms.tolist(),
            "quality_passed": not issues, "issues": issues,
            "decode": verify_decode(config, path) if decode else {"full_decode_passed": False, "reason": "not requested"}}
