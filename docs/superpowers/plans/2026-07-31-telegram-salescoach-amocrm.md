# Telegram SalesCoach → AmoCRM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram’dagi ruxsat etilgan biznes dialoglarini SalesCoach mezonida baholash, natijani saqlash va xavfsiz rollout rejimiga muvofiq AmoCRM note/task yozish.

**Architecture:** Oracle VM’dagi mavjud Telethon userbot faqat event manbai bo‘lib qoladi. Yangi Python orchestration qatlami dialogni filterlaydi, CRM bilan bog‘laydi, fingerprint qiladi va `salescoach-ai` API’ga yuboradi; alohida AmoCRM writer responsible manager, dedupe va write verificationni boshqaradi. Production default `shadow`, undan keyin `approval`, so‘ng allowlist asosidagi `auto` rejimiga o‘tiladi.

**Tech Stack:** Python 3.11+, asyncio, Telethon, FastAPI, httpx, SQLite/Turso-compatible SQL, NestJS, class-validator, Anthropic SDK, pytest, Jest, Bandit.

## Global Constraints

- Telegram userbot faqat Oracle VM’da ishlaydi; yangi Telegram session ochilmaydi.
- Mijozga avtomatik Telegram xabari yuborilmaydi.
- Faqat private biznes DM va AmoCRM bilan ishonchli bog‘langan dialog tahlil qilinadi.
- Oila, shaxsiy, do‘st, Saved Messages, bot va ichki jamoa chatlari chiqarib tashlanadi.
- Xabar matni, telefon, token va session string loglarga yozilmaydi.
- Default rejim: `TELEGRAM_SALESCOACH_MODE=shadow`.
- Auto write uchun CRM confidence kamida `0.85`, analysis confidence kamida `0.80`.
- Task leadning `responsible_user_id` qiymatiga tushadi; hardcoded `OWNER_ID` ishlatilmaydi.
- Idempotency key: `sha256(lead_id + task_type + conversation_fingerprint)`.
- AmoCRM POST javobi success uchun yetarli emas; write qayta o‘qilib tekshiriladi.
- Python yakuniy gate: `pytest -q` va `bandit -r src/ -ll`.
- TypeScript yakuniy gate: API testlari va `tsc --noEmit`.

---

## File Map

**Create**

- `salescoach-ai/apps/api/src/negotiations/dto/analyze-conversation.dto.ts` — conversation request validation.
- `salescoach-ai/apps/api/src/negotiations/conversation-analysis.types.ts` — structured response contract va score normalization.
- `salescoach-ai/apps/api/src/negotiations/negotiations.controller.spec.ts` — endpoint contract tests.
- `salescoach-ai/apps/api/src/negotiations/negotiations.service.spec.ts` — scoring/parser tests.
- `src/services/core/telegram_salescoach_store.py` — `conversation_analyses` va task audit persistence.
- `src/services/core/telegram_salescoach.py` — filtering, batching, fingerprint va orchestration.
- `src/services/core/crm/salescoach_task_writer.py` — AmoCRM note/task, dedupe va verification.
- `tests/test_telegram_salescoach_store.py` — schema va persistence tests.
- `tests/test_telegram_salescoach.py` — privacy, batching, confidence va mode tests.
- `tests/test_salescoach_task_writer.py` — responsible manager, dedupe va verifier tests.
- `tests/test_salescoach_sync_conversation.py` — Python HTTP bridge tests.

**Modify**

- `salescoach-ai/apps/api/src/negotiations/negotiations.controller.ts` — `POST /negotiations/analyze-conversation`.
- `salescoach-ai/apps/api/src/negotiations/negotiations.service.ts` — structured conversation scoring.
- `src/services/core/salescoach_sync.py` — `analyze_conversation(...)` client method.
- `src/handlers/message_handler.py` — lightweight event hook va admin approval callbacks.
- `src/main.py` — singleton initialization va dependency wiring only.
- `src/api/routes/sales_quality.py` — Telegram conversation list/detail endpoint.
- `src/settings.py` — feature flags va safe defaults.
- `src/boot.py` — store schema initialization.
- `AGENTS.md` — implementation status va production notes.

---

### Task 1: SalesCoach API Conversation Contract

