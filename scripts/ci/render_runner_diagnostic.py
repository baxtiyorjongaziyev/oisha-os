"""Classify GitHub Actions run metadata without exposing secrets."""
from __future__ import annotations

import json
import sys
from typing import Any


CLASSIFICATIONS = {
    "queued_waiting_for_runner",
    "runner_or_account_before_step_one",
    "workflow_step_failure",
    "workflow_success",
    "cancelled",
    "unknown",
}


def classify_run(run: dict[str, Any], jobs: list[dict[str, Any]]) -> str:
    status = str(run.get("status") or "")
    conclusion = str(run.get("conclusion") or "")

    if status in {"queued", "waiting", "requested", "pending"}:
        return "queued_waiting_for_runner"
    if conclusion == "cancelled":
        return "cancelled"
    if conclusion == "success":
        return "workflow_success"

    if status == "completed" and conclusion == "failure":
        if jobs and all(job.get("steps") in (None, []) for job in jobs):
            return "runner_or_account_before_step_one"
        if any(
            step.get("conclusion") == "failure"
            for job in jobs
            for step in (job.get("steps") or [])
        ):
            return "workflow_step_failure"

    return "unknown"


def render_safe_summary(run: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    classification = classify_run(run, jobs)
    return {
        "classification": classification,
        "run_status": run.get("status"),
        "run_conclusion": run.get("conclusion"),
        "jobs": [
            {
                "name": job.get("name"),
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "step_count": len(job.get("steps") or []),
                "reached_step_one": bool(job.get("steps")),
            }
            for job in jobs
        ],
    }


def main() -> int:
    payload = json.load(sys.stdin)
    summary = render_safe_summary(payload.get("run", {}), payload.get("jobs", []))
    json.dump(summary, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
