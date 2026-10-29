# Agent handoff: scoped resume and handoff

Use resume only when the current request continues previous work. Follow AGENTS.md's scoped workflow.

## When continuing a task
1. Search `docs/agents/handoff-log.md` by task, branch or file, then read only the matching entry. The latest entry may belong to another task. `rtk proxy powershell -NoProfile -File scripts/agent_resume.ps1` is an optional read-only snapshot when that broader context is needed; do not run it on every small task.
2. Continue only the remaining work tied to the current request. With no concrete request, do not automatically adopt unrelated backlog.
3. If the user gives a new, unrelated task, do that instead; do not resume old work.
4. Respect Locks and other agents' uncommitted changes. Do not guess; unknown state is "noma'lum".

## During the task
- Add your lock under `## Locks` in AGENTS.md only if the owner/Coordinator allows it; otherwise report it.
- If you are about to hit a limit or stop, write the handoff immediately.

## At the end (or when stopping early)
Append to the END of `docs/agents/handoff-log.md`: date/agent, done, changed files, verification evidence, "Qolgan ish". Commit if appropriate, or leave `git status` clean of surprises. Never write secrets.