**Files:**
- Create: `salescoach-ai/apps/api/src/negotiations/dto/analyze-conversation.dto.ts`
- Create: `salescoach-ai/apps/api/src/negotiations/conversation-analysis.types.ts`
- Create: `salescoach-ai/apps/api/src/negotiations/negotiations.controller.spec.ts`
- Create: `salescoach-ai/apps/api/src/negotiations/negotiations.service.spec.ts`
- Modify: `salescoach-ai/apps/api/src/negotiations/negotiations.controller.ts`
- Modify: `salescoach-ai/apps/api/src/negotiations/negotiations.service.ts`

**Interfaces:**
- Produces: `AnalyzeConversationDto`, `ConversationAnalysis`, `normalizeConversationAnalysis(raw)`.
- HTTP: `POST /v1/negotiations/analyze-conversation` through the existing API prefix.
- Response: validated `ConversationAnalysis` with deterministic `overallScore`.

- [ ] **Step 1: Write DTO validation tests**

```ts
it('rejects an empty conversation', async () => {
  await request(app.getHttpServer())
    .post('/v1/negotiations/analyze-conversation')
    .set('Authorization', `Bearer ${serviceToken}`)
    .send({ leadId: 42, managerId: '77', messages: [] })
    .expect(400);
});

it('accepts bounded manager/customer messages', async () => {
  service.analyzeConversation.mockResolvedValue(validAnalysis);
  await request(app.getHttpServer())
    .post('/v1/negotiations/analyze-conversation')
    .set('Authorization', `Bearer ${serviceToken}`)
    .send({
      leadId: 42,
      managerId: '77',
      crmStatus: 'Birinchi kontakt',
      messages: [
        { id: 1001, role: 'customer', text: 'Narxi qancha?', sentAt: '2026-07-31T10:00:00Z' },
        { id: 1002, role: 'manager', text: 'Avval vazifangizni aniqlab olaylik.', sentAt: '2026-07-31T10:01:00Z' },
      ],
    })
    .expect(201);
});
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```bash
cd salescoach-ai
pnpm --filter @salescoach/api test -- negotiations.controller.spec.ts
```

Expected: FAIL because `AnalyzeConversationDto` and route do not exist.

- [ ] **Step 3: Add the exact DTO contract**

```ts
export enum ConversationRole {
  MANAGER = 'manager',
  CUSTOMER = 'customer',
}

export class ConversationMessageDto {
  @IsInt()
  id!: number;

  @IsEnum(ConversationRole)
  role!: ConversationRole;

  @IsString()
  @MinLength(1)
  @MaxLength(4000)
  text!: string;

  @IsISO8601()
  sentAt!: string;
}

export class AnalyzeConversationDto {
  @IsInt()
  leadId!: number;

  @IsString()
  managerId!: string;

  @IsOptional()
  @IsString()
  crmStatus?: string;

  @IsArray()
  @ArrayMinSize(2)
  @ArrayMaxSize(50)
  @ValidateNested({ each: true })
  @Type(() => ConversationMessageDto)
  messages!: ConversationMessageDto[];
}
```

- [ ] **Step 4: Add the response contract and deterministic normalizer**

```ts
export interface ConversationAnalysis {
  overallScore: number;
  scores: {
    opening: number;
    needsDiscovery: number;
    solutionFit: number;
    valueExplanation: number;
    objectionHandling: number;
    nextStep: number;
    responseDiscipline: number;
  };
  strengths: string[];
  mistakes: string[];
  missedQuestions: string[];
  clientIntent: 'cold' | 'warm' | 'hot';
  objections: string[];
  dealRisk: 'low' | 'medium' | 'high';
  nextBestAction: string;
  recommendedReply: string;
  recommendedTasks: Array<{
    type: 'reply_customer' | 'schedule_meeting' | 'send_proposal' | 'follow_up' | 'send_material' | 'manager_review';
    reason: string;
    evidenceMessageIds: number[];
  }>;
  confidence: number;
  evidenceMessageIds: number[];
}

