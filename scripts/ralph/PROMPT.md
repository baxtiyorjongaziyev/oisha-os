# Ralph Dev Loop — iteration prompt

You are one iteration of an autonomous dev loop on the Oisha-OS repo.
Each iteration starts with a fresh context. State lives ONLY in files:
`scripts/ralph/PLAN.md` (task checklist), `scripts/ralph/PROGRESS.md` (notes), git history.

## Each iteration, do exactly this

1. Read `scripts/ralph/PLAN.md` and `scripts/ralph/PROGRESS.md`.
2. Pick the FIRST unchecked item (`- [ ]`). Do only that one item.
3. Implement it with the smallest correct change. Read only relevant files.
4. Verify:
   - `SKIP_LIVE=1 python -m pytest -q --tb=short` (or the focused test file first, then full suite)
   - `bandit -r src/ -ll -x src/services/debug/ --quiet`
5. If both pass:
   - Mark the item `- [x]` in PLAN.md.
   - Append 1–3 lines to PROGRESS.md (what changed, anything the next iteration must know).
   - `git add` only the files you touched + PLAN.md + PROGRESS.md, then
     `git commit -m "<type>(<scope>): <message> [ralph]"`.
6. If you cannot make it pass after a reasonable attempt:
   - Revert your uncommitted changes to touched files (`git checkout -- <files>`).
   - Mark the item `- [!]` with a one-line reason in PLAN.md, note it in PROGRESS.md, commit.
7. Stop. Do not start a second item.

## Hard rules (never break)

- NEVER run `src/main.py`, `userbot.py`, `admin_bot.py`, or anything that opens a Telethon
  session. Oracle owns the production session (AuthKeyDuplicatedError risk).
- NEVER call live external APIs (AmoCRM, Telegram, Meta, Gemini). Tests run with `SKIP_LIVE=1`.
- NEVER push, merge, deploy, force-push, or touch `.env` / secrets.
- Do not edit: `src/services/debug/`, `src/legacy/`, `settings.py`, `context.py`, `boot.py`
  (coordinator-owned) unless the PLAN item explicitly says so.
- Do not weaken, skip, or delete existing tests to make them pass.
- Respect `AGENTS.md` Locks section.
- When all items are `[x]` or `[!]`, write `RALPH_DONE` as the last line of PROGRESS.md.
