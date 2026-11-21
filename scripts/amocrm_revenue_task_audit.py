"""Read-only audit of AI-created amoCRM tasks for revenue relevance.

Never changes tasks. "Review" is not permission to complete/delete a task.
Run only where the authenticated amoCRM integration is configured.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

AI_PREFIXES = (
    "oisha-os keyingi qadam",
    "oisha-os telegram bot",
    "oisha smart:",
    "oisha audit:",
    "telegram suhbatidan:",
)
PAYMENT_WORDS = (
    "avans", "tolov", "qarz", "undirish", "invoice", "payment",
    "qoldiq", "debit", "hisob faktura",
)
REVENUE_WORDS = PAYMENT_WORDS + (
    "qongiroq", "boglan", "aloqa", "uchrashuv", "taklif",
    "shartnoma", "kelishuv", "muzokara", "followup",
    "reaktivatsiya", "qayta boglan", "kp", "buyurtma",
)
CLOSED_STATUSES = frozenset({142, 143})


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    for mark in ("ʻ", "ʼ", "’", "'", "‘", "´"):
        text = text.replace(mark, "")
    text = re.sub(r"[^a-z0-9а-яёғқўҳ]+", " ", text)
    return " ".join(text.split())


def is_ai_task(task: dict) -> bool:
    text = normalized(task.get("text"))
    return any(text.startswith(normalized(prefix)) for prefix in AI_PREFIXES)


def has_action(text: str, words: tuple[str, ...]) -> bool:
    clean = " " + normalized(text) + " "
    return any(re.search(r"(?<!\w)" + re.escape(word) + r"\w*", clean) for word in words)


def audit_tasks(
    tasks: list[dict],
    lead_status: Callable[[int], int | None],
) -> list[dict]:
    """Classify only clearly AI-created open tasks; do not mutate input or CRM."""
    statuses: dict[int, int | None] = {}
    findings: list[dict] = []
    for task in tasks:
        if task.get("is_completed") or not is_ai_task(task):
            continue
        task_id = task.get("id")
        entity_id = task.get("entity_id") or task.get("element_id")
        entity_type = str(task.get("entity_type") or "leads").lower()
        text = str(task.get("text") or "")
        lead_id = None
        if entity_type in {"leads", "2"} and entity_id:
            try:
                lead_id = int(entity_id)
            except (TypeError, ValueError):
                pass

        if lead_id is None:
            outcome = "review_unlinked"
        else:
            if lead_id not in statuses:
                try:
                    statuses[lead_id] = lead_status(lead_id)
                except Exception:
                    statuses[lead_id] = None
            status = statuses[lead_id]
            if status is None:
                outcome = "review_unknown_status"
            elif status in CLOSED_STATUSES:
                # Won deals may still have unpaid balances; do not hide collection work.
                outcome = "keep_collection" if has_action(text, PAYMENT_WORDS) else "review_closed_deal"
            elif has_action(text, REVENUE_WORDS):
                outcome = "keep_revenue"
            else:
                outcome = "review_no_revenue_signal"

        findings.append({
            "task_id": task_id,
            "lead_id": lead_id,
            "outcome": outcome,
            # Text is not emitted to logs/reports; it can contain client PII.
            "_fingerprint": (lead_id, normalized(text), task.get("complete_till")),
        })

    # Same text, deal and deadline: flag older copies for review only.
    most_recent: dict[tuple, int] = {}
    for item in findings:
        fp = item["_fingerprint"]
        if fp[0] is None:
            continue
        try:
            identifier = int(item["task_id"])
        except (TypeError, ValueError):
            continue
        most_recent[fp] = max(identifier, most_recent.get(fp, identifier))
    for item in findings:
        fp = item.pop("_fingerprint")
        if fp[0] is not None and item["task_id"] is not None:
            try:
                if int(item["task_id"]) < most_recent.get(fp, -1):
                    item["outcome"] = "review_duplicate"
            except (TypeError, ValueError):
                pass
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Oisha tasks without modifying amoCRM")
    parser.add_argument("--output", type=Path, help="Optional PRIVATE JSON report path")
    args = parser.parse_args()

    # Import here so pure classification tests never connect to production.
    from scripts.amocrm_task_cleanup import AmoCRMTaskCleaner

    client = AmoCRMTaskCleaner(live=False)
    tasks = client._get_all_tasks()
    findings = audit_tasks(tasks, client._get_lead_status)
    counts = Counter(x["outcome"] for x in findings)
    summary = {
        "audited_at": datetime.now().isoformat(timespec="seconds"),
        "total_open_tasks": len(tasks),
        "ai_tasks_examined": len(findings),
        "outcomes": dict(sorted(counts.items())),
        "mutations": 0,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"summary": summary, "tasks": findings}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("Private report saved. Do not commit it to the public repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