const SCORE_LIMITS = {
  opening: 10,
  needsDiscovery: 20,
  solutionFit: 15,
  valueExplanation: 15,
  objectionHandling: 15,
  nextStep: 15,
  responseDiscipline: 10,
} as const;
```

`normalizeConversationAnalysis` each score’ni `0..limit` oralig‘iga clamp qiladi, `overallScore`ni category score’lar yig‘indisidan qayta hisoblaydi, confidence’ni `0..1` oralig‘iga clamp qiladi va evidence IDs’ni input message IDs bilan kesishadi.

- [ ] **Step 5: Add service parser tests**

```ts
it('recalculates the overall score instead of trusting the model', () => {
  const result = normalizeConversationAnalysis(
    { overallScore: 99, scores: { opening: 8, needsDiscovery: 14, solutionFit: 10, valueExplanation: 9, objectionHandling: 7, nextStep: 10, responseDiscipline: 6 }, confidence: 0.91 },
    new Set([1001, 1002]),
  );
  expect(result.overallScore).toBe(64);
});

it('drops hallucinated evidence ids', () => {
  const result = normalizeConversationAnalysis(
    { scores: zeroScores, evidenceMessageIds: [1001, 9999], confidence: 0.8 },
    new Set([1001, 1002]),
  );
  expect(result.evidenceMessageIds).toEqual([1001]);
});
```

- [ ] **Step 6: Implement the controller and service method**

Controller signature:

```ts
@Post('analyze-conversation')
analyzeConversation(
  @OrgId() orgId: string,
  @CurrentUser() user: any,
  @Body() dto: AnalyzeConversationDto,
) {
  return this.service.analyzeConversation(orgId, user.id, dto);
}
```

Service signature:

```ts
async analyzeConversation(
  orgId: string,
  actorId: string,
  dto: AnalyzeConversationDto,
): Promise<ConversationAnalysis>
```

The prompt must include the seven exact weighted criteria, demand JSON only, and explicitly forbid invented message IDs. Do not persist raw message text in SalesCoach API logs.

- [ ] **Step 7: Run tests and typecheck**

```bash
cd salescoach-ai
pnpm --filter @salescoach/api test -- negotiations.controller.spec.ts negotiations.service.spec.ts
pnpm --filter @salescoach/api exec tsc --noEmit
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add salescoach-ai/apps/api/src/negotiations
git commit -m "feat(salescoach): analyze Telegram conversations"
```

---

### Task 2: Python SalesCoach HTTP Bridge

**Files:**
- Modify: `src/services/core/salescoach_sync.py`
- Create: `tests/test_salescoach_sync_conversation.py`

**Interfaces:**
- Consumes: Task 1 `POST /v1/negotiations/analyze-conversation`.
- Produces:

```python
async def analyze_conversation(
    self,
    *,
    lead_id: int,
    manager_id: str,
    messages: list[dict[str, object]],
    crm_status: str = "",
) -> dict[str, object] | None:
```

- [ ] **Step 1: Write failing HTTP bridge tests**

```python
@pytest.mark.asyncio
async def test_analyze_conversation_posts_structured_payload(monkeypatch):
    sync = SalesCoachSync()
    sync.enabled = True
    sync.base_url = "https://salescoach.test"
    fake = FakeAsyncClient(json_response={"overallScore": 78, "confidence": 0.9})
    sync._client = fake

    result = await sync.analyze_conversation(
        lead_id=42,
        manager_id="77",
        crm_status="Birinchi kontakt",
        messages=[
            {"id": 1001, "role": "customer", "text": "Narxi qancha?", "sentAt": "2026-07-31T10:00:00Z"},
            {"id": 1002, "role": "manager", "text": "Vazifangizni aniqlab olaylik.", "sentAt": "2026-07-31T10:01:00Z"},
        ],
    )

    assert result["overallScore"] == 78
    assert fake.last_path == "/v1/negotiations/analyze-conversation"
    assert fake.last_json["leadId"] == 42
```

Also test disabled mode returns `None`, timeout returns `None`, and logs do not contain message text.

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_salescoach_sync_conversation.py -q
```

Expected: FAIL because the method does not exist.

- [ ] **Step 3: Implement the minimal client method**

```python
async def analyze_conversation(self, *, lead_id, manager_id, messages, crm_status=""):
    if not self.enabled:
        return None
    payload = {
        "leadId": int(lead_id),
        "managerId": str(manager_id),
        "crmStatus": crm_status,
        "messages": messages[-50:],
    }
    try:
        response = await self.client.post(
            "/v1/negotiations/analyze-conversation",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("[SalesCoach] conversation analysis failed: %s", type(exc).__name__)
        return None
```

