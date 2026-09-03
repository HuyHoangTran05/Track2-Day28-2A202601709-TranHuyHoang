"""Capture a reversible Feast outage with readiness and no-data-loss proof."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from lab28_platform import delta_store
from lab28_platform.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = REPO_ROOT / "evidence" / "incident-recovery.json"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _readiness(settings: Settings) -> dict[str, Any]:
    response = httpx.get(f"{settings.api_url.rstrip('/')}/ready", timeout=15.0)
    response.raise_for_status()
    return dict(response.json())


def _feast_ready(report: dict[str, Any]) -> bool:
    return next(
        component["ready"]
        for component in report["components"]
        if component["name"] == "feast"
    )


def _wait_for_feast(settings: Settings, expected: bool, timeout: float = 60.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: object = None
    while time.monotonic() < deadline:
        try:
            report = _readiness(settings)
            last = report
            if _feast_ready(report) is expected:
                return report
        except Exception as error:
            last = f"{type(error).__name__}: {error}"
        time.sleep(1.0)
    raise RuntimeError(f"Feast readiness did not become {expected}; last observed: {last}")


def _state(settings: Settings) -> dict[str, Any]:
    response = httpx.get(
        f"{settings.qdrant.url.rstrip('/')}/collections/{settings.qdrant.collection}",
        timeout=5.0,
    )
    response.raise_for_status()
    return {
        "feedback_version": delta_store.current_version(settings.feedback_table),
        "feedback_rows": len(delta_store.read_rows(settings.feedback_table)),
        "document_version": delta_store.current_version(settings.document_table),
        "document_rows": len(delta_store.read_rows(settings.document_table)),
        "qdrant_points": response.json()["result"]["points_count"],
    }


def _compose(*args: str) -> None:
    subprocess.run(
        ["docker", "compose", "--env-file", "ports.template", *args],
        cwd=REPO_ROOT,
        check=True,
        timeout=120.0,
    )


def main() -> None:
    settings = Settings.from_env()
    before = _state(settings)
    baseline = _readiness(settings)
    started_at = _timestamp()

    _compose("stop", "feast")
    try:
        during = _wait_for_feast(settings, False)
        observed_at = _timestamp()
    finally:
        _compose("start", "feast")

    recovered = _wait_for_feast(settings, True)
    recovered_at = _timestamp()
    after = _state(settings)
    protected = ("feedback_rows", "document_rows", "qdrant_points")

    payload = {
        "scenario": "optional Feast outage",
        "hypothesis": (
            "readiness remains degraded and names Feast; recovery restores the Feast probe "
            "without losing or duplicating Delta/Qdrant state"
        ),
        "injected_at": started_at,
        "observed_at": observed_at,
        "recovered_at": recovered_at,
        "injection": "docker compose stop feast",
        "recovery": "docker compose start feast",
        "before_state": before,
        "baseline_readiness": baseline,
        "during_readiness": during,
        "after_state": after,
        "final_readiness": recovered,
        "no_data_loss": all(after[field] == before[field] for field in protected),
        "no_duplicate_rows": all(after[field] == before[field] for field in protected),
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
