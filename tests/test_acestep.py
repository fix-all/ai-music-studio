"""Contract tests with a mock HTTP server; these do not validate any AI model."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import io
import json
import numpy as np
import pytest
import soundfile as sf
from music_studio.common import StudioError
from music_studio.generation.acestep import AceStep


@contextmanager
def server(mode="success"):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.path == "/health": self.send_json({"status": "ok", "service": "ACE-Step API", "version": "1.0"})
            elif mode == "invalid-audio":
                self.send_response(200); self.end_headers(); self.wfile.write(b"not audio")
            else:
                buf = io.BytesIO()
                sf.write(buf, np.sin(np.arange(44100)*.02)*.1, 44100, format="WAV")
                self.send_response(200); self.end_headers(); self.wfile.write(buf.getvalue())
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, body))
            if self.path == "/release_task": self.send_json({"task_id": "test-123", "status": "queued"})
            else:
                status = 2 if mode == "failed" else 0 if mode == "timeout" else 1
                self.send_json([{"task_id": "test-123", "status": status,
                                 "result": json.dumps([{"file": "/v1/audio?path=test.wav"}])}])
        def send_json(self, data):
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"code": 200, "error": None, "data": data}).encode())
    svc = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=svc.serve_forever, daemon=True)
    worker.start()
    try: yield {"enabled": True, "base_url": f"http://127.0.0.1:{svc.server_port}"}, calls
    finally: svc.shutdown(); svc.server_close(); worker.join()


def test_async_contract_and_download(tmp_path):
    with server() as (config, calls):
        out = tmp_path/"test.wav"
        result = AceStep(config).generate({"prompt": "neutral test", "duration": 10, "thinking": False}, str(out))
        audio, rate = sf.read(out)
        assert rate == 44100 and np.max(np.abs(audio)) > .05
        assert result["task_id"] == "test-123"
        assert calls[0][0] == "/release_task" and calls[0][1]["audio_format"] == "wav"
        assert calls[0][1]["audio_duration"] == 10 and calls[0][1]["batch_size"] == 1
        assert not calls[0][1]["use_random_seed"]
        assert calls[1][1] == {"task_id_list": ["test-123"]}


@pytest.mark.parametrize("mode,code", [("failed", "GENERATION_FAILED"), ("timeout", "GENERATION_TIMEOUT"), ("invalid-audio", "GENERATION_INVALID_AUDIO")])
def test_failures_preserve_receipt(tmp_path, mode, code):
    with server(mode) as (config, calls):
        output = tmp_path/"failed.wav"
        with pytest.raises(StudioError) as exc:
            AceStep(config).generate({"prompt": "test", "timeout": .08, "poll_interval": .01}, str(output))
        assert exc.value.code == code and not output.exists()
        assert json.loads((tmp_path/"failed.wav.task.json").read_text())["task_id"] == "test-123"


def test_disabled_and_nonlocal_services_rejected(tmp_path):
    with pytest.raises(StudioError) as exc:
        AceStep({"enabled": False}).generate({"prompt": "test"}, str(tmp_path/"a.wav"))
    assert exc.value.code == "ENGINE_DISABLED"
    with pytest.raises(StudioError): AceStep({"base_url": "https://example.com"})
