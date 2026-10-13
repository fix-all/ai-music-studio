"""Run the pinned external ACE-Step service with inspected auto-download paths disabled.

This module has no dependency on the studio venv. Use the external service Python.
"""
import importlib
import os
from pathlib import Path
import sys


class OfflineModelError(RuntimeError):
    pass


def deny_download(*args, **kwargs):
    raise OfflineModelError("AI Music Studio blocks automatic model downloads. Provision approved weights separately.")


def block_module_downloads(module, names):
    # Fail closed if upgrading upstream changes a download entry point.
    for name in names:
        if not callable(getattr(module, name, None)):
            raise OfflineModelError(f"Unrecognised upstream download API: {module.__name__}.{name}")
    for name in names:
        setattr(module, name, deny_download)


def main():
    repo = Path.cwd()
    if not (repo / "acestep/api_server.py").is_file():
        raise OfflineModelError("Run from the separately installed official ACE-Step checkout")
    sys.path.insert(0, str(repo))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["ACESTEP_DOWNLOAD_SOURCE"] = "huggingface"
    for module_name, names in {
        "acestep.api.model_download": ["download_from_huggingface", "download_from_modelscope"],
        "acestep.model_downloader": ["_download_from_huggingface_internal", "_download_from_modelscope_internal"],
    }.items():
        block_module_downloads(importlib.import_module(module_name), names)
    # Upstream uses one uvicorn worker and in-process model initialisation.
    importlib.import_module("acestep.api_server").main()


if __name__ == "__main__":
    main()
