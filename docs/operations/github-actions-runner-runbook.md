# GitHub Actions runner diagnosis runbook

## Security boundary

- Pull-request code runs only on isolated GitHub-hosted runners.
- `[self-hosted, oracle]` is reserved for trusted `main` deployment/tests and a
  manual diagnostic dispatched from `main`.
- Diagnostic workflows do not receive repository or environment secrets.
- Never move PR jobs to Oracle to bypass GitHub-hosted runner failures.

## Current observed failure

The following pull-request CI run completed as failure before any job step was
created:

```text
run_id=30270467130
pull-request-tests: steps=None
TypeScript monorepo checks: steps=None
classification=runner_or_account_before_step_one
```

This is an account/runner-assignment infrastructure failure, not evidence that
an application test failed.

## GitHub-hosted probe interpretation

```text
queued with no assignment:
  classification=queued_waiting_for_runner

completed failure and steps=None:
  classification=runner_or_account_before_step_one
  check Settings -> Billing and licensing -> Actions usage/spending
  check account payment/restriction banners
  check repository Settings -> Actions -> General
  check GitHub Status
  open GitHub Support case with repository and run ID when settings are valid

Reach step one, later named step fails:
  classification=workflow_step_failure
  fix the named workflow/action problem

Completed success:
  classification=workflow_success
  GitHub-hosted capacity is restored
```

## Oracle probe interpretation

Run `Runner diagnostics` manually from the `main` branch after this workflow is
merged.

```text
queued indefinitely:
  runner service offline, busy, or label mismatch

step one reached:
  registration and labels are healthy

workspace_writable=false:
  fix service user/workspace ownership

disk_free_kb below 2097152:
  free at least 2 GB before trusted jobs
```

On the Oracle host, inspect only service state and non-secret metadata:

```bash
sudo systemctl status 'actions.runner*' --no-pager
sudo journalctl -u 'actions.runner*' -n 100 --no-pager
systemctl is-active oisha-os
```

Do not print `.env`, runner credentials, process environments, command-line
tokens, or configured Git remote URLs into logs.

## Acceptance criteria

- GitHub-hosted probe reaches and completes `Reach step one`.
- Python and TypeScript PR jobs complete on `ubuntu-latest`.
- Oracle manual probe completes from `main` only.
- No pull-request job targets `[self-hosted, oracle]`.
- Infrastructure failures remain separate from application test failures.
