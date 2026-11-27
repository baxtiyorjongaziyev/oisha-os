# Harness Loop v2 walkthrough

Follow-up to [PR #1195](https://github.com/baxtiyorjongaziyev/oisha-os/pull/1195).

- Restore canonical Claude skill and synchronize the agent mirror.
- Make the engineering overlay subordinate to the mandatory harness lifecycle.
- Extend the runner with Ruff, committed branch text, staged text and skill mirror checks. Use the interpreter that launched the runner rather than a Windows-only path.
- Distinguish focused tests and local checks from full release evidence. Coordinate shared handoffs and verify live PR state.

## Verification in an authorized clean checkout

```bash
git fetch origin main
python -m pytest -q tests/test_harness.py tests/test_harness_loop.py
python scripts/sync_agent_skills.py --check
python scripts/harness/run_harness.py
```

Run the mandatory lifecycle gates on the final commit; a local pass does not establish independent review, remote CI, or production health. The connector-only authoring session has not executed these commands. No production runtime change is intended. Do not include credentials or production sessions in test checkouts.

Rollback: revert the follow-up PR after reviewing its diff; note that restoring the pre-v2 skill mirror mismatch would reintroduce the known defect.
