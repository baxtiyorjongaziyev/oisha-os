---
trigger: always_on
---
# oisha-os: engineering agreement

Read AGENTS.md; load only task-relevant sections of linked documents. Its scoped workflow is canonical. Keep ALLOW_LOCAL_RUN=0 and SKIP_LIVE=1 for local tests. Never start src/main.py or a production Telegram session locally. Keep apps/, packages/ and salescoach-ai/ package boundaries distinct. Handoff goes at the END of docs/agents/handoff-log.md.

- Start by identifying the repository, branch, dirty files, applicable locks and acceptance criteria. Preserve other agents' changes.
- Work directly by default; use subagents only when the owner requests them. Only then read the three-agent agreement. One implementer per checkout; independent concurrent writers need separate Git worktrees. Reviewer/analyst do not edit implementation files.
- Owner preference (2026-10-04): local diagnosis, scoped edits and checks proceed autonomously. Production deploy, merge and external writes (CRM, finance, Telegram and other connected systems) require explicit owner authorization for the action. Prepare and verify a concrete result before asking; do not ask again when the same action is already authorized. A setup task is not blanket external-write authorization.
- Use rtk for shell commands. Keep secrets, .env, sessions and customer payloads out of prompts, logs, commits and artifacts. Do not start services merely to check IDE configuration.
- For fixes, reproduce the failure before editing; run the checks relevant to the change and required repo gates. Never hide failures, skip tests to get green, or weaken assertions.
- Review the complete task diff (in bounded chunks if large) for correctness, privacy, authorization, failure handling and regressions; preserve unrelated staged/unstaged changes. Do not audit unrelated work. Report actionable findings with severity, file/line and evidence.
- Finish with changed files, commands/results and remaining blockers in the project log. Say local/committed/pushed/deployed separately. Report in concise natural Uzbek: bajarildi / qisman / ochiq.
