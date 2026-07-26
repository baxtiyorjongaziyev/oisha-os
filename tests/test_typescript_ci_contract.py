from pathlib import Path


def test_typescript_monorepo_has_a_separate_ci_job():
    workflow = Path('.github/workflows/test.yml').read_text(encoding='utf-8')

    assert 'typescript-monorepo:' in workflow
    assert 'pnpm/action-setup@v5' in workflow
    assert 'pnpm install --frozen-lockfile' in workflow
    assert 'pnpm run typecheck' in workflow
    assert 'pnpm run lint' in workflow
    assert 'pnpm run test' in workflow
    assert 'pnpm run build' in workflow
