---
name: deploy-configuration-update
description: Workflow command scaffold for deploy-configuration-update in oisha-os.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /deploy-configuration-update

Use this workflow when working on **deploy-configuration-update** in `oisha-os`.

## Goal

Update deployment configuration, scripts, and documentation for a new or modified service (e.g., splitting a service head, making cutovers fail-safe).

## Common Files

- `.github/workflows/oracle-deploy.yml`
- `deploy/AIOGRAM_CLOUD_RUN.md`
- `deploy/cloud-run-aiogram.Dockerfile`
- `deploy/cloudbuild-aiogram.yaml`
- `deploy/deploy_cloud_run.py`
- `scripts/deploy_aiogram_cloudrun.ps1`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit deployment workflow YAML in .github/workflows/
- Update deployment documentation in deploy/*.md
- Modify or add deployment scripts in deploy/ and scripts/
- Update or add Dockerfiles and cloud build configs in deploy/
- Update service entrypoints or settings in src/

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.