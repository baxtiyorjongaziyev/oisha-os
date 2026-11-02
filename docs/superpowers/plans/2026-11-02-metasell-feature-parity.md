# Metasell Feature Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all missing high-impact Metasell Console features into Oisha-OS: Speed-to-Lead SLA Tracking, Stuck Deals Radar, Marketing Ad Attribution (CPL/CAC), AI Sales Practice Simulator, Morning Task Triage Engine, Knowledge Quiz, and Executive Dashboard Aggregator.

**Architecture:** Modular Python 3.12 architecture conforming to Oisha-OS standards (150-400 lines per module, functions <= 60 lines, double quotes for Uzbek text, zero bandit issues). Services reside in `src/services/command_center/` and `src/services/ai/`, exposed via REST endpoints in `src/api/routes/`.

**Tech Stack:** Python 3.12, FastAPI / Starlette, Pydantic, Pytest.

**Spec:** Gap analysis between Metasell Console and Oisha-OS conducted on 2026-11-01.

---

## Global Constraints

- Every production `.py` file must strictly stay between 150 and 400 lines.
- Functions must stay between 20 and 60 lines.
- Uzbek text in code must use double quotes `"..."` and proper letters (`ö`/`ğ` or `ʻ`/`ʼ`), NEVER ASCII `'` inside words (e.g. `"qo'ng'iroq"` is forbidden).
- No hardcoded secrets, tokens, or credentials.
- Bandit security scan must pass with 0 issues (`-ll`).

---

## Tasks

### Task 1: Speed to Lead (SLA Response Tracking) Service
**Files:**
- Create: `src/services/command_center/speed_to_lead.py`
- Test: `tests/test_speed_to_lead.py`

- [ ] Write failing test in `tests/test_speed_to_lead.py` checking response bucket categorization (`<15m`, `15-30m`, `30-60m`, `1-2h`, `>2h`, `unanswered`), SLA compliance rate calculation, and longest-waiting customer detection.
- [ ] Implement `src/services/command_center/speed_to_lead.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 2: Stuck Deals Radar (Qolib Ketgan Bitimlar)
**Files:**
- Create: `src/services/command_center/stuck_deals.py`
- Test: `tests/test_stuck_deals.py`

- [ ] Write failing test in `tests/test_stuck_deals.py` verifying stage duration calculation, threshold filtering, oldest stuck deal detection, and stage-by-stage aggregations.
- [ ] Implement `src/services/command_center/stuck_deals.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 3: Marketing Ad Attribution & ROI Engine (CPL / CAC)
**Files:**
- Create: `src/services/command_center/ad_attribution.py`
- Test: `tests/test_ad_attribution.py`

- [ ] Write failing test in `tests/test_ad_attribution.py` for spend calculation, lead count, CPL, sales count, CAC, revenue, and conversion rate.
- [ ] Implement `src/services/command_center/ad_attribution.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 4: AI Sales Practice Simulator Engine
**Files:**
- Create: `src/services/ai/sales_simulator.py`
- Test: `tests/test_sales_simulator.py`

- [ ] Write failing test in `tests/test_sales_simulator.py` for scenario generation (`first_30_seconds`, `too_expensive`, etc.), hidden fact revelation logic, and turn-by-turn coaching feedback.
- [ ] Implement `src/services/ai/sales_simulator.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 5: Morning Task Triage & Secure Daily Review Engine
**Files:**
- Create: `src/services/command_center/morning_tasks.py`
- Test: `tests/test_morning_tasks.py`

- [ ] Write failing test in `tests/test_morning_tasks.py` for task categorization (Today vs Overdue), bulk actions (`done`, `dismiss_today`, `reschedule`), and ephemeral secure audio review token generation.
- [ ] Implement `src/services/command_center/morning_tasks.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 6: Knowledge Base & AI Quiz Engine
**Files:**
- Create: `src/services/ai/knowledge_quiz.py`
- Test: `tests/test_knowledge_quiz.py`

- [ ] Write failing test in `tests/test_knowledge_quiz.py` for quiz question generation from playbook topics, answer evaluation, and scoring.
- [ ] Implement `src/services/ai/knowledge_quiz.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 7: Executive Dashboard Aggregator & API Endpoint
**Files:**
- Create: `src/api/routes/metasell_dashboard.py`
- Test: `tests/test_metasell_dashboard_api.py`

- [ ] Write failing test in `tests/test_metasell_dashboard_api.py` verifying `/api/dashboard/metasell-executive` payload structure (Hero, Speed to Lead, Stuck Deals, Ads, Attention, Leaderboard).
- [ ] Implement `src/api/routes/metasell_dashboard.py` (150-400 lines).
- [ ] Run test to verify passes.

### Task 8: Verification & Pre-flight
- [ ] Run all newly created tests.
- [ ] Run Uzbek text check: `python scripts/check_uzbek_text.py --staged`.
- [ ] Run bandit security check: `bandit -r src/ -ll`.
