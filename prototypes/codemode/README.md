# Code Mode prototype (not wired into prod)

`ts_api.py` renders gateway MCP tools as a TypeScript declaration. Model writes one
script against it instead of many tool calls.

Rules for any runner built on top:
- Every call -> `GatewayService.call_tool` (reads automatic, mutations `pending_approval`).
- Sandbox gets no network, no env, no session strings; only a `telegram.*` proxy binding.
- Quiet-hours/`agent_policy` enforced in the binding, not in model-written code.
- Gateway is on 127.0.0.1 (Contabo): run sandbox locally there, or Cloudflare Tunnel; never expose :8765/:8766.

Run test: `cd prototypes/codemode && python -m pytest -q`

## Sandbox honesty
- `bridge.py`: read-only; mutations refused (no approval flow yet), 200-call cap, 60s timeout, empty env.
- Layers: `node --permission` (blocks fs write, NOT network on Node 24) + `vm` context (no fetch/process/import).
- This stops naive/accidental access, **not a determined vm escape**. Before running untrusted model
  output in prod: run runner in a container with `--network none` (or a Cloudflare Worker isolate).

## Status (all prototype, nothing wired into src/ or deployed)
- `host.py` `CodeModeHost`: `telegram.*` via GatewayService + `amo.*` read-only (get_leads/get_lead/search_leads, args allowlisted, limit capped).
- `batch.py`: with `allow_mutation_batch=True` mutations are queued, never executed; script end -> ONE `codemode_batch` approval (max 20, destructive refused).
  To execute after owner approves, build `ApprovalExecutor(store, BatchUpstream(upstream), owner_id)` in the AdminBot path (needs wiring in src/, not done).
  Limit: approval card shows only first 900 chars of args, so owner may not see all 20 actions. Needs a custom card before real use.
- `smoke_live.py`: run on Contabo against real :8765 (read-only). NOT run yet.
- `container/`: `docker build -t oisha-codemode-runner:latest -f container/Dockerfile container/`, then `CodeModeHost(..., sandbox="docker")`. NOT built/tested (no docker here).