Do not interpolate payload or customer text into the log line.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_salescoach_sync_conversation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/core/salescoach_sync.py tests/test_salescoach_sync_conversation.py
git commit -m "feat(oisha): add conversation scoring bridge"
```

---

### Task 3: Conversation Analysis Store and Audit Schema

**Files:**
- Create: `src/services/core/telegram_salescoach_store.py`
- Create: `tests/test_telegram_salescoach_store.py`
- Modify: `src/boot.py`

**Interfaces:**
- Produces `TelegramSalesCoachStore`:

```python
class TelegramSalesCoachStore:
    async def initialize(self) -> None: ...
    async def save_analysis(self, record: ConversationAnalysisRecord) -> int: ...
    async def fingerprint_exists(self, fingerprint: str) -> bool: ...
    async def task_key_exists(self, idempotency_key: str) -> bool: ...
    async def record_task_write(self, audit: TaskWriteAudit) -> None: ...
    async def list_recent(self, limit: int = 100) -> list[dict[str, object]]: ...
```

- [ ] **Step 1: Write schema tests**

```python
@pytest.mark.asyncio
async def test_initialize_creates_conversation_and_task_audit_tables(db):
    store = TelegramSalesCoachStore(db)
    await store.initialize()
    tables = await list_table_names(db)
    assert "conversation_analyses" in tables
    assert "salescoach_task_audit" in tables

@pytest.mark.asyncio
async def test_duplicate_fingerprint_is_rejected(db):
    store = TelegramSalesCoachStore(db)
    await store.initialize()
    await store.save_analysis(sample_record(fingerprint="abc"))
    with pytest.raises(DuplicateConversationAnalysis):
        await store.save_analysis(sample_record(fingerprint="abc"))
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_telegram_salescoach_store.py -q
```

Expected: FAIL because store and tables do not exist.

- [ ] **Step 3: Implement exact schemas**

```sql
CREATE TABLE IF NOT EXISTS conversation_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_hash TEXT NOT NULL,
    telegram_user_hash TEXT NOT NULL,
    lead_id INTEGER NOT NULL,
    manager_id TEXT NOT NULL,
    conversation_fingerprint TEXT NOT NULL UNIQUE,
    source_message_ids_json TEXT NOT NULL,
    overall_score INTEGER NOT NULL,
    scores_json TEXT NOT NULL,
    strengths_json TEXT NOT NULL,
    mistakes_json TEXT NOT NULL,
    missed_questions_json TEXT NOT NULL,
    client_intent TEXT NOT NULL,
    objections_json TEXT NOT NULL,
    deal_risk TEXT NOT NULL,
    next_best_action TEXT NOT NULL,
    recommended_reply TEXT NOT NULL,
    recommended_tasks_json TEXT NOT NULL,
    analysis_confidence REAL NOT NULL,
    crm_match_confidence REAL NOT NULL,
    rollout_mode TEXT NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'not_required',
    analysis_source TEXT NOT NULL DEFAULT 'telegram_userbot',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS salescoach_task_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    lead_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    approval_actor TEXT,
    amocrm_note_id TEXT,
    amocrm_task_id TEXT,
    verification_status TEXT NOT NULL,
    failure_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(analysis_id) REFERENCES conversation_analyses(id)
);
```

Store JSON fields with `ensure_ascii=False`, but never log the JSON payload.

- [ ] **Step 4: Wire initialization in boot**

Create one store instance from the existing DB singleton and call `await store.initialize()` during boot after DB connectivity is ready. Initialization failure must log a warning and leave Telegram SalesCoach disabled rather than crashing the whole bot.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_telegram_salescoach_store.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/services/core/telegram_salescoach_store.py src/boot.py tests/test_telegram_salescoach_store.py
git commit -m "feat(oisha): persist Telegram sales analyses"
```

---

### Task 4: Telegram Filtering, Batching and Orchestration

**Files:**
- Create: `src/services/core/telegram_salescoach.py`
- Create: `tests/test_telegram_salescoach.py`
- Modify: `src/handlers/message_handler.py`
- Modify: `src/main.py`
- Modify: `src/settings.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class TelegramConversationMessage:
    id: int
    role: Literal["manager", "customer"]
    text: str
    sent_at: datetime

@dataclass(frozen=True)
class CrmMatch:
    lead_id: int
    contact_id: int | None
    responsible_user_id: int
    confidence: float
    crm_status: str

class TelegramSalesCoach:
    async def handle_private_event(self, event, *, sender, client) -> None: ...
    async def analyze_dialog_now(self, telegram_user_id: int) -> dict[str, object] | None: ...
```

