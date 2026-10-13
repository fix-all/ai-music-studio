from pathlib import Path
import json
from ..common import StudioError, required_file, new_output, run_process


def tool(config: dict, name: str) -> str:
    return str(required_file(config.get(name, ""), "ENGINE_MISSING"))


def probe(config: dict, source: str | Path) -> dict:
    p = required_file(source)
    result = run_process([tool(config, "ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)])
    return json.loads(result.stdout)


def verify_decode(config: dict, source: str | Path) -> dict:
    p = required_file(source)
    result = run_process([tool(config, "ffmpeg"), "-nostdin", "-v", "error", "-xerror", "-i", str(p), "-f", "null", "-"])
    return {"decoder": "ffmpeg", "full_decode_passed": True, "stderr": result.stderr}


def convert(config: dict, source: str, output: str, bitrate: str = "192k") -> dict:
    p = required_file(source)
    out = new_output(output)
    codecs = {".mp3": ["-c:a", "libmp3lame", "-b:a", bitrate], ".flac": ["-c:a", "flac"],
              ".wav": ["-c:a", "pcm_s24le"]}
    if out.suffix.lower() not in codecs:
        raise StudioError("FORMAT_UNSUPPORTED", "Export supports WAV, FLAC, MP3")
    run_process([tool(config, "ffmpeg"), "-nostdin", "-v", "error", "-n", "-i", str(p), "-map", "0:a:0",
                 *codecs[out.suffix.lower()], str(out)])
    return {"path": str(out), "probe": probe(config, out), "decode": verify_decode(config, out)}
