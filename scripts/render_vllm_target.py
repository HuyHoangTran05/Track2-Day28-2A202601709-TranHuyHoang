"""Render the Prometheus file_sd target for the configured vLLM endpoint.

The inference endpoint moves: on a workstation it is a local port, and on a
Kaggle/GPU session it is a tunnel hostname issued at run time. A run-time
hostname must not enter Git, so the scrape target is generated from
``LAB28_VLLM_BASE_URL`` into a gitignored file that Prometheus discovers.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from urllib.parse import urlsplit

TARGET_FILE = pathlib.Path("monitoring/targets/vllm.json")
DEFAULT_BASE_URL = "http://host.docker.internal:8001/v1"


def target_entry(base_url: str) -> dict[str, object]:
    """Turn an OpenAI-style base URL into one Prometheus file_sd entry.

    ``__scheme__`` is carried as a label because a tunnel serves HTTPS on 443
    while a local endpoint serves plain HTTP, and a scrape config can only
    declare one scheme for the whole job.
    """
    parts = urlsplit(base_url)
    if not parts.scheme or not parts.hostname:
        raise SystemExit(f"LAB28_VLLM_BASE_URL is not an absolute URL: {base_url!r}")

    port = parts.port or (443 if parts.scheme == "https" else 80)
    return {
        "targets": [f"{parts.hostname}:{port}"],
        "labels": {"__scheme__": parts.scheme, "lab28_endpoint": "vllm"},
    }


def main() -> int:
    base_url = os.getenv("LAB28_VLLM_BASE_URL", DEFAULT_BASE_URL)
    entry = target_entry(base_url)

    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARGET_FILE.write_text(json.dumps([entry], indent=2) + "\n", encoding="utf-8")

    print(f"wrote {TARGET_FILE} -> {entry['targets'][0]} ({entry['labels']['__scheme__']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
