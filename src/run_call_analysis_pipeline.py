"""
run_call_analysis_pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unified CLI pipeline for AmoCRM call recording analysis + lead enrichment.

Usage:
    # Analyze last 20 deals' call recordings:
    python src/run_call_analysis_pipeline.py

    # Analyze last 50 deals:
    python src/run_call_analysis_pipeline.py --limit 50

    # Analyze a single lead:
    python src/run_call_analysis_pipeline.py --lead-id 12345678

    # Only analyze calls, skip enrichment:
    python src/run_call_analysis_pipeline.py --calls-only

    # Only enrich leads (skip call analysis):
    python src/run_call_analysis_pipeline.py --enrich-only

    # Full pipeline for single lead:
    python src/run_call_analysis_pipeline.py --lead-id 12345678 --enrich
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows PowerShell unicode fix — force UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    handlers=[
        logging.StreamHandler(
            stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
            if hasattr(sys.stdout, "fileno")
            else sys.stdout
        )
    ],
)
logger = logging.getLogger("call_pipeline")



async def build_amocrm() -> "AmoCRMSync":
    from src.settings import settings
    from src.services.core.amocrm_sync import AmoCRMSync

    return AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=(
            settings.AMOCRM_CLIENT_SECRET.get_secret_value()
            if settings.AMOCRM_CLIENT_SECRET
            else ""
        ),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )


async def build_userbot_client():
    """Build Telethon userbot client if USERBOT_SESSION_STRING is configured."""
    from src.settings import settings

    session_str = (
        settings.USERBOT_SESSION_STRING.get_secret_value()
        if settings.USERBOT_SESSION_STRING
        else None
    )
    if not session_str or not session_str.strip():
        logger.warning("[PIPELINE] USERBOT_SESSION_STRING not set — Telegram enrichment disabled.")
        return None

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        client = TelegramClient(
            StringSession(session_str),
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
        )
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("[PIPELINE] Userbot session not authorized.")
            await client.disconnect()
            return None
        logger.info("✅ [PIPELINE] Userbot connected.")
        return client
    except Exception as e:
        logger.warning(f"[PIPELINE] Userbot connect failed: {e}")
        return None


async def run_call_analysis(
    amocrm,
    db,
    lead_id: int = None,
    limit: int = 20,
):
    """Run call recording transcription + classification for leads."""
    from src.services.core.call_analyzer import CallAnalyzer

    analyzer = CallAnalyzer(amocrm=amocrm, db=db)

    if lead_id:
        logger.info(f"🎙️ [CALLS] Analyzing calls for single lead {lead_id}...")
        phone = _get_lead_phone(amocrm, lead_id)
        n = await analyzer.process_call_recordings_for_lead(lead_id, caller_phone=phone)
        logger.info(f"✅ [CALLS] Processed {n} recording(s) for lead {lead_id}.")
        return {"leads_scanned": 1, "calls_processed": n}
    else:
        logger.info(f"🎙️ [CALLS] Analyzing calls for {limit} most recent leads...")
        stats = await analyzer.analyze_recent_calls(limit=limit)
        logger.info(
            f"✅ [CALLS] Done — scanned {stats['leads_scanned']} leads, "
            f"processed {stats['calls_processed']} recordings."
        )
        return stats


async def run_call_analysis_safe(
    amocrm,
    db,
    lead_id: int = None,
    limit: int = 20,
    write: bool = True,
    include_transcript: bool = True,
    one_analysis_per_lead: bool = False,
    max_calls_per_lead: int = 0,
    min_call_duration_seconds: int = 0,
):
    """Run call analysis with production safety controls ported from jonbranding-web."""
    from src.services.core.call_analyzer import CallAnalyzer

    analyzer = CallAnalyzer(amocrm=amocrm, db=db)
    common = {
        "write": write,
        "include_transcript": include_transcript,
        "one_analysis_per_lead": one_analysis_per_lead,
        "max_calls_per_lead": max_calls_per_lead,
        "min_call_duration_seconds": min_call_duration_seconds,
    }

    if lead_id:
        logger.info("[CALLS] Analyzing calls for single lead %s...", lead_id)
        phone = _get_lead_phone(amocrm, lead_id)
        n = await analyzer.process_call_recordings_for_lead(
            lead_id,
            caller_phone=phone,
            **common,
        )
        logger.info("[CALLS] Processed %s recording(s) for lead %s.", n, lead_id)
        return {"leads_scanned": 1, "calls_processed": n}

    logger.info("[CALLS] Analyzing calls for %s most recent leads...", limit)
    stats = await analyzer.analyze_recent_calls(limit=limit, **common)
    logger.info(
        "[CALLS] Done: scanned %s leads, processed %s recordings.",
        stats["leads_scanned"],
        stats["calls_processed"],
    )
    return stats


async def append_report(report_path: str, row: dict) -> None:
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now(timezone.utc).isoformat(), **row}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


async def run_enrichment(
    amocrm,
    db,
    user_client,
    lead_id: int = None,
    limit: int = 20,
):
    """Run Telegram-based lead enrichment for leads."""
    from src.services.core.amocrm_lead_enrichment import AmoCRMLeadEnricher
    from src.settings import settings

    enricher = AmoCRMLeadEnricher(
        amocrm=amocrm,
        db=db,
        user_client=user_client,
        gemini_api_key=settings.GEMINI_API_KEY.get_secret_value(),
    )

    if lead_id:
        logger.info(f"🔍 [ENRICH] Enriching lead {lead_id}...")
        phone = _get_lead_phone(amocrm, lead_id)
        if not phone:
            logger.warning(f"[ENRICH] No phone found for lead {lead_id}. Skipping.")
            return
        try:
            leads = await amocrm.get_leads_detailed(limit=1)
            lead_data = next((l for l in leads if l.get("id") == lead_id), {})
        except Exception:
            lead_data = {}

        result = await enricher.enrich_lead(lead_id=lead_id, lead_data=lead_data, phone=phone)
        logger.info(f"✅ [ENRICH] Lead {lead_id}: status={result.status}, tags={result.tags_added}")
        return result
    else:
        logger.info(f"🔍 [ENRICH] Enriching {limit} most recent leads...")
        try:
            leads = await asyncio.to_thread(amocrm.get_leads_detailed, limit) \
                if not asyncio.iscoroutinefunction(amocrm.get_leads_detailed) \
                else await amocrm.get_leads_detailed(limit=limit)
        except Exception as e:
            logger.error(f"[ENRICH] Failed to fetch leads: {e}")
            return

        enriched = 0
        skipped = 0
        failed = 0

        for lead in leads or []:
            lid = lead.get("id")
            if not lid:
                continue

            phone = _extract_phone_from_lead(lead)
            if not phone:
                skipped += 1
                continue

            try:
                result = await enricher.enrich_lead(
                    lead_id=int(lid), lead_data=lead, phone=phone
                )
                if result.status == "enriched":
                    enriched += 1
                elif result.status == "skipped":
                    skipped += 1
                else:
                    failed += 1
                logger.info(
                    f"  Lead {lid}: {result.status} | tags={result.tags_added}"
                )
            except Exception as e:
                logger.error(f"  Lead {lid}: enrichment error — {e}")
                failed += 1

            await asyncio.sleep(1)  # Rate limiting

        logger.info(
            f"✅ [ENRICH] Done — enriched={enriched}, skipped={skipped}, failed={failed}"
        )


def _get_lead_phone(amocrm, lead_id: int) -> str:
    """Quick sync fetch of phone for a single lead."""
    import requests
    try:
        url = f"{amocrm.base_url}/api/v4/leads/{lead_id}"
        params = {"with": "contacts"}
        resp = requests.get(url, headers=amocrm._get_headers(), params=params, timeout=20)
        if resp.status_code == 200:
            lead = resp.json()
            return _extract_phone_from_lead(lead)
    except Exception as e:
        logger.warning(f"[PIPELINE] Could not fetch phone for lead {lead_id}: {e}")
    return ""


def _extract_phone_from_lead(lead: dict) -> str:
    """Extract phone from AmoCRM lead's embedded contacts."""
    try:
        contacts = (
            lead.get("_embedded", {}).get("contacts", [])
            or lead.get("contacts", [])
        )
        for contact in contacts:
            fields = contact.get("custom_fields_values") or []
            for field in fields:
                if str(field.get("field_code", "")).upper() == "PHONE":
                    vals = field.get("values") or []
                    if vals:
                        return str(vals[0].get("value", ""))
    except Exception:
        pass
    return ""