Dependencies are injected: `store`, `salescoach_sync`, `crm_matcher`, `task_writer`, `personal_sender_checker`, `internal_user_ids`, and `mode`.

- [ ] **Step 1: Write privacy and eligibility tests**

```python
@pytest.mark.asyncio
async def test_personal_folder_sender_is_never_analyzed(coach, event, sender):
    coach.personal_sender_checker = AsyncMock(return_value=True)
    await coach.handle_private_event(event, sender=sender, client=client)
    coach.salescoach_sync.analyze_conversation.assert_not_awaited()

@pytest.mark.asyncio
async def test_bot_and_internal_team_are_never_analyzed(coach):
    await coach.handle_private_event(bot_event, sender=bot_sender, client=client)
    await coach.handle_private_event(team_event, sender=team_sender, client=client)
    coach.salescoach_sync.analyze_conversation.assert_not_awaited()

@pytest.mark.asyncio
async def test_unmatched_crm_dialog_is_not_sent_to_salescoach(coach):
    coach.crm_matcher.match.return_value = None
    await coach.analyze_dialog_now(555)
    coach.salescoach_sync.analyze_conversation.assert_not_awaited()
```

- [ ] **Step 2: Write fingerprint and batching tests**

```python
def test_fingerprint_is_stable_and_text_sensitive():
    first = conversation_fingerprint(42, sample_messages())
    second = conversation_fingerprint(42, sample_messages())
    changed = conversation_fingerprint(42, sample_messages(last_text="Yangi xabar"))
    assert first == second
    assert first != changed

@pytest.mark.asyncio
async def test_batch_is_limited_to_last_50_messages(coach):
    coach.message_loader.return_value = make_messages(80)
    await coach.analyze_dialog_now(555)
    payload = coach.salescoach_sync.analyze_conversation.await_args.kwargs
    assert len(payload["messages"]) == 50
```

Fingerprint input must include `lead_id`, ordered message IDs, roles, sent timestamps rounded to seconds, and `sha256(text)` for each message. The raw text itself is not stored in the fingerprint string.

- [ ] **Step 3: Add mode behavior tests**

```python
@pytest.mark.asyncio
async def test_shadow_mode_never_calls_task_writer(coach):
    coach.mode = "shadow"
    await coach.analyze_dialog_now(555)
    coach.task_writer.apply_analysis.assert_not_awaited()

@pytest.mark.asyncio
async def test_low_confidence_analysis_never_auto_writes(coach):
    coach.mode = "auto"
    coach.salescoach_sync.analyze_conversation.return_value = analysis(confidence=0.60)
    await coach.analyze_dialog_now(555)
    coach.task_writer.apply_analysis.assert_not_awaited()
```

- [ ] **Step 4: Implement filtering and message normalization**

Eligibility order:

1. Feature flag enabled.
2. Incoming event is private user chat and not Saved Messages.
3. Sender is not a bot.
4. Sender is not in `SALESCOACH_INTERNAL_TELEGRAM_IDS`.
5. Existing personal folder checker returns false.
6. CRM matcher returns a lead with confidence at least `0.60`.
7. Batch has both manager and customer roles.
8. Fingerprint has not been analyzed.

Message text is trimmed, blank/media-only messages are skipped, and voice transcript text may be included only when already available from the existing voice processor.

- [ ] **Step 5: Implement debounce**

Keep one asyncio task per Telegram user. Each new eligible message cancels and replaces the task. Default delay is `TELEGRAM_SALESCOACH_IDLE_SECONDS=600`. The delayed task calls `analyze_dialog_now(user_id)` and catches/logs only exception type plus hashed conversation ID.

- [ ] **Step 6: Wire the lightweight handler hook**

Add to `message_handler.py`:

```python
async def process_telegram_salescoach(event, *, sender, client, telegram_salescoach) -> None:
    if telegram_salescoach is None:
        return
    await telegram_salescoach.handle_private_event(event, sender=sender, client=client)
```

Call it after checkpoint and finance/admin special handlers, but before any auto-reply logic. It must not return `True` or stop normal message processing.

