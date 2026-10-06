# Post-conversation CRM automation (Deep Sales 1-band)

Sana: 2026-10-06 · Holat: Owner tasdiqlagan chegaralar bilan reja

## Maqsad
Qo'ng'iroq/chat tahlili tugagach AmoCRM avtomatik yangilanadi: note, bo'sh maydonlar,
keyingi task, etapni oldinga surish. Owner tasdig'isiz.

## Tasdiqlangan chegaralar
| Amal | Rejim |
|---|---|
| Xulosa note | auto |
| Bo'sh maydon to'ldirish | auto |
| To'la maydonni o'zgartirish | yo'q — note'da taklif |
| Follow-up task | auto, lid boshiga 1 ochiq AI-task |
| Etap oldinga | auto, confidence >= 0.8 |
| Etap orqaga / Lost / Won | yo'q — menejerga task |

Himoya: audit + rollback, DB kill-switch, lid/soat rate-limit (3 o'zgarish).
Quiet-hours: `agent_policy` payload `allow_in_quiet_hours=True` (mijozga xabar ketmaydi).

## Mavjud poydevor
- `call_analytics/crm_notes.py` — note builder (bor)
- `call_analytics/crm_tasks.py` — `_should_create_task`, `_create_follow_up_task` (bor)
- `call_analytics/runner.py` — pipeline
- `core/agent_policy.py` — quiet-hours / auto_actions
- `salescoach_store` — `salescoach_task_audit` jadvali

## Yangi ishlar
1. `call_analytics/crm_actions.py` — `CrmActionPlanner`:
   tahlil -> `[NoteAction, FieldFillAction, TaskAction, StageAction]` (sof funksiya).
   - Field mapping: `call_analytics/crm_automation_config.py` (PyYAML yo'q; ID'lar repo skriptlaridan).
   - Stage mapping: `crm_automation_config.STAGE_RULES` (outcome -> status_id, faqat oldinga tartib).
2. `call_analytics/crm_executor.py` — `CrmActionExecutor`:
   - kill-switch `crm_automation:enabled` (agent_state), rate-limit, policy tekshiruv
   - bo'sh bo'lmagan maydonni tashlab, note'ga "taklif" qo'shadi
   - etap: joriy pipeline tartibida faqat oldinga; Lost/Won/orqaga -> TaskAction
   - har amal oldin/keyin qiymati bilan `crm_automation_audit` jadvaliga
3. `crm_automation_audit` jadvali + `rollback(audit_id)` (maydon/etapni eski qiymatga).
4. `runner.py` — mavjud note/task chaqiruvlari o'rniga planner+executor (feature flag
   `CRM_AUTOMATION_ENABLED`, default off -> shadow log).
5. Telegram chatlar: `telegram_salescoach_runtime` tahlilidan keyin shu executor.
6. Admin bot: `/crm_auto on|off`, `/crm_rollback <audit_id>`.

## Testlar (TDD, SKIP_LIVE)
- `tests/test_crm_action_planner.py` — mapping, confidence chegarasi, Lost/Won -> task
- `tests/test_crm_executor.py` — bo'sh maydon only, kill-switch, rate-limit, audit, rollback
- mavjud: `test_call_conversion_tasks.py`, `test_call_crm_note_builder.py` yashil qolsin

## Rollout
1. Flag off: shadow — rejalashtirilgan amallar faqat audit'ga (`dry_run=1`), 3 kun.
2. Audit ko'rib chiqish -> flag on.
3. Pre-flight: `SKIP_LIVE=1 python -m pytest -q`, `bandit -r src/ -ll`.

## Ochiq savollar
- Select maydonlar (LPR, soha, toifa) enum mapping talab qiladi — keyingi bosqich.
- `settings.py` coordinator-owned: flag qo'shish AGENTS.md lock orqali.
