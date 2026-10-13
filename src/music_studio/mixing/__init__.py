from __future__ import annotations
import numpy as np
from scipy.signal import lfilter, fftconvolve
import soundfile as sf
from ..common import StudioError, number, new_output, required_file


def process_audio(audio: np.ndarray, rate: int, effects: dict) -> np.ndarray:
    unknown = set(effects) - {"eq", "reverb", "delay", "stereo_width", "gain_db", "fade_in", "fade_out", "peak_dbfs"}
    if unknown:
        raise StudioError("CONFIG_ERROR", f"Unknown effects: {sorted(unknown)}")
    x = np.asarray(audio, dtype=np.float64).copy()
    if x.ndim != 2 or x.shape[1] not in (1, 2) or not np.isfinite(x).all():
        raise StudioError("AUDIO_INVALID", "Mix requires finite mono or stereo audio")
    for band in effects.get("eq", []):
        frequency = number(band.get("frequency"), 20, rate*.49, "eq.frequency")
        q = number(band.get("q", 1), .1, 20, "eq.q")
        gain = number(band.get("gain_db", 0), -18, 18, "eq.gain_db")
        # RBJ peaking biquad: gain at centre, unity at DC and Nyquist.
        amplitude = 10**(gain/40)
        omega = 2*np.pi*frequency/rate
        alpha = np.sin(omega)/(2*q)
        b = [1+alpha*amplitude, -2*np.cos(omega), 1-alpha*amplitude]
        a = [1+alpha/amplitude, -2*np.cos(omega), 1-alpha/amplitude]
        x = lfilter(b, a, x, axis=0)
    delay = effects.get("delay", {})
    if delay:
        frames = round(number(delay.get("seconds", .2), .001, 2, "delay.seconds") * rate)
        wet = number(delay.get("wet", .1), 0, 1, "delay.wet")
        feedback = number(delay.get("feedback", .25), 0, .85, "delay.feedback")
        dry = x.copy()
        for tap in range(1, 9):
            offset = frames * tap
            if offset >= len(x): break
            x[offset:] += dry[:-offset] * wet * feedback**(tap-1)
    reverb = effects.get("reverb", {})
    if reverb:
        seconds = number(reverb.get("seconds", .6), .05, 3, "reverb.seconds")
        wet = number(reverb.get("wet", .08), 0, 1, "reverb.wet")
        rng = np.random.default_rng(0)
        length = round(seconds * rate)
        t = np.arange(length)/rate
        for ch in range(x.shape[1]):
            impulse = rng.normal(0, 1, length) * np.exp(-6.91*t/seconds)
            impulse[:round(.012*rate)] = 0
            impulse /= max(np.linalg.norm(impulse), 1e-12)
            x[:, ch] += wet * fftconvolve(x[:, ch], impulse)[:len(x)]
    width = number(effects.get("stereo_width", 1), 0, 2, "stereo_width")
    if x.shape[1] == 2:
        mid, side = (x[:, 0]+x[:, 1])/2, (x[:, 0]-x[:, 1])/2 * width
        x = np.column_stack((mid+side, mid-side))
    x *= 10**(number(effects.get("gain_db", 0), -60, 24, "gain_db")/20)
    for key in ("fade_in", "fade_out"):
        n = min(len(x), round(number(effects.get(key, 0), 0, 30, key)*rate))
        if n:
            ramp = np.linspace(0, 1, n)[:, None]
            if key == "fade_in": x[:n] *= ramp
            else: x[-n:] *= ramp[::-1]
    if "peak_dbfs" in effects:
        peak = float(np.max(np.abs(x)))
        ceiling = 10**(number(effects["peak_dbfs"], -24, -1, "peak_dbfs")/20)
        if peak > 0: x *= ceiling/peak
    if not np.isfinite(x).all() or np.max(np.abs(x)) >= 1:
        raise StudioError("MIX_CLIPPING", "Mix exceeds digital full scale; reduce gain or set peak_dbfs")
    return x


def mix(source: str, output: str, effects: dict) -> dict:
    path = required_file(source)
    info = sf.info(path)
    if info.duration > 3600:
        raise StudioError("AUDIO_TOO_LONG", "Mix is limited to 1 hour")
    audio, rate = sf.read(path, always_2d=True)
    result = process_audio(audio, rate, effects)
    out = new_output(output)
    if out.suffix.lower() != ".wav":
        raise StudioError("FORMAT_UNSUPPORTED", "mix produces WAV")
    with sf.SoundFile(str(out), "x", samplerate=rate, channels=result.shape[1], subtype="PCM_24", format="WAV") as f:
        f.write(result)
    return {"path": str(out), "effects": effects, "sample_rate": rate, "channels": result.shape[1],
            "tail_policy": "effects use existing audio tail; render with enough --tail seconds"}
