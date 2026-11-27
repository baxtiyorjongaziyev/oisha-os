---
name: agent-harness-workflow
description: Use for software changes in Oisha-OS that require planning, debugging, implementation, independent review, QA, or release evidence across Claude Code, Codex, and Antigravity.
---

# Oisha-OS Agent Harness Workflow

## 1. Scope

This is a native Oisha-OS adaptation of engineering methods from ECC, Superpowers and GStack, not an upstream package installation. The mandatory `.agents/skills/harness-loop/SKILL.md`, AGENTS.md, CLAUDE.md, code-mode and owner approval rules take precedence. This overlay is for planning, implementation and review; it does not replace the mandatory lifecycle. The canonical skill lives under `.claude/skills/`; keep its `.agents/skills/` mirror byte-identical using `python scripts/sync_agent_skills.py --check`. Do not use this skill to authorize live business actions or replace the runtime agent architecture.

## 2. Inputs

Read AGENTS.md, CLAUDE.md, docs/agents/three-agent-workflow.md and subsystem-specific rules. Identify the request, affected subsystem, acceptance criteria, current branch/status, active file locks, available test commands and required permissions. Do not inspect secrets or production sessions.

## 3. Execution

### Plan (Antigravity/analyst or assigned analyst)
- Distinguish the business problem from the requested implementation. Define a measurable outcome, minimal scope, alternatives and non-goals.
- Identify impacted interfaces, data integrity, security, regression and rollback risks. For UI changes include user journeys and error/empty/loading states.
- Specify exact acceptance tests and hand the plan to the implementer. Small changes need only a short plan.

### Implement (Codex or assigned implementer)
- Use a dedicated branch/worktree with one writer per file. Preserve unrelated edits and respect active locks.
- For behavior changes, first reproduce the defect or add a test that fails for the intended reason. Implement the smallest fix, rerun the test and refactor only as necessary. Document exceptions such as documentation-only work.
- If debugging, trace the failing input through the responsible layer, test one hypothesis at a time, and verify root cause before changing code. Never retry a live mutation merely to reproduce a bug.
- Keep production code within existing size and dependency constraints. Never run the production Telegram userbot locally.

### Review (Claude Code or assigned independent reviewer)
- Read the actual diff against its base. Do not edit the implementer's files.
- Check acceptance criteria, logic, error paths, input validation, authorization, secret exposure, external writes, idempotency, race conditions, migrations and regression coverage as applicable.
- Report actionable findings with file/line, severity, impact and suggested fix. Distinguish verified findings from untested risks. If no independent reviewer is available, mark that gate NOT RUN; do not invent agreement.

### Verify and QA (ECC-style evidence gate, GStack-style journey review)
- Run focused tests and relevant lint, typecheck, build and coverage checks for the changed subsystem. Use mocks, fixtures or isolated test environments; no production writes.
- For changes with UI/API journeys, verify expected behavior and failure paths with safe fixtures or an authorized test environment. Do not claim browser/API QA if it was not performed.
- Before every push and PR, follow the mandatory harness-loop gate (and AGENTS.md):
  - `SKIP_LIVE=1 python -m pytest -q --tb=short` (set environment variable using shell-appropriate syntax)
  - `bandit -r src/ -ll`
  - `ruff check --select F821,F822,ASYNC210,ASYNC221 --per-file-ignores "src/config.py:F822" src/`
  - `python scripts/check_uzbek_text.py --base origin/main` (fetch the base first; also use `--staged` for staged edits)
  - `python scripts/sync_agent_skills.py --check`
- Run `python scripts/harness/run_harness.py` for the local audit; a focused target is not a full-suite pass. The local audit does not replace independent review, CI or post-merge verification.
- For TypeScript changes, run applicable package-scoped checks plus relevant workspace lint, typecheck, test and build commands from CLAUDE.md. Record exit status and scope; do not hide failures using truncated pipelines.
- Fix findings and rerun affected gates. No ready PR when required pre-flight is failing or unavailable. Only an explicitly owner-authorized draft may be opened for visibility while gates remain NOT RUN or FAIL; never mark it ready or merge until the mandatory gates pass. Verify the latest commit, required CI, review threads and branch state before merge; verify main and deployment separately after merge.

### Handoff and learning
- Append evidence to `docs/agents/handoff-log.md`: task, branch, files, reviewer status, commands and results, remaining blockers. Coordinate one writer for the shared log; reconcile both entries if concurrent appends conflict. Record PR URL/status as a dated checkpoint, and re-read live GitHub state before acting; never assume a handoff is current.
- Record only reusable, verified lessons through skill-evolution; omit secrets, customer details and raw transcripts. Do not create automatic memory collection or new external integrations.

## 4. Troubleshooting and safeguards

- Conflicting skills: follow Oisha-OS rules first; this skill is a workflow overlay, not a second policy system.
- Missing runner or reviewer: label NOT RUN and retain branch for authorized verification. Do not weaken tests or CI to bypass a blocker.
- Do not install upstream hooks, MCP servers, binaries, telemetry, or auto-learning services without reviewing their source, permissions, license, pinned revision and compatibility separately.
- No direct main pushes, force pushes, local production userbot, secret reads, or approval bypasses. Production deployment and health verification are separate from local QA.

## 5. Evidence gate

Use a compact handoff:
- Acceptance criteria: PASS / FAIL / NOT RUN, evidence.
- Focused checks: command, exit status, result.
- Required pre-flight: PASS / FAIL / NOT RUN.
- Independent review: findings and resolution or NOT RUN.
- QA and deployment: tested environment, evidence or NOT RUN.
- Remaining risks and next action.

## References

Method inspirations (reference links, not installed dependencies or evidence of an upstream audit):
- ECC verification loop: https://github.com/affaan-m/ECC/blob/main/skills/verification-loop/SKILL.md
- Superpowers testing and debugging: https://github.com/obra/superpowers/tree/main/skills
- GStack product review and QA: https://github.com/garrytan/gstack/blob/main/docs/skills.md
