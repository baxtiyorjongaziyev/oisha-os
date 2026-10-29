# Contabo runtime inventory

Observed 2026-10-29, Asia/Tashkent. Read-only inspection; credentials excluded.

## Confirmed processes

| Process | State | Responsibility |
|---|---|---|
| oisha-os.service | active | Main Oisha application and userbot runtime |
| hermes-gateway.service | active | Separate Hermes Telegram gateway |
| oisha-watchdog.service | active | Oisha endpoint/service health recovery |
| oisha-sales-hourly.timer | scheduled | Mon–Sat 10–12,14–19 at :05, Tashkent |
| oisha-calls-report.timer | scheduled | Daily 18:30, Tashkent; persistent catch-up |

Oisha server revision: 635723c5. Hermes revision: bf0203a794. These revisions do not describe uncommitted server patches.

## Confirmed delivery paths

- Group mention: src/handlers/group_mention.py lines 132,141,168 call message.reply directly.
- Check-in: remote_staff_checkin_scheduler.py uses quality gate and delivery_ledger.send_once. Disabled through systemd environment; observed process value REMOTE_STAFF_CHECKIN_ENABLED=0.
- Hourly report: scripts/hourly_sales_control.py uses send_telegram; independent of check-in disable flag.
- Daily call report: scripts/daily_sales_calls_report.py implements HTTP Telegram sendMessage.
- Hermes gateway: gateway/run_turn_runner.py and run_turn_persistence.py call gateway/run.py final response sanitizer. Separate delivery runtime from Oisha.

## Bootstrap scheduler inventory

start_background_schedulers returns immediately when RUN_USERBOT_ONLY is true. Declared loops:
crm_discipline, crm_capacity_archiver, daily_frog, channel_scout, hunter_retry,
lead_follow_up, chat_manager_extract, attendance_summary, instagram_weekly_report,
meta_health_check, instagram_comment_backfill, youtube_comment_backfill,
call_analysis, cloud_brain_synthesizer, training_advice, ROP schedulers,
daily_insights, sales_intel, unowned_lead_alert, speed_to_lead,
marketing_attribution, income_supervisor, jamoa_ritm, remote_staff_checkin.

AI autopilot requires ENABLE_AI_AUTOPILOT. Meta leadgen and its watchdog run here only
when no standalone worker is configured. Several imports are optional and catch ImportError.
Declaration is not proof each task is currently alive: task-level runtime census remains open.

## Source drift confirmed

Server has src/services/core/checkin_composer.py; local checkout does not.
Local checkout has core/ai/hermes_provider.py and hermes_harness.py; inspected Oisha
server tree does not. Consequently the local harness is not proven to protect server replies.
Check-in scheduler server SHA256 after normalization:
4063cfd0899c7f0565d0bcb03029490a4d90424f1a57ef55c78d00808a5b0bb1.

## Memory and identity

Hermes state.db contains Telegram sessions/messages. Config enables memory and user profile.
Group sessions default to per-user, thread sessions can be shared. Sender ID is now exposed
in shared Telegram message context; DM context includes ID. This does not establish a
cross-chat identity/ACL database. SOUL.md contains policy, not an enforcement boundary.

## Remaining stage-1 acceptance work

- Census live asyncio tasks and effective feature flags without exposing credentials.
- Enumerate all sender call sites recursively and map each to its scheduler/handler.
- Verify Telegram bot identity ownership for each runtime without exposing bot tokens.
- Complete local/server file hash comparison and inventory all memory stores.
- Inventory nested ROP/admin scheduler registrations, external cron and user timers.

Stage 1 remains incomplete until these gaps are resolved. No runtime changes performed by this inventory.
