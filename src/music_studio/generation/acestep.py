from __future__ import annotations
import json
import os
import time
from urllib.parse import urlparse, urljoin
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from ..common import StudioError, number, integer, new_output, write_json, log


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StudioError("SERVICE_URL_REJECTED", "ACE-Step redirects are not supported")


class AceStep:
    """Adapter for the official v0.1.8 asynchronous REST contract. Local service only."""
    def __init__(self, config: dict):
        self.config = config
        self.base = str(config.get("base_url", "http://127.0.0.1:8001")).rstrip("/")
        url = urlparse(self.base)
        if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1") or url.path not in ("", "/") or url.username or url.query or url.fragment:
            raise StudioError("SERVICE_URL_REJECTED", "ACE-Step base_url must be a local loopback HTTP origin")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.timeout = number(config.get("request_timeout", 15), .05, 120, "request_timeout")

    def request(self, endpoint: str, payload: dict | None = None, binary: bool = False) -> bytes | dict:
        url = urljoin(self.base + "/", endpoint)
        if urlparse(url).netloc != urlparse(self.base).netloc:
            raise StudioError("SERVICE_URL_REJECTED", "Cross-origin audio URL rejected")
        headers = {"Accept": "application/json"}
        key = os.environ.get(self.config.get("api_key_env", "ACESTEP_API_KEY"))
        if key:
            headers["Authorization"] = "Bearer " + key
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        try:
            with self.opener.open(Request(url, data=data, headers=headers), timeout=self.timeout) as response:
                if urlparse(response.url).netloc != urlparse(self.base).netloc:
                    raise StudioError("SERVICE_URL_REJECTED", "Cross-origin redirect rejected")
                limit = 512*1024*1024 if binary else 8*1024*1024
                content = response.read(limit+1)
                if len(content) > limit:
                    raise StudioError("SERVICE_RESPONSE_TOO_LARGE", "ACE-Step response exceeds size limit")
        except HTTPError as exc:
            raise StudioError("SERVICE_HTTP_ERROR", f"ACE-Step returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise StudioError("SERVICE_UNAVAILABLE", f"Cannot reach ACE-Step at {self.base}", type(exc).__name__) from exc
        if binary:
            return content
        try:
            body = json.loads(content)
            if not isinstance(body, dict) or body.get("code") != 200 or body.get("error"):
                raise StudioError("SERVICE_PROTOCOL_ERROR", "ACE-Step returned an unsuccessful response")
            return body["data"]
        except (ValueError, KeyError) as exc:
            raise StudioError("SERVICE_PROTOCOL_ERROR", "Invalid ACE-Step JSON envelope") from exc

    def health(self) -> dict:
        if not self.config.get("enabled", False):
            return {"state": "disabled", "reason": "Weights and model service are not deployed", "base_url": self.base}
        result = self.request("/health")
        if not isinstance(result, dict) or result.get("status") != "ok" or "ACE-Step" not in result.get("service", ""):
            raise StudioError("SERVICE_PROTOCOL_ERROR", "Endpoint is not a healthy ACE-Step API")
        return {"state": "service_healthy", "service": result, "generation_verified": False}

    def generate(self, plan: dict, output: str) -> dict:
        if not self.config.get("enabled", False):
            raise StudioError("ENGINE_DISABLED", "ACE-Step is disabled. Deploy the separate model service, then enable it in config/local.yaml.")
        prompt = plan.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise StudioError("CONFIG_ERROR", "generation.prompt requires nonempty text")
        output_path = new_output(output)
        if output_path.suffix.lower() != ".wav":
            raise StudioError("FORMAT_UNSUPPORTED", "Generation requests WAV output")
        record_path = new_output(str(output_path) + ".task.json")
        duration = number(plan.get("duration", 10), 10, 600, "duration")
        seed = integer(plan.get("seed", 1234), 0, 2147483647, "seed")
        timeout = number(plan.get("timeout", 600), .05, 7200, "timeout")
        poll = number(plan.get("poll_interval", 2), .01, 30, "poll_interval")
        if not isinstance(plan.get("thinking", False), bool):
            raise StudioError("CONFIG_ERROR", "generation.thinking must be true or false")
        payload = {"prompt": prompt, "lyrics": plan.get("lyrics", "[Instrumental]"),
                   "audio_duration": duration, "audio_format": "wav", "seed": seed,
                   "use_random_seed": False, "batch_size": 1, "thinking": plan.get("thinking", False),
                   "use_cot_caption": False, "use_cot_language": False,
                   "bpm": number(plan.get("bpm", 120), 20, 300, "bpm"),
                   "key_scale": str(plan.get("key_scale", "C Major")), "time_signature": "4"}
        self.health()
        start = time.monotonic()
        submitted = self.request("/release_task", payload)
        if not isinstance(submitted, dict) or not isinstance(submitted.get("task_id"), str):
            raise StudioError("SERVICE_PROTOCOL_ERROR", "Submission returned no task_id")
        task_id = submitted["task_id"]
        write_json(record_path, {"task_id": task_id, "base_url": self.base, "request": payload,
                                 "note": "Submission receipt; inspect /query_result after timeout. Do not resubmit blindly."})
        log.info("ACE-Step task submitted: %s", task_id)
        while time.monotonic()-start < timeout:
            rows = self.request("/query_result", {"task_id_list": [task_id]})
            if not isinstance(rows, list):
                raise StudioError("SERVICE_PROTOCOL_ERROR", "query_result data must be an array", {"task_id": task_id})
            matches = [row for row in rows if isinstance(row, dict) and row.get("task_id") == task_id]
            if len(matches) != 1:
                raise StudioError("SERVICE_PROTOCOL_ERROR", "query_result omitted or duplicated task", {"task_id": task_id})
            row = matches[0]
            if row.get("status") == 2:
                raise StudioError("GENERATION_FAILED", "ACE-Step generation failed", {"task_id": task_id})
            if row.get("status") == 1:
                try:
                    results = json.loads(row["result"]) if isinstance(row["result"], str) else row["result"]
                    file_url = results[0]["file"]
                    if not isinstance(file_url, str) or not file_url.startswith("/v1/audio?"):
                        raise ValueError("Expected /v1/audio? URL")
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    raise StudioError("SERVICE_PROTOCOL_ERROR", "Invalid completed audio result", {"task_id": task_id}) from exc
                content = self.request(file_url, binary=True)
                # Verify actual container before saving; downstream analyze checks samples and full decode.
                if not (content[:4] == b"RIFF" and content[8:12] == b"WAVE"):
                    raise StudioError("GENERATION_INVALID_AUDIO", "Service returned no WAV container", {"task_id": task_id})
                with output_path.open("xb") as f:
                    f.write(content)
                return {"path": str(output_path), "task_id": task_id, "receipt": str(record_path),
                        "service_result": results, "engine": "acestep-rest"}
            if row.get("status") != 0:
                raise StudioError("SERVICE_PROTOCOL_ERROR", "Unknown task status", {"task_id": task_id})
            time.sleep(min(poll, max(0, timeout-(time.monotonic()-start))))
        raise StudioError("GENERATION_TIMEOUT", "ACE-Step task still pending; receipt preserves task_id", {"task_id": task_id, "receipt": str(record_path)})
