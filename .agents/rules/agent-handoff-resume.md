# Agent handoff: automatic resume and handoff

Applies to every task, without the user repeating it.

## At the start of every task
1. Run `powershell -NoProfile -File scripts/agent_resume.ps1` (read-only). It prints branch, git status/diff, active Locks and the last `docs/agents/handoff-log.md` entry.
2. If the last entry has "Qolgan ish" and the user's task is a continuation (or the user gave no new task), work ONLY on that remaining work.
3. If the user gives a new, unrelated task, do that instead; do not resume old work.
4. Respect Locks and other agents' uncommitted changes. Do not guess; unknown state is "noma'lum".

## During the task
- Add your lock under `## Locks` in AGENTS.md only if the owner/Coordinator allows it; otherwise report it.
- If you are about to hit a limit or stop, write the handoff immediately.

## At the end (or when stopping early)
Append to the END of `docs/agents/handoff-log.md`: date/agent, done, changed files, verification evidence, "Qolgan ish". Commit if appropriate, or leave `git status` clean of surprises. Never write secrets.