async def main():
    parser = argparse.ArgumentParser(
        description="Oisha-OS: AmoCRM Call Analysis & Lead Enrichment Pipeline"
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of leads to scan (default: 20)")
    parser.add_argument("--lead-id", type=int, default=None, help="Process a single lead by ID")
    parser.add_argument("--calls-only", action="store_true", help="Only analyze call recordings")
    parser.add_argument("--enrich-only", action="store_true", help="Only run lead enrichment")
    parser.add_argument("--enrich", action="store_true", help="Run enrichment after call analysis")
    parser.add_argument("--write", action="store_true", help="Write notes, tags, tasks, and DB logs to AmoCRM")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without writing to AmoCRM")
    parser.add_argument("--include-transcript", action="store_true", help="Include transcript in AmoCRM notes")
    parser.add_argument("--one-analysis-per-lead", action="store_true", help="Skip leads that already have an AI_CALL_ANALYSIS note and stop after one processed call")
    parser.add_argument("--max-calls-per-lead", type=int, default=0, help="Maximum recordings to analyze per lead; 0 means all")
    parser.add_argument("--min-call-duration-seconds", type=int, default=0, help="Skip recordings shorter than this duration when AmoCRM provides duration")
    parser.add_argument("--report-path", default="", help="Write JSONL run summary/report to this path")
    args = parser.parse_args()

    run_calls = not args.enrich_only
    run_enrich = args.enrich_only or args.enrich
    write = args.write and not args.dry_run

    from src.database import Database

    # Initialize components
    await append_report(
        args.report_path,
        {
            "event": "run_started",
            "mode": "WRITE" if write else "DRY-RUN",
            "limit": args.limit,
            "lead_id": args.lead_id,
            "one_analysis_per_lead": args.one_analysis_per_lead,
            "max_calls_per_lead": args.max_calls_per_lead or "all",
            "min_call_duration_seconds": args.min_call_duration_seconds,
        },
    )
    logger.info("🚀 [PIPELINE] Initializing Oisha-OS Call Analysis Pipeline...")
    db = Database()
    await db.init_instance()

    amocrm = await build_amocrm()

    user_client = None
    if run_enrich:
        user_client = await build_userbot_client()

    # Run pipeline stages
    try:
        if run_calls:
            call_stats = await run_call_analysis_safe(
                amocrm=amocrm,
                db=db,
                lead_id=args.lead_id,
                limit=args.limit,
                write=write,
                include_transcript=args.include_transcript,
                one_analysis_per_lead=args.one_analysis_per_lead,
                max_calls_per_lead=args.max_calls_per_lead,
                min_call_duration_seconds=args.min_call_duration_seconds,
            )
            await append_report(args.report_path, {"event": "calls_finished", **call_stats})

        if run_enrich:
            await run_enrichment(
                amocrm=amocrm,
                db=db,
                user_client=user_client,
                lead_id=args.lead_id,
                limit=args.limit,
            )

    finally:
        if user_client:
            try:
                await user_client.disconnect()
            except Exception:
                pass
        await db.close()
        await append_report(args.report_path, {"event": "run_finished"})
        logger.info("🏁 [PIPELINE] Pipeline finished.")


if __name__ == "__main__":
    asyncio.run(main())
