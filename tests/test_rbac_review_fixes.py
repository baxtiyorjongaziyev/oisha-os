from pathlib import Path


def test_oracle_deploy_injects_explicit_proxy_role_map():
    workflow = Path('.github/workflows/oracle-deploy.yml').read_text()
    assert 'OISHA_PROXY_ROLE_MAP_JSON: ${{ secrets.OISHA_PROXY_ROLE_MAP_JSON }}' in workflow
    assert 'OISHA_PROXY_ROLE_MAP_JSON=${OISHA_PROXY_ROLE_MAP_JSON}' in workflow


def test_admin_mutation_requires_mutation_grade_permission():
    source = Path('src/api/admin.py').read_text()
    marker = '@router.post("/actions/{action_type}"'
    start = source.index(marker)
    decorator = source[start: source.index('async def execute_admin_action', start)]
    assert 'Permission.SYSTEM_DEPLOY' in decorator or 'Permission.TELEGRAM_SEND' in decorator


def test_mcp_routes_do_not_require_owner_secret_in_addition_to_scoped_rbac():
    source = Path('src/api/routes/telegram_mcp.py').read_text()
    assert 'Depends(_require_internal_secret)' not in source
    assert 'require_permissions(Permission.MCP_READ)' in source
    assert 'require_permissions(Permission.MCP_WRITE)' in source


def test_crm_exposes_canonical_assignment_write_path():
    source = Path('src/api/routes/crm_dashboard.py').read_text()
    assert '/api/crm/leads/{user_id}/assignment' in source
    assert 'Permission.USERS_MANAGE_LIMITED' in source
    assert 'apply_assignment_backfill' in source