`main.py` only builds the singleton and passes it to the handler. Business logic stays in the new service.

- [ ] **Step 7: Add settings with safe defaults**

```python
TELEGRAM_SALESCOACH_ENABLED: bool = False
TELEGRAM_SALESCOACH_MODE: str = "shadow"
TELEGRAM_SALESCOACH_IDLE_SECONDS: int = 600
SALESCOACH_INTERNAL_TELEGRAM_IDS: list[int] = []
```

Validate mode against `{"shadow", "approval", "auto"}`; invalid values fall back to `shadow` with a warning that contains no secret values.

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_telegram_salescoach.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/services/core/telegram_salescoach.py src/handlers/message_handler.py src/main.py src/settings.py tests/test_telegram_salescoach.py
git commit -m "feat(oisha): orchestrate Telegram sales coaching"
```

---

### Task 5: AmoCRM Task Writer, Dedupe and Verification

**Files:**
- Create: `src/services/core/crm/salescoach_task_writer.py`
- Create: `tests/test_salescoach_task_writer.py`

**Interfaces:**
- Produces:

```python
class SalesCoachTaskWriter:
    async def apply_analysis(
        self,
        *,
        analysis_id: int,
        lead_id: int,
        responsible_user_id: int,
        conversation_fingerprint: str,
        analysis: dict[str, object],
        mode: Literal["approval", "auto"],
        approval_actor: str | None = None,
    ) -> list[TaskWriteResult]: ...
```

Injected AmoCRM adapter must expose:

```python
async def get_lead(lead_id: int) -> dict: ...
async def list_open_tasks(lead_id: int) -> list[dict]: ...
async def create_note(lead_id: int, text: str) -> dict: ...
async def create_task(payload: dict) -> dict: ...
async def get_task(task_id: int) -> dict: ...
async def list_notes(lead_id: int) -> list[dict]: ...
```

- [ ] **Step 1: Write responsible manager tests**

```python
@pytest.mark.asyncio
async def test_task_uses_lead_responsible_user(writer, amo):
    amo.get_lead.return_value = {"id": 42, "responsible_user_id": 777}
    amo.create_task.return_value = {"id": 9001}
    amo.get_task.return_value = {
        "id": 9001,
        "entity_id": 42,
        "responsible_user_id": 777,
        "text": "Mijozga javob bering",
        "complete_till": fixed_deadline,
    }

    result = await writer.apply_analysis(**auto_analysis_args())

    assert result[0].verified is True
    assert amo.create_task.await_args.args[0]["responsible_user_id"] == 777
```

- [ ] **Step 2: Write dedupe tests**

```python
@pytest.mark.asyncio
async def test_existing_open_same_type_task_blocks_duplicate(writer, amo):
    amo.list_open_tasks.return_value = [{"id": 1, "text": "Mijozga javob bering", "is_completed": False}]
    await writer.apply_analysis(**auto_analysis_args())
    amo.create_task.assert_not_awaited()

@pytest.mark.asyncio
async def test_local_idempotency_key_blocks_retry_duplicate(writer, store):
    store.task_key_exists.return_value = True
    await writer.apply_analysis(**auto_analysis_args())
    writer.amocrm.create_task.assert_not_awaited()
```

- [ ] **Step 3: Write verification failure tests**

```python
@pytest.mark.asyncio
async def test_mismatched_responsible_user_is_not_reported_as_success(writer, amo):
    amo.get_lead.return_value = {"id": 42, "responsible_user_id": 777}
    amo.create_task.return_value = {"id": 9001}
    amo.get_task.return_value = {"id": 9001, "entity_id": 42, "responsible_user_id": 13021974}

    result = await writer.apply_analysis(**auto_analysis_args())

    assert result[0].verified is False
    assert result[0].failure_code == "responsible_user_mismatch"
    writer.admin_notifier.notify_write_failure.assert_awaited_once()
