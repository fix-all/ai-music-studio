"""Exercise the official saved downloader without network or model dependencies."""
import importlib.util
from pathlib import Path
import pytest
from music_studio.common import root_path


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, root_path()/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_official_helper_cannot_fallback_to_network(tmp_path, monkeypatch):
    guard = load("offline_guard", "scripts/acestep_offline_server.py")
    official = load("official_helper", "docs/evidence/acestep-api-model-download-v0.1.8.py")
    guard.block_module_downloads(official, ["download_from_huggingface", "download_from_modelscope"])
    monkeypatch.setenv("ACESTEP_DOWNLOAD_SOURCE", "huggingface")
    with pytest.raises(guard.OfflineModelError):
        official.ensure_model_downloaded("acestep-v15-turbo", str(tmp_path))
    assert not list(tmp_path.iterdir())
    # Already provisioned local models retain the normal no-download path.
    local = tmp_path/"acestep-v15-turbo"
    local.mkdir(); (local/"model.safetensors").write_bytes(b"test fixture, not weights")
    assert official.ensure_model_downloaded("acestep-v15-turbo", str(tmp_path)) == str(local)


def test_upstream_drift_fails_closed():
    guard = load("offline_guard_drift", "scripts/acestep_offline_server.py")
    import types
    with pytest.raises(guard.OfflineModelError):
        guard.block_module_downloads(types.ModuleType("changed_upstream"), ["renamed_function"])
