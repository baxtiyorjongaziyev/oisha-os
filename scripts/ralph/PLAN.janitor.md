# Ralph JANITOR PLAN (weekly entropy cleanup)

Enforces `docs/agents/golden-principles.md`. Before starting, reset all items to `- [ ]`.
Each item: find at most ONE violation, fix it, verify, commit. If none found, mark `[x]` with "clean".

- [ ] Production file in `src/` over 400 lines (excluding facades/tests/debug) -> split per `docs/agents/code-standards.md`
- [ ] New `.md` report/handoff file in repo root (allowed: README, CLAUDE, AGENTS, CONTRIBUTING, SECURITY, DEPLOYMENT, ARCHITECTURE, ROAD_MAP, DEV_LOG, GEMINI, LICENSE) -> `git mv` to `docs/archive/`
- [ ] `AGENTS.md` over 150 lines -> move detail into `docs/agents/`, keep only links
- [ ] Released/stale entries in `AGENTS.md` `## Locks` older than 14 days -> move to `docs/agents/handoff-log.md`
- [ ] Unused import or dead function reported by `python -m pyflakes src/` (skip `src/services/debug/`) -> remove one
- [ ] Duplicate helper that re-implements something in `src/services/utils/` -> replace with shared helper
