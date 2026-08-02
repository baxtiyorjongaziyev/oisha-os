```markdown
# oisha-os Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill covers the core development conventions and workflows for the `oisha-os` Python codebase. It outlines best practices for file organization, code style, and deployment update workflows, enabling contributors to maintain consistency and efficiency across the project.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for all Python files.
  ```
  # Good
  aiogram_cloudrun.py
  boot.py

  # Bad
  AiogramCloudRun.py
  aiogramCloudRun.py
  ```

- **Import Style:**  
  Prefer **relative imports** within the package.
  ```python
  # Good
  from .services.core.telegram import aiogram_webhook_head

  # Bad
  import src.services.core.telegram.aiogram_webhook_head
  ```

- **Export Style:**  
  Use **named exports** (explicitly define what is exported).
  ```python
  # In src/aiogram_cloudrun.py
  def deploy():
      pass

  __all__ = ['deploy']
  ```

- **Commit Messages:**  
  Use prefixes like `feat` and `fix`. Keep messages concise (~53 characters).
  ```
  feat: add cloud run deployment script
  fix: correct webhook head import path
  ```

## Workflows

### Deploy Configuration Update
**Trigger:** When you need to change how a service is deployed or split deployment responsibilities (e.g., splitting a service head, making cutovers fail-safe).  
**Command:** `/update-deploy-config`

1. **Edit deployment workflow YAML**  
   Update the relevant workflow file in `.github/workflows/`, such as:
   ```
   .github/workflows/oracle-deploy.yml
   ```

2. **Update deployment documentation**  
   Revise or add documentation in `deploy/*.md`:
   ```
   deploy/AIOGRAM_CLOUD_RUN.md
   ```

3. **Modify or add deployment scripts**  
   Update scripts in `deploy/` and `scripts/`:
   ```
   deploy/deploy_cloud_run.py
   scripts/deploy_aiogram_cloudrun.ps1
   ```

4. **Update or add Dockerfiles and cloud build configs**  
   Edit files such as:
   ```
   deploy/cloud-run-aiogram.Dockerfile
   deploy/cloudbuild-aiogram.yaml
   ```

5. **Update service entrypoints or settings**  
   Change relevant files in `src/`:
   ```
   src/aiogram_cloudrun.py
   src/boot.py
   src/services/core/telegram/aiogram_webhook_head.py
   src/settings.py
   ```

6. **Add or update related tests**  
   Ensure tests in `tests/` are updated or created:
   ```
   tests/test_aiogram_cloudrun.py
   tests/test_aiogram_webhook_head.py
   tests/test_oracle_only_runtime.py
   ```

**Example:**
```bash
# To update deployment config for a new webhook head
# 1. Edit .github/workflows/oracle-deploy.yml
# 2. Update deploy/AIOGRAM_CLOUD_RUN.md
# 3. Modify deploy/deploy_cloud_run.py
# 4. Update src/services/core/telegram/aiogram_webhook_head.py
# 5. Add/modify tests/test_aiogram_webhook_head.py
```

## Testing Patterns

- **Framework:** Unknown (not detected)
- **File Pattern:** Test files are named with the pattern `*.test.ts` (suggests some TypeScript tests may exist, but Python test files like `test_*.py` are also present).
- **Location:** All tests are placed in the `tests/` directory.
- **Example:**
  ```python
  # tests/test_aiogram_cloudrun.py
  import unittest
  from src.aiogram_cloudrun import deploy

  class TestDeploy(unittest.TestCase):
      def test_deploy_runs(self):
          self.assertIsNone(deploy())
  ```

## Commands

| Command               | Purpose                                                         |
|-----------------------|-----------------------------------------------------------------|
| /update-deploy-config | Update deployment configuration, scripts, and documentation.     |
```
