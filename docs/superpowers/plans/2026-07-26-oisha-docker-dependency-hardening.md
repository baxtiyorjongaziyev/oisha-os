# Oisha Docker and Dependency Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Oisha containers with least privilege, remove public/default infrastructure exposure, and make Python, pnpm, and GitHub Actions dependencies reproducible and auditable.

**Architecture:** Harden the multi-stage Docker image, split development and production compose behavior, require production secrets, bind development infrastructure to loopback, and add lock/audit workflows that never execute untrusted lifecycle scripts during remediation.

**Tech Stack:** Docker, Docker Compose, Python 3.11, pip-tools, pnpm 10, GitHub Actions, pytest.

## Global Constraints

- Production application process runs as non-root.
- Production database, Redis, and MinIO ports are not publicly bound.
- Production compose contains no default passwords.
- Production images use pinned versions or digests; no `latest` tags.
- Production startup fails when required secrets are absent.
- Python production installation is locked and reproducible.
- `pnpm install --frozen-lockfile` remains authoritative.
- Dependency remediation does not run untrusted lifecycle scripts.
- Third-party security/deploy actions are pinned to immutable 40-character commit SHAs.

---

## File Structure

- Modify `Dockerfile`.
- Create `.dockerignore` or tighten the existing file.
- Modify `docker-compose.yml` for local-only development defaults.
- Create `docker-compose.production.yml`.
- Create `scripts/docker/validate_production_env.sh`.
- Create `requirements.in` and generated `requirements.lock` with hashes.
- Modify `requirements.txt` only to preserve the project’s direct dependency contract during migration.
- Modify `package.json`, `pnpm-lock.yaml`, and `.github/dependabot.yml` as audit evidence requires.
- Create `.github/workflows/dependency-audit.yml`.
- Create Docker, compose, lock, and workflow contract tests.

---

### Task 1: Establish Docker security contract tests

**Files:**
- Create: `tests/test_docker_security_contract.py`

**Interfaces:**
- Produces static tests for non-root runtime, pinned images, secret requirements, and port bindings.

- [ ] **Step 1: Write failing contract tests**

```python
from pathlib import Path
import yaml


def test_dockerfile_runs_as_non_root():
    text = Path("Dockerfile").read_text(encoding="utf-8")
    assert "USER oisha" in text
    assert "COPY --chown=oisha:oisha" in text


def test_production_compose_has_no_default_passwords_or_latest_tags():
    text = Path("docker-compose.production.yml").read_text(encoding="utf-8")
    assert "salescoach_dev" not in text
    assert ":latest" not in text


def test_development_ports_bind_loopback():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
    assert "127.0.0.1:5432:5432" in compose["services"]["postgres"]["ports"]
    assert "127.0.0.1:6379:6379" in compose["services"]["redis"]["ports"]
    assert "127.0.0.1:9000:9000" in compose["services"]["minio"]["ports"]
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_docker_security_contract.py -q`
Expected: FAIL because the current runtime is root, MinIO is `latest`, default credentials exist, and public port bindings exist.

- [ ] **Step 3: Commit the failing contract**

```bash
git add tests/test_docker_security_contract.py
git commit -m "test(docker): define Oisha container security contract"
```

---

### Task 2: Harden the application image

**Files:**
- Modify: `Dockerfile`
- Modify/Create: `.dockerignore`
- Modify: `scripts/entrypoint.sh`

**Interfaces:**
- Produces: non-root production image with healthcheck and minimal writable paths.

- [ ] **Step 1: Implement non-root runtime**

The final stage must follow this shape:

```dockerfile
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RUNNING_IN_CLOUD=True

RUN groupadd --system --gid 10001 oisha \
    && useradd --system --uid 10001 --gid oisha --home-dir /app --shell /usr/sbin/nologin oisha

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=oisha:oisha . .
RUN sed -i 's/\r$//' scripts/entrypoint.sh \
    && chmod 0555 scripts/entrypoint.sh \
    && mkdir -p /app/data /app/runtime \
    && chown -R oisha:oisha /app/data /app/runtime

USER oisha
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
ENTRYPOINT ["/bin/sh", "scripts/entrypoint.sh"]
```

- [ ] **Step 2: Tighten the build context**

`.dockerignore` must include:

```text
.git
.env
.env.*
*.session
service_account.json
node_modules
.next
coverage*
.pytest_cache
__pycache__
data
```

Do not ignore `.env.example`.

- [ ] **Step 3: Make entrypoint non-root compatible**

Remove runtime `chmod`, package install, privileged port binding, or writes outside `/app/data` and `/app/runtime`. Fail with an explicit message when required writable directories are unavailable.

- [ ] **Step 4: Build and inspect**

```bash
docker build -t oisha:test .
docker run --rm --entrypoint sh oisha:test -c 'id -u; test "$(id -u)" != 0'
docker inspect oisha:test --format '{{json .Config.Healthcheck}}'
```

Expected: UID `10001`, non-zero assertion succeeds, healthcheck exists.

- [ ] **Step 5: Run contract tests**

Run: `pytest tests/test_docker_security_contract.py -q`
Expected: non-root assertions pass; compose assertions may still fail until Task 3.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore scripts/entrypoint.sh
git commit -m "fix(docker): run Oisha as non-root"
```

---

### Task 3: Split development and production compose behavior

**Files:**
- Modify: `docker-compose.yml`
- Create: `docker-compose.production.yml`
- Create: `scripts/docker/validate_production_env.sh`
- Modify: `tests/test_docker_security_contract.py`

**Interfaces:**
- Produces: loopback-only development dependencies and secret-required production deployment.

- [ ] **Step 1: Bind development services to loopback**

```yaml
postgres:
  image: postgres:16.10-bookworm
  ports:
    - '127.0.0.1:5432:5432'
redis:
  image: redis:7.4.5-bookworm
  ports:
    - '127.0.0.1:6379:6379'
minio:
  image: minio/minio:RELEASE.2025-09-07T16-13-09Z
  ports:
    - '127.0.0.1:9000:9000'
    - '127.0.0.1:9001:9001'
```

Development credentials may remain clearly marked local-only, but production compose must not inherit them.

- [ ] **Step 2: Create production compose**

Production infrastructure services use internal networks and no `ports` keys. Required values use shell-required syntax:

```yaml
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
  MINIO_ROOT_USER: ${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}
  MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}
security_opt:
  - no-new-privileges:true
```

For the Oisha service add:

```yaml
read_only: true
tmpfs:
  - /tmp:size=64m,mode=1777
volumes:
  - oisha_data:/app/data
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

Only add a capability back if a failing runtime test proves it necessary.

- [ ] **Step 3: Add environment validator**

```bash
#!/usr/bin/env bash
set -euo pipefail
required=(POSTGRES_PASSWORD MINIO_ROOT_USER MINIO_ROOT_PASSWORD JWT_SECRET OISHA_API_SECRET)
for name in "${required[@]}"; do
  test -n "${!name:-}" || { echo "missing required secret: $name" >&2; exit 1; }
done
```

- [ ] **Step 4: Validate compose rendering**

```bash
docker compose -f docker-compose.yml config >/tmp/oisha-dev-compose.yml
POSTGRES_PASSWORD=x MINIO_ROOT_USER=x MINIO_ROOT_PASSWORD=x JWT_SECRET=$(printf 'a%.0s' {1..32}) OISHA_API_SECRET=$(printf 'b%.0s' {1..32}) \
  docker compose -f docker-compose.production.yml config >/tmp/oisha-prod-compose.yml
```

Expected: both commands succeed; production output has no public infrastructure port bindings.

- [ ] **Step 5: Verify contract tests**

Run: `pytest tests/test_docker_security_contract.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml docker-compose.production.yml scripts/docker/validate_production_env.sh tests/test_docker_security_contract.py
git commit -m "fix(docker): isolate Oisha production services"
```

---

### Task 4: Create reproducible Python dependency locks

**Files:**
- Create: `requirements.in`
- Create: `requirements-dev.in`
- Create: `requirements.lock`
- Create: `requirements-dev.lock`
- Modify: `Dockerfile`
- Create: `tests/test_python_dependency_lock.py`

**Interfaces:**
- Produces: hash-locked production and development dependency sets generated by pip-tools.

- [ ] **Step 1: Write failing lock contract tests**

```python
from pathlib import Path


def test_production_lock_contains_hashes():
    text = Path("requirements.lock").read_text(encoding="utf-8")
    assert "--hash=sha256:" in text
    assert " --index-url " not in text


def test_docker_installs_from_production_lock():
    assert "requirements.lock" in Path("Dockerfile").read_text(encoding="utf-8")
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_python_dependency_lock.py -q`
Expected: FAIL because lock files do not exist.

- [ ] **Step 3: Separate direct dependencies**

Move only direct production requirements to `requirements.in`; move direct test/lint tools to `requirements-dev.in` with:

```text
-c requirements.lock
-r requirements.in
```

- [ ] **Step 4: Generate locks**

```bash
python -m pip install 'pip-tools==7.5.1'
pip-compile --generate-hashes --resolver=backtracking --output-file=requirements.lock requirements.in
pip-compile --generate-hashes --resolver=backtracking --output-file=requirements-dev.lock requirements-dev.in
```

Review the direct VCS dependency line beginning with `telegram-mcp @` explicitly. Pin it to an immutable commit and document why hash enforcement cannot cover that line if pip-tools cannot emit a compatible hash.

- [ ] **Step 5: Install from a clean environment**

```bash
python -m venv /tmp/oisha-lock-test
/tmp/oisha-lock-test/bin/pip install --require-hashes -r requirements.lock
/tmp/oisha-lock-test/bin/pip check
```

Expected: installation and `pip check` succeed. If a VCS line prevents `--require-hashes`, split it into a separately verified immutable-install step and keep all registry packages hash-locked; record the exact exception in `docs/security/dependency-exceptions.md`.

- [ ] **Step 6: Update Docker build**

