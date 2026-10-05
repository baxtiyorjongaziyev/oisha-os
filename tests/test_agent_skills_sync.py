from scripts.sync_agent_skills import drift


def test_agents_skills_mirror_matches_claude_skills():
    # Codex/Antigravity read .agents/skills; fix with `python scripts/sync_agent_skills.py`.
    assert drift() == []
