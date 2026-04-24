# gstack Review

**Source:** https://github.com/garrytan/gstack  
**Reviewed:** 2026-04-24  
**Reviewer:** Claude (automated review on branch `claude/review-gstack-ZMeKZ`)

---

## What Is gstack?

gstack is an open-source Claude Code skills framework by Garry Tan (Y Combinator President & CEO). It transforms Claude Code into a structured "engineering team" by providing 23+ composable skills covering the full development lifecycle:

```
Think → Plan → Build → Review → Test → Ship → Reflect
```

Tech stack: TypeScript/Bun, Playwright/Chromium for browser automation, MIT licensed.

---

## Architecture

### Skill System

Each skill is a directory (e.g. `review/`, `ship/`, `cso/`) with a `SKILL.md` generated from a `.tmpl` template via `bun run gen:skill-docs`. Skills are invoked as slash commands (`/review`, `/ship`, `/cso`). This is a clean, discoverable pattern: documentation and behavior live together, templates enforce consistency across skills.

### Two-Tier Testing

- **Gate tests** (`bun test`) — free, run on every change, fast feedback
- **Eval tests** (`bun run test:evals`) — paid LLM calls, run periodically or on relevant diffs

Diff-based auto-selection prevents unnecessary paid runs. This is a disciplined approach to managing AI evaluation cost that oisha-os could mirror (cheap unit tests vs. expensive live Gemini/CRM checks).

### Sub-Agent Dispatch

The `/review` skill dispatches 7–8 specialist sub-agents in parallel (security, data migration, API surface, etc.) and gates each on relevance. Confidence scoring (1–10) filters noise. Results are persisted to `~/.gstack/analytics/` for trend tracking.

### Version Queue Management (v1.11)

`/ship` queries open PRs to detect version claims before bumping, preventing silent overwrites in parallel sprint environments. A non-trivial coordination problem solved cleanly.

### Dual-Listener Tunnel Security

Separates local (dev) and remote (public) listeners at the tunnel layer, with HttpOnly SSE cookies and ngrok restriction. Relevant for oisha-os which runs both a Cloud Run API and a VM userbot simultaneously.

---

## Strengths

**1. Lifecycle completeness.** Every phase from product ideation (`/office-hours`) through post-deploy monitoring (`/canary`) is covered. Most teams only automate the middle.

**2. Security depth.** The `/cso` skill runs a 14-phase scan including git history secrets archaeology, CI/CD permission audits, and LLM-specific attack vectors (prompt injection, unsanitized AI output). Few open-source dev tools have this coverage.

**3. Ethos-driven design.** `ETHOS.md` defines three non-negotiable principles:
- *Boil the Lake* — complete the implementation when marginal cost is low
- *Search Before Building* — understand conventions before innovating
- *User Sovereignty* — AI recommends, humans decide

These prevent scope creep and half-finished work, which are common failure modes in AI-assisted development.

**4. Observability built-in.** `/retro` tracks commits, contributor velocity, work-session detection, and hotspot analysis with JSON persistence. Most projects instrument their products but not their own dev process.

**5. Platform-agnostic design.** Skills avoid hardcoding Claude Code patterns, supporting Codex, Cursor, OpenCode, Factory Droid. This increases longevity.

---

## Weaknesses / Risks

**1. Bun/TypeScript lock-in.** The runtime choice optimizes for compiled binaries and native SQLite but limits contribution from Python/Node ecosystems. For a tool targeting diverse AI development workflows, this narrows the contribution surface.

**2. Browser automation brittleness.** Headless Chromium with anti-bot stealth (`connect-chrome`, `open-gstack-browser`) works until it doesn't. Web UI testing against accessibility trees is more stable than DOM selectors but still breaks on major redesigns.

**3. Confidence scoring is uncalibrated.** The `/review` skill uses 1–10 confidence thresholds to gate sub-agents, but these are heuristic values with no explicit calibration methodology documented. A finding at 7.9 vs. 8.0 can produce different behavior with no principled reason.

**4. Prompt injection surface.** The `/guard` skill exists but the LLM-generated outputs piped into subsequent skills (e.g., `/review` → `/ship`) are a live attack surface. Defense against indirect prompt injection in multi-hop skill chains is partially addressed but not proven.

**5. Cost opacity.** The `/ship` skill runs tests, bumps versions, generates changelogs, and opens PRs "without intermediate permission requests." This is powerful but means a single misfire can produce unintended side effects at scale (wrong version, wrong PR). The design trusts the LLM more than a human-in-the-loop gating model would.

---

## Relevance to Oisha-OS

oisha-os already shares several architectural patterns with gstack, suggesting the design directions are independently valid:

| Pattern | gstack | oisha-os |
|---|---|---|
| Tool registry / adapter layer | `lib/` + skill system | `tool_registry.py`, `tool_adapters.py` |
| Planner / Executor / Verifier | Sub-agent dispatch in `/review` | `agent_loop.py` (Phase 3 roadmap) |
| Confidence-based gating | `/review` confidence scoring | Not yet implemented |
| Observability / audit trail | `/retro`, analytics JSON | `agent_verifier.py`, `/api/system/traces` |
| Guardrails / policy gates | `ETHOS.md`, `/careful`, `/freeze` | `agent_policy.py`, quiet-hours |
| Security scanning | `/cso` 14-phase scan | Not yet implemented |

### Actionable Recommendations

**1. Add a confidence threshold to AI responses.**  
oisha-os's `NegotiationEngine` and `SurgicalNegotiator` return AI-generated actions that go directly to CRM or Telegram. Attaching a confidence score (e.g., from Gemini's `safety_ratings` or a prompt-level self-assessment) and gating low-confidence actions for human review would reduce costly errors on live leads.

**2. Adopt diff-based test selection.**  
Currently CI runs all tests on every push. With the growing suite (`tests/`), split into fast gate tests (always run) and slow live-API tests (run only when relevant files change). See gstack's two-tier model.

**3. Implement a `/cso`-equivalent security pass.**  
oisha-os handles Telegram auth tokens, AmoCRM credentials, and Google OAuth. A periodic audit script covering: tracked `.env` files in git history, hardcoded credentials in debug scripts (`src/services/debug/`), and CI secret exposure would reduce credential leak risk. The `src/services/debug/` directory contains ~90 scripts, many importing credentials — this is the highest-risk surface.

**4. Version the agent schema explicitly.**  
gstack uses monotonic release identifiers with per-branch changelog entries. oisha-os has no versioning beyond git tags. As the agent loop (`agent_loop.py`) matures and tools accumulate, breaking changes to `ToolResult` schema or `TaskObject` model need explicit versioning to avoid silent regressions in long-running Cloud Run deployments.

**5. Persist agent retrospectives.**  
gstack's `/retro` stores JSON snapshots for trend analysis. oisha-os's `/api/system/traces` exists but is ephemeral (in-memory or short-lived DB rows). Persisting weekly snapshots of: task success rate, retry rate per tool, quiet-hours violation count, and Gemini token cost would surface operational patterns that are otherwise invisible.

---

## Summary

gstack is a well-engineered meta-tool for AI-assisted development. Its strongest contributions are lifecycle completeness, security depth via `/cso`, and principled ethos enforcement. The main risks are LLM trust without calibration, prompt injection in multi-hop chains, and cost opacity in automated ship flows.

For oisha-os, the most directly applicable patterns are confidence-gated actions, diff-based CI test selection, a periodic security audit of the `debug/` script surface, and explicit agent schema versioning. The architectural directions (tool registry, planner/executor/verifier, policy gates) are already aligned — execution depth is the gap.