```

- [ ] **Step 4: Implement task recommendation allowlist**

Exact mapping:

```python
TASK_RULES = {
    "reply_customer": ("Mijozga javob bering", timedelta(minutes=30), "call"),
    "schedule_meeting": ("Uchrashuv vaqtini belgilang", "today_18_00", "call"),
    "send_proposal": ("Moslashtirilgan taklif/KP yuboring", timedelta(hours=2), "follow_up"),
    "follow_up": ("Follow-up qiling", timedelta(hours=24), "follow_up"),
    "send_material": ("Va’da qilingan materialni yuboring", timedelta(hours=1), "follow_up"),
    "manager_review": ("Rahbar bilan suhbatni ko‘rib chiqing", "today_18_00", "follow_up"),
}
```

`today_18_00` means 18:00 Asia/Tashkent; if current local time is after 18:00, use next business day at 10:00.

- [ ] **Step 5: Implement note write**

The note contains score, intent, risk, objection summary, next action, evidence IDs and marker:

```text
[OISHA_SALESCOACH]
Score: 64/100
Intent: warm
Risk: medium
Next: Uchrashuv vaqtini belgilang
Evidence: 1001,1002
Fingerprint: abcd1234...
```

Do not include the full Telegram transcript or phone number.

- [ ] **Step 6: Implement task write and verification**

For each allowlisted recommendation:

1. Derive idempotency key.
2. Check local audit.
3. Check existing open task text.
4. Read lead and use its current `responsible_user_id`.
5. Create task.
6. Fetch task by ID.
7. Verify entity ID, responsible user, normalized text and deadline tolerance ±60 seconds.
8. Record audit result.
9. Notify admin on mismatch.

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_salescoach_task_writer.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/services/core/crm/salescoach_task_writer.py tests/test_salescoach_task_writer.py
git commit -m "feat(oisha): write verified SalesCoach tasks to AmoCRM"
```

---

### Task 6: Approval Mode and Sales Quality API

**Files:**
- Modify: `src/handlers/message_handler.py`
- Modify: `src/api/routes/sales_quality.py`
- Modify: `src/services/core/telegram_salescoach_store.py`
- Modify: `tests/test_telegram_salescoach.py`
- Create: `tests/test_sales_quality_conversations.py`

**Interfaces:**
- Approval callback data format:

```text
salescoach:approve:<analysis_id>
salescoach:reject:<analysis_id>
```

- API:

```text
GET /api/sales-quality/conversations?limit=100
GET /api/sales-quality/conversations/{analysis_id}
```

- [ ] **Step 1: Write approval mode tests**

```python
@pytest.mark.asyncio
async def test_approval_mode_sends_buttons_but_does_not_write(coach):
    coach.mode = "approval"
    await coach.analyze_dialog_now(555)
    coach.approval_notifier.send.assert_awaited_once()
    coach.task_writer.apply_analysis.assert_not_awaited()

@pytest.mark.asyncio
async def test_owner_approval_writes_once(coach, store):
    store.mark_approved.return_value = True
    await coach.approve_analysis(analysis_id=12, actor_id=999)
    coach.task_writer.apply_analysis.assert_awaited_once()
```

Reject non-owner/non-sales-lead actors and repeated approvals.

- [ ] **Step 2: Implement approval notification**

Telegram admin summary must contain:

- Client display name or CRM lead name, never phone number.
- Score and risk.
- Short mistakes and next action.
- Proposed task text and deadline.
- Inline buttons `Tasdiqlash` and `Bekor qilish`.

No customer message transcript is included in the approval message.

- [ ] **Step 3: Implement callback handling**

Callbacks are owner/sales-lead only. `mark_approved` or `mark_rejected` uses an atomic status update from `pending` so the same analysis cannot be executed twice.

- [ ] **Step 4: Write API tests**

```python
def test_conversation_list_returns_real_source_metadata(client, seeded_analysis):
    response = client.get("/api/sales-quality/conversations?limit=10", headers=auth_headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["source"] == "telegram_userbot"
    assert item["real_data"] is True
    assert item["confidence"] == 0.91

def test_viewer_response_hides_recommended_reply(client, seeded_analysis, viewer_headers):
    response = client.get(f"/api/sales-quality/conversations/{seeded_analysis}", headers=viewer_headers)
    assert "recommended_reply" not in response.json()
```

- [ ] **Step 5: Implement API routes**

