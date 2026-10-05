# Dependency and code-scanning remediation — 2026-10-05

## Audited scope

GitHub's live API reported 33 open dependency PRs (#750–#782), 44 open
Dependabot alerts, one open CodeQL alert (#62, `py/redos`,
`scripts/test_tn6_cleaner.py`), and no open secret-scanning alerts.

This change incorporates the compatible updates from 31 PRs into consistent
manifests, overrides and regenerated lockfiles. The root, SalesCoach and
Marketing workspaces keep separate package-manager boundaries. S3 client and
request-presigner minimum versions are updated together to avoid incompatible
Smithy private types. Next is pinned to 16.3.6 in both overrides.

Python security minimums are PyJWT 2.15.0, urllib3 2.8.0 and oauthlib 4.0.0.
The production lockfile is resolved for Linux/Python 3.11, rather than Windows;
it selects PyJWT 2.15.1. Platform-only packages and incompatible transitive
versions in the previous lockfile are corrected by the resolver.

## Incompatible PRs

- #756 (`multidict==7.0.0`): uv reports no solution because aiohttp>=3.14.1
  requires multidict<7.0. The compatible lock selects 6.9.1.
- #752 (`docutils==0.23`): uv reports no solution through
  libsql-client -> sphinx-press-theme -> Sphinx. Sphinx releases usable on
  Python 3.11 require docutils<0.23. The compatible lock keeps 0.22.4.

Both constraints were reproduced with `uv pip compile requirements.txt
--python-platform linux --python-version 3.11 --constraint <pinned-version>`.
Dependabot ignores only these two exact incompatible releases; security alerts
are still enabled. Re-evaluate when aiohttp/Sphinx support those versions.

## Unreleased braces fix

GHSA-vfj7-8cjw-p6xm affects braces<=3.0.3 and has no published patched release.
Both workspaces apply `patches/braces@3.0.3.patch`, which limits parser AST
nesting before recursive compilation/expansion. The patch bounds brace and
parenthesis blocks, including imbalanced input. It does not replace the library
API or its normal expansion semantics.

`scripts/check_braces_security.cjs` fails on the original package and passes
against the installed patched packages in both workspaces. It checks a nested
attack below the existing character limit for parse/compile/expand, normal
alternatives, ranges and a wide shallow expansion. CI runs this check after
frozen installations in both workspaces. The version-based npm scanner still
reports this advisory; the local patch is a mitigation, not an upstream release.
Any GitHub dismissal must explicitly reference this patch and its CI evidence.
Remove the patch after a supported upstream fix is available.

## CodeQL ReDoS

The contact cleaner now scans non-repeated suffix tokens and verifies the final
contiguous suffix run, avoiding catastrophic backtracking. Importing the
operator script no longer reconfigures pytest's stdout. Seven characterization
cases and a bounded near-match subprocess regression pass. The original code
fails the bounded regression by timing out; assertions were preserved.

## Local verification

- Updated security packages in an isolated Python 3.11 test environment:
  **2459 passed, 17 skipped, 4 subtests passed**. The original host environment
  had intermittent 45-second subprocess shutdown timeouts under installation
  load; the full updated-environment run passed without changing test limits.
- Required `bandit -r src/ -ll`: no medium/high findings.
- Python lockfile audit: no known vulnerabilities among audited dependencies;
  the pinned VCS telegram-mcp dependency is not covered by pip-audit.
- Root workspace: typecheck, lint, test and production build passed.
  Several existing package scripts are placeholders; these are not additional
  behavioral test coverage.
- SalesCoach: type-check, build and API tests passed (2 suites, 7 tests).
- Marketing: frozen installation, production build and npm audit passed
  (zero advisories).
- Both workspaces: frozen offline installation and installed braces protection
  regression passed. Version-based audits retain the patched braces advisory.
- `git diff --check` passed.

Remote CI, merge, alert read-back and production deployment are separate gates.
Obsidian's live connector returned `Session terminated`; repository handoff
records preserve this evidence until vault logging is restored.

## Follow-up dependency queue

PR #795 merged as b3634ae04390341bca41cec8c0527c098225121c. Oracle
deploy run 37304769364 completed successfully, including health verification.
Live GitHub read-back showed zero open Dependabot, CodeQL and secret alerts.
Dependabot #241 was explicitly dismissed with the tested braces patch evidence.

Dependabot then opened a new queue (#796 onward). This follow-up refreshes
compatible Python locks for Linux/Python 3.11 and both Node workspace locks,
including paired AWS SDK 3.1146, Next 16.3.8 and Anthropic SDK 0.131.0.
It updates Ruff and mypy minimums. Frozen installation exposed overridden
manifest specifier mismatches; nodemailer and postcss overrides now match the
updated minimums.

PR #803 is incompatible: libsql-client 0.3.1 requires
sphinx-press-theme>=0.8,<0.9, so uv rejects 0.9.1. Ignore only that exact
release. Baileys 6.7.24 lacks makeInMemoryStore and fails the gateway build;
the gateway pins the previously verified 6.17.16, preserving its current API.
No gateway authentication/session was started.

Follow-up verification: 2459 Python tests passed, 17 skipped, 4 subtests;
Bandit found no medium/high issues; pip-audit found zero vulnerabilities
(excluding its unsupported pinned VCS dependency). Root typecheck, lint and
test passed; SalesCoach type-check, build and 2 API suites / 7 tests passed.
Both frozen offline installations and installed braces regressions passed.
Node version audits report only the locally patched braces advisory.
Obsidian brain_log again returned Session terminated; no vault write confirmed.

Root production build also passed after restoring the verified Baileys API.
