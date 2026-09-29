# Ralph PLAN

One item per iteration. `- [ ]` todo · `- [x]` done · `- [!]` blocked (reason).
Keep items small and independently verifiable (one commit each).

- [x] Add unit tests for `.claude/hooks/guard.py` in `tests/test_claude_guard_hook.py`: blocked cases (local userbot run, force push, push to main, `.env` read, recursive force delete) exit 2; allowed cases (pytest, push feature branch, `.env.example`) exit 0
- [ ] Find one pure helper module in `src/services/utils/` with no matching `tests/test_*.py`, add focused unit tests for its public functions