List returns redacted metadata: analysis ID, lead ID, manager ID, score, risk, intent, confidence, mode, approval status, created time and evidence count. Detail route includes strengths/mistakes/next action for authorized roles. It never returns the raw transcript because it is not stored.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_telegram_salescoach.py tests/test_sales_quality_conversations.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/handlers/message_handler.py src/api/routes/sales_quality.py src/services/core/telegram_salescoach_store.py tests/test_telegram_salescoach.py tests/test_sales_quality_conversations.py
git commit -m "feat(oisha): add SalesCoach approval workflow"
```

---

### Task 7: End-to-End Safety, Shadow Rollout and Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/salescoach-architecture.md`
- Modify: deployment environment templates or service unit files that already hold Oisha feature flags.
- Test: all related Python and TypeScript suites.

**Interfaces:**
- Production flags:

```env
TELEGRAM_SALESCOACH_ENABLED=0
TELEGRAM_SALESCOACH_MODE=shadow
TELEGRAM_SALESCOACH_IDLE_SECONDS=600
SALESCOACH_ENABLED=0
```

No secret values are committed.

- [ ] **Step 1: Add a synthetic integration test with fake adapters**

The test must run this complete flow without external network:

```text
eligible Telegram DM
→ CRM match lead 42 / responsible 777 / confidence 0.93
→ SalesCoach response score 74 / confidence 0.91
→ store analysis
→ shadow mode prevents task write
→ switch to approval mode
→ owner approval
→ note/task creation through fake AmoCRM
→ verification passes
→ audit status verified
```

- [ ] **Step 2: Run focused Python tests**

```bash
pytest \
  tests/test_salescoach_sync_conversation.py \
  tests/test_telegram_salescoach_store.py \
  tests/test_telegram_salescoach.py \
  tests/test_salescoach_task_writer.py \
  tests/test_sales_quality_conversations.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run full Python quality gates**

```bash
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll
```

Expected: all tests pass; Bandit reports no medium/high issues.

- [ ] **Step 4: Run TypeScript gates**

```bash
cd salescoach-ai
pnpm --filter @salescoach/api test -- negotiations.controller.spec.ts negotiations.service.spec.ts
pnpm --filter @salescoach/api exec tsc --noEmit
```

Expected: PASS.

- [ ] **Step 5: Update architecture and operator notes**

Document:

- Oracle remains sole owner of userbot session.
- Feature is enabled in shadow mode first.
- How to inspect recent analyses through API/dashboard.
- How to move from shadow to approval.
- Auto mode is not enabled until at least 7 days of shadow data has been reviewed and task precision is at least 95% on a manually checked sample of at least 40 recommendations.
- Rollback is `TELEGRAM_SALESCOACH_ENABLED=0` plus service restart.
- No raw Telegram transcript is persisted by this module.

- [ ] **Step 6: Deploy shadow mode through the existing Oracle deployment path**

Use the existing GitHub Actions/self-hosted runner process. After deploy, verify:

```text
/healthz is healthy
Telegram userbot remains authorized
SalesCoach API source health is healthy
AmoCRM source health is healthy
At least one eligible test dialog produces a stored analysis
No AmoCRM task is created in shadow mode
```

Do not enable `approval` or `auto` during this deployment task.

- [ ] **Step 7: Commit documentation and rollout config**

```bash
git add AGENTS.md docs/salescoach-architecture.md
git commit -m "docs: document Telegram SalesCoach shadow rollout"
```

- [ ] **Step 8: Open a pull request**

PR title:

```text
feat: analyze Telegram sales chats and create verified AmoCRM tasks
```

PR body must include:

- Summary of data flow.
- Privacy exclusions.
- Test commands and outputs.
- Confirmation that default mode is shadow.
- Confirmation that no new Telegram session was created.
- Link to issue `#418`.

---

## Plan Self-Review Results

- **Spec coverage:** Privacy filtering, CRM matching thresholds, weighted scoring, persistence, responsible manager, dedupe, verification, approval and shadow rollout are each assigned to explicit tasks.
- **Scope:** This plan delivers one coherent vertical feature; dashboard styling and automatic customer replies remain outside scope.
- **Type consistency:** `lead_id/leadId`, `manager_id/managerId`, message roles, analysis confidence and task recommendation enums are explicitly mapped at the HTTP boundary.
- **Ambiguity resolved:** “Shu kun” deadline is 18:00 Asia/Tashkent; after 18:00 it becomes the next business day at 10:00.
- **Production safety:** Default is shadow, userbot ownership stays on Oracle, raw transcript is not persisted, and rollback is feature-flag based.
