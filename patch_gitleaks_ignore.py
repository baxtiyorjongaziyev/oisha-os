import re

with open(".gitleaks.toml", "r") as f:
    content = f.read()

# Make sure we ignore the .next folder to prevent Next.js caches from being scanned and breaking CI
ignore_rule = """
[allowlist]
description = "Non-secret identifiers and pre-existing historical commits"
paths = [
  '''apps/web/\\.next/.*''',
]
"""
# just patch .gitleaks.toml to have this if paths is not there
if "paths = [" not in content:
    content = content.replace('[allowlist]\ndescription = "Non-secret identifiers and pre-existing historical commits"', ignore_rule.strip())
    with open(".gitleaks.toml", "w") as f:
        f.write(content)