```dockerfile
COPY requirements.lock requirements.lock
RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.lock
```

- [ ] **Step 7: Verify tests and commit**

```bash
pytest tests/test_python_dependency_lock.py -q
git add requirements.in requirements-dev.in requirements.lock requirements-dev.lock Dockerfile tests/test_python_dependency_lock.py
git commit -m "build(deps): lock Python dependencies with hashes"
```

---

### Task 5: Add dependency audits without untrusted scripts

**Files:**
- Create: `.github/workflows/dependency-audit.yml`
- Modify: `.github/dependabot.yml`
- Create: `tests/test_dependency_audit_workflow.py`

**Interfaces:**
- Produces: read-only scheduled/manual audit evidence for Python and pnpm.

- [ ] **Step 1: Write failing workflow tests**

```python
from pathlib import Path
import re


def test_dependency_audit_disables_pnpm_scripts():
    text = Path(".github/workflows/dependency-audit.yml").read_text(encoding="utf-8")
    assert "pnpm install --frozen-lockfile --ignore-scripts" in text
    assert "pip-audit" in text
    assert "permissions:" in text and "contents: read" in text


def test_every_action_is_pinned_to_a_commit_sha():
    text = Path(".github/workflows/dependency-audit.yml").read_text(encoding="utf-8")
    uses_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- uses:")]
    assert uses_lines
    assert all(re.search(r"@[0-9a-f]{40}$", line) for line in uses_lines)
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_dependency_audit_workflow.py -q`
Expected: FAIL because the workflow does not exist.

- [ ] **Step 3: Implement the read-only audit workflow with exact action commits**

Use these immutable action commits, verified from their official GitHub release commit pages on 2026-07-26:

```text
actions/checkout v7.0.1       3d3c42e5aac5ba805825da76410c181273ba90b1
pnpm/action-setup v6.0.9      0ebf47130e4866e96fce0953f49152a61190b271
actions/setup-node v7.0.0     820762786026740c76f36085b0efc47a31fe5020
actions/setup-python v7.0.0   5fda3b95a4ea91299a34e894583c3862153e4b97
```

Create `.github/workflows/dependency-audit.yml`:

```yaml
name: Dependency audit
on:
  workflow_dispatch:
  schedule:
    - cron: '17 3 * * 1'
permissions:
  contents: read
jobs:
  audit:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
      - uses: pnpm/action-setup@0ebf47130e4866e96fce0953f49152a61190b271
        with:
          version: 10.33.2
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020
        with:
          node-version: '20'
          package-manager-cache: false
      - run: pnpm install --frozen-lockfile --ignore-scripts
      - run: pnpm audit --audit-level=high
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: '3.11'
      - run: python -m pip install 'pip-audit==2.10.1'
      - run: pip-audit -r requirements.lock
```

- [ ] **Step 4: Configure Dependabot grouping**

Separate security updates from routine version updates by ecosystem and cap open routine PRs. Do not ignore security advisories.

- [ ] **Step 5: Verify workflow tests**

Run: `pytest tests/test_dependency_audit_workflow.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/dependency-audit.yml .github/dependabot.yml tests/test_dependency_audit_workflow.py
git commit -m "ci(security): audit Oisha dependencies"
```

---

### Task 6: Run audits, remediate, and verify images

**Files:**
- Modify only files named by verified findings: `package.json`, `pnpm-lock.yaml`, `requirements.in`, `requirements.lock`, `requirements-dev.lock`.
- Create: `docs/security/dependency-exceptions.md` only when an exception is unavoidable.

**Interfaces:**
- Consumes audit output.
- Produces zero unresolved fixable critical/high findings or documented exceptions.

- [ ] **Step 1: Run local audits**

```bash
pnpm install --frozen-lockfile --ignore-scripts
pnpm audit --audit-level=high
python -m pip install 'pip-audit==2.10.1'
pip-audit -r requirements.lock
```

- [ ] **Step 2: Patch only verified findings**

Update direct version constraints or `pnpm.overrides`, regenerate lock files, and rerun tests after each logical dependency group. Do not use broad major upgrades without a separate compatibility review.

- [ ] **Step 3: Scan the image**

Use the repository’s approved container scanner in CI or local tooling. Record the image digest, scanner name/version, command, and findings. Do not claim clean status without captured output.

- [ ] **Step 4: Run full verification**

```bash
pytest -q --tb=short
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run lint
pnpm run test
pnpm run build
docker build -t oisha:test .
```

Expected: PASS.

- [ ] **Step 5: Commit verified remediations**

```bash
git add package.json pnpm-lock.yaml requirements.in requirements.lock requirements-dev.lock
if [ -f docs/security/dependency-exceptions.md ]; then git add docs/security/dependency-exceptions.md; fi
git commit -m "fix(security): remediate verified dependency findings"
```

- [ ] **Step 6: Open PR**

PR title: `fix(security): harden Oisha containers and dependencies`

Evidence: non-root UID, rendered compose checks, clean installs, audit before/after, full tests/build, image scan result.
