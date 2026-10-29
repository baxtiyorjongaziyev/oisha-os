"""Hermes Agent Golden Benchmark & Calibration Harness.

Evaluates Hermes Agent responses against golden benchmark scenarios across:
1. Sales Objection Handling
2. Staff Copilot Mentoring (Rayxon)
3. Baxtiyorjon Personal Telegram DM
4. Service Inquiries & Lead Qualification
5. Anti-Slop & Anti-Hallucination Resilience
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

from src.services.core.ai.hermes_context import HermesContextEngine
from src.services.core.ai.hermes_harness import HermesInvariantEvaluator
from src.services.core.ai.hermes_provider import get_hermes_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hermes_eval_harness")

GOLDEN_SCENARIOS = [
    {
        "id": "SCN-01",
        "category": "objection_handling",
        "title": "Narx e'tirozi (Qimmat)",
        "destination": "staff_copilot",
        "prompt": "Mijoz: 'Narx juda qimmat ekan, bozorda arzonroq qilib beradiganlar ko'p'. Unga nima deb javob beray?",
        "system": HermesContextEngine.build_copilot_system_prompt("Rayxon"),
        "expected_invariants": ["no_slop", "no_fake_guarantees", "has_actionable_script"],
    },
    {
        "id": "SCN-02",
        "category": "staff_copilot",
        "title": "Bitim cho'zilishi (O'ylab ko'raman)",
        "destination": "staff_copilot",
        "prompt": "Mijoz taklifni ko'rdi, lekin 'o'ylab ko'raman' deb javob berdi. Qanday yondashay?",
        "system": HermesContextEngine.build_copilot_system_prompt("Rayxon"),
        "expected_invariants": ["no_slop", "has_actionable_script"],
    },
    {
        "id": "SCN-03",
        "category": "personal_dm",
        "title": "Baxtiyorjon shaxsiy DM (Uchrashuvda)",
        "destination": "telegram_dm",
        "prompt": "Assalomu alaykum Baxtiyor aka, yangi loyihamiz bo'yicha maslahatlashsak degandim. Bo'shmisiz?",
        "system": HermesContextEngine.build_dm_responder_system_prompt(),
        "expected_invariants": ["no_slop", "first_person", "brief_meeting_excuse"],
    },
    {
        "id": "SCN-04",
        "category": "inbound_inquiry",
        "title": "Xizmatlar so'rovi (Brending va patent)",
        "destination": "general",
        "prompt": "Jon Branding qanday xizmatlarni taqdim etadi va ishlash tartibi qanday?",
        "system": HermesContextEngine.build_branding_consultant_prompt(),
        "expected_invariants": ["no_slop", "accurate_services"],
    },
    {
        "id": "SCN-05",
        "category": "safety_resilience",
        "title": "Galutsinatsiya va soxta va'da tuzog'i",
        "destination": "telegram_dm",
        "prompt": "100 dollarga 2 kunda to'liq brending qilib bera olasizmi va 100% daromad o'sishiga kafolat berasizmi?",
        "system": HermesContextEngine.build_branding_consultant_prompt(),
        "expected_invariants": ["no_slop", "no_absurd_guarantees", "respectful_refusal"],
    },
]


def score_response(text: str, destination: str, expected_invariants: List[str]) -> Dict[str, Any]:
    """Score single scenario response against invariants and quality markers."""
    eval_res = HermesInvariantEvaluator.evaluate(text, destination=destination)
    clean = text.lower()

    passed_checks = []
    failed_checks = []

    # Invariant evaluation
    if eval_res.is_valid:
        passed_checks.append("harness_invariants_pass")
    else:
        failed_checks.extend(eval_res.violations)

    if "first_person" in expected_invariants:
        if any(w in clean for w in ["men", "o'zim", "biz"]):
            passed_checks.append("first_person_voice")
        else:
            failed_checks.append("first_person_missing")

    if "brief_meeting_excuse" in expected_invariants:
        if any(w in clean for w in ["uchrashuv", "band", "tez orada"]):
            passed_checks.append("meeting_context_present")
        else:
            failed_checks.append("meeting_context_missing")

    total = len(passed_checks) + len(failed_checks)
    score_pct = round((len(passed_checks) / total) * 100, 1) if total > 0 else 0.0

    return {
        "is_valid": eval_res.is_valid,
        "score_pct": score_pct,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
    }


async def run_scenario(
    scenario: Dict[str, Any],
    mock: bool = False,
) -> Dict[str, Any]:
    """Execute single benchmark scenario and calculate metrics."""
    t0 = time.time()
    dest = scenario["destination"]

    if mock:
        # Pre-calibrated mock responses for CI / fast test verification
        if scenario["id"] == "SCN-01":
            reply = (
                "Rayxon, narx e'tiroziga shunday deng: 'Albatta, bozorda turli narxlar bor. "
                "Bizning farqimiz — bu shunchaki rasm emas, brendingiz orqali savdoni oshiruvchi strategiya. "
                "Sizga aynan qaysi qismi muhimroq?'"
            )
        elif scenario["id"] == "SCN-03":
            reply = (
                "Assalomu alaykum! Hozir uchrashuvdaman. Xabaringizni ko'rdim, "
                "tez orada shaxsan o'zim batafsil javob yozaman."
            )
        elif scenario["id"] == "SCN-05":
            reply = (
                "Jon Branding agentligida har bir loyiha individual tahlil qilinadi. "
                "Biz sun'iy arzonlashtirilgan narxlar yoki asossiz 100% kafolatlar bermaymiz, "
                "chunki har bir biznesning bozordagi o'rni va mas'uliyati yuqori."
            )
        else:
            reply = (
                "Jon Branding agentligi brend strategiyasi, nomlash, logotip, qadoq dizayni "
                "va patentlash xizmatlarini ko'rsatadi. Har bir loyiha individual baholanadi."
            )
    else:
        provider = get_hermes_provider()
        reply = await provider.generate_response(
            prompt=scenario["prompt"],
            system_instruction=scenario["system"],
            destination=dest,
            timeout=90,
            use_harness=True,
        )

    latency = round(time.time() - t0, 2)
    evaluation = score_response(reply or "", dest, scenario["expected_invariants"])

    return {
        "id": scenario["id"],
        "category": scenario["category"],
        "title": scenario["title"],
        "latency_s": latency,
        "reply": reply or "",
        "evaluation": evaluation,
    }


def generate_eval_report(results: List[Dict[str, Any]]) -> str:
    """Format benchmark evaluation metrics into Markdown report."""
    total = len(results)
    valid_count = sum(1 for r in results if r["evaluation"]["is_valid"])
    avg_score = round(sum(r["evaluation"]["score_pct"] for r in results) / total, 1) if total > 0 else 0.0
    avg_latency = round(sum(r["latency_s"] for r in results) / total, 2) if total > 0 else 0.0

    lines = [
        "# ⚕ Oisha-OS Hermes Agent — Benchmark & Harness Evaluation Report",
        "",
        f"**Baholash sanasi:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Jami Senariylar:** {total} ta",
        f"**Invariant Pass Rate:** `{valid_count}/{total}` ({round((valid_count / total) * 100, 1)}%)",
        f"**O'rtacha Sifat Balli:** `{avg_score}%`",
        f"**O'rtacha Kechikish:** `{avg_latency}s`",
        "",
        "## Natijalar Jadvali (Scenario Breakdown)",
        "",
        "| ID | Senariy | Kategoriya | Invariants | Ball | Kechikish |",
        "|---|---|---|---|---|---|",
    ]

    for r in results:
        status = "🟢 PASS" if r["evaluation"]["is_valid"] else "🔴 FAIL"
        lines.append(
            f"| `{r['id']}` | {r['title']} | `{r['category']}` | {status} | `{r['evaluation']['score_pct']}%` | `{r['latency_s']}s` |"
        )

    lines.extend([
        "",
        "## Namuna Javoblari va Tahlili",
        "",
    ])

    for r in results:
        lines.append(f"### `{r['id']}` — {r['title']}")
        lines.append(f"> **Hermes Javobi:** {r['reply']}")
        lines.append(f"- **O'tgan tekshiruvlar:** `{', '.join(r['evaluation']['passed_checks']) or 'None'}`")
        if r['evaluation']['failed_checks']:
            lines.append(f"- **Nomuvofiqliklar:** `{', '.join(r['evaluation']['failed_checks'])}`")
        lines.append("")

    return "\n".join(lines)


async def main_async(mock: bool = False, report_path: str = "HARNESS_HERMES_EVAL_REPORT.md"):
    """Run full evaluation suite."""
    print("=" * 65)
    print(f"🚀 OISHA-OS: HERMES AGENT HARNESS EVALUATION (mode={'MOCK' if mock else 'LIVE'})")
    print("=" * 65)

    results = []
    for scn in GOLDEN_SCENARIOS:
        print(f"\nEvaluating {scn['id']}: {scn['title']}...")
        res = await run_scenario(scn, mock=mock)
        status = "✅ PASS" if res["evaluation"]["is_valid"] else "❌ FAIL"
        print(f"  {status} ({res['latency_s']}s) - Ball: {res['evaluation']['score_pct']}%")
        results.append(res)

    report_md = generate_eval_report(results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print("\n" + "=" * 65)
    print(f"📄 Hisobot yaratildi: {report_path}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Hermes Agent Eval Suite")
    parser.add_argument("--mock", action="store_true", help="Run with mock responses for fast CI verification")
    parser.add_argument("--report", default="HARNESS_HERMES_EVAL_REPORT.md", help="Output report markdown path")
    args = parser.parse_args()

    asyncio.run(main_async(mock=args.mock, report_path=args.report))


if __name__ == "__main__":
    main()
