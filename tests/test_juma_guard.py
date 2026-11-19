"""Tests for Juma anti-spam guard, TN7 targeting, and PCG username exclusion."""

from __future__ import annotations

import importlib
import json
import random
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.juma_guard import (
    JUMA_TEMPLATES,
    TASHKENT_TZ,
    JumaRateConfig,
    classify_and_order_recipients,
    compute_juma_deadline,
    estimate_duration_minutes,
    is_excluded_juma_recipient,
    is_excluded_member,
    is_juma_send_window,
    is_quiet_hours,
    is_silent_send_time,
    load_custom_greetings,
    load_juma_rate_config,
    next_delay_seconds,
    pick_greeting_text,
    seconds_until_quiet_ends,
    select_target_groups,
)


@pytest.mark.parametrize(
    "username,expected",
    [
        ("pcg", True),
        ("@PCG_admin", True),
        ("sherbek_pcg", True),
        ("myPcgUser", True),
        ("baxtiyorjon", False),
        ("", False),
        (None, False),
    ],
)
def test_is_excluded_juma_recipient_pcg_usernames(username, expected):
    blocked, reason = is_excluded_juma_recipient(username)
    assert blocked is expected
    if expected:
        assert reason == "username:pcg"
    else:
        assert reason == ""


def test_is_excluded_juma_recipient_custom_tokens_and_names():
    cfg = load_juma_rate_config({"JUMA_EXCLUDED_USERNAME_TOKENS": " @PCG , vip_staff "})
    assert cfg.blocked_username_tokens == ("pcg", "vip_staff")
    assert is_excluded_juma_recipient(
        "ali_vip_staff", blocked_username_tokens=cfg.blocked_username_tokens
    ) == (True, "username:vip_staff")
    assert is_excluded_juma_recipient(
        "normal_user", full_name="Hasanboy Admin", excluded_names=["Admin"]
    ) == (True, "name:Admin")


@pytest.mark.parametrize(
    "member,expected_prefix",
    [
        ({"id": 1, "username": "amaan_uz", "name": "Zokir"}, "brand_username:amaan"),
        ({"id": 2, "username": "zokir_u", "name": "Zokir Umedov Patent Amaan"}, "brand_name:amaan"),
        ({"id": 3, "username": "zokir_u", "name": "Амаан Патент"}, "brand_name:amaan"),
        ({"id": 4, "username": "@Asxab_sotuv", "name": "Samandar"}, "brand_username:asxab"),
        ({"id": 5, "username": "samandar_d", "name": "Samandar ASXAB"}, "brand_name:asxab"),
        ({"id": 6, "username": "alisher_d", "name": "Асхаб Дизайн"}, "brand_name:asxab"),
        ({"id": 5190113669, "username": "alisher_tn7", "name": "Алишер Тешаев TN7"}, "user_id:5190113669"),
        ({"id": 7, "username": "noor_marketing", "name": "Nurmuhammad"}, "brand_username:noormarketing"),
        ({"id": 8, "username": "@noormarketing", "name": "Nurmuhammad"}, "brand_username:noormarketing"),
        ({"id": 9, "username": "nurmuhammad_a", "name": "Ноор Маркетинг"}, "brand_name:noormarketing"),
        ({"id": 10, "username": "nurmuhammad_a", "name": "Nurmuhammad", "company": "NOOR marketing agentligi"}, "brand_meta:noormarketing"),
        ({"id": 11, "username": "@nurmuhammadabdulaziz", "name": "Nurmuhammad"}, "exact_username:nurmuhammadabdulaziz"),
        ({"id": 12, "username": "metasell_uz", "name": "Rano"}, "brand_username:metasell"),
        ({"id": 13, "username": "rano_m", "name": "Метаселл Агентство"}, "brand_name:metasell"),
        ({"id": 8691281355, "username": "rano_tn7", "name": "Rano TN7 Gr"}, "user_id:8691281355"),
        ({"id": 14, "username": "@bifoza_assistance", "name": "Lochinbek"}, "brand_username:bifoza"),
        ({"id": 15, "username": "lochin_b", "name": "Lochinbek Bifoza"}, "brand_name:bifoza"),
        ({"id": 16, "username": "sarvar_erp", "name": "Бифоза"}, "brand_name:bifoza"),
        ({"id": 17, "username": "@rahimov_erpflow", "name": "Jamshid"}, "exact_username:rahimov_erpflow"),
        ({"id": 18, "username": "sarvarbeksaibov", "name": "Sarvar"}, "exact_username:sarvarbeksaibov"),
        ({"id": 19, "username": "@patent_lab", "name": "Ali"}, "brand_username:patentlab"),
        ({"id": 20, "username": "ali_p", "name": "Patent Lab"}, "brand_name:patentlab"),
        ({"id": 21, "username": "ali_p", "name": "PatentLab"}, "brand_name:patentlab"),
        ({"id": 22, "username": "ali_p", "name": "Патент Лаб"}, "brand_name:patentlab"),
    ],
)
def test_competitor_brands_and_accounts_excluded(member, expected_prefix):
    cfg = load_juma_rate_config({})
    blocked, reason = is_excluded_member(member, cfg)
    assert blocked is True
    assert reason == expected_prefix


@pytest.mark.parametrize(
    "member",
    [
        {"id": 901, "username": "noor_ali", "name": "Nooruliyman"},
        {"id": 902, "username": "ali_biz", "name": "- PCG TN4 Gr"},
        {"id": 903, "username": "kamol_mebel", "name": "Kamoliddin Mebel TN7"},
    ],
)
def test_non_competitor_members_not_false_positived(member):
    cfg = load_juma_rate_config({})
    blocked, reason = is_excluded_member(member, cfg)
    assert blocked is False
    assert reason == ""


def test_classify_and_order_recipients():
    members = [{"id": i, "warm": False, "mutual": False} for i in range(1, 61)]
    members.append({"id": 100, "warm": True, "mutual": False})
    members.append({"id": 101, "warm": False, "mutual": True})

    selected, deferred = classify_and_order_recipients(members, cold_limit=50)
    assert [m["id"] for m in selected[:2]] == [100, 101]
    assert len(selected) == 52
    assert len(deferred) == 10
    assert deferred[0]["id"] == 51

    only_warm, all_cold_deferred = classify_and_order_recipients(members, cold_limit=0)
    assert [m["id"] for m in only_warm] == [100, 101]
    assert len(all_cold_deferred) == 60

    all_selected, none_deferred = classify_and_order_recipients(members, cold_limit=None)
    assert len(all_selected) == 62
    assert none_deferred == []


@pytest.mark.parametrize(
    "hour,minute,expected_quiet,expected_sec",
    [
        (22, 29, False, 0.0),
        (22, 30, True, 7 * 3600 + 30 * 60),
        (3, 0, True, 3 * 3600),
        (5, 59, True, 60.0),
        (6, 0, False, 0.0),
    ],
)
def test_quiet_hours_and_seconds_until_end(hour, minute, expected_quiet, expected_sec):
    cfg = JumaRateConfig()
    now = datetime(2026, 11, 19, hour, minute, tzinfo=TASHKENT_TZ)
    assert is_quiet_hours(now, cfg) is expected_quiet
    assert seconds_until_quiet_ends(now, cfg) == pytest.approx(expected_sec)


@pytest.mark.parametrize(
    "hour,minute,expected_silent",
    [
        (5, 59, False),
        (6, 0, True),
        (7, 59, True),
        (8, 0, False),
        (14, 0, False),
    ],
)
def test_is_silent_send_time(hour, minute, expected_silent):
    cfg = JumaRateConfig()
    now = datetime(2026, 11, 20, hour, minute, tzinfo=TASHKENT_TZ)
    assert is_silent_send_time(now, cfg) is expected_silent


async def test_send_to_member_passes_silent_flag(monkeypatch):
    mod_greetings = importlib.import_module("scripts.send_juma_greetings")
    monkeypatch.setattr(mod_greetings.asyncio, "sleep", AsyncMock())

    class _DummyAction:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return False

    client = SimpleNamespace(
        action=lambda *args, **kwargs: _DummyAction(),
        send_message=AsyncMock(),
    )
    cfg = JumaRateConfig(typing_min_sec=0.0, typing_max_sec=0.0)
    await mod_greetings.send_to_member(client, {"id": 42}, "Salom", cfg, silent=True)
    await mod_greetings.send_to_member(client, {"id": 43}, "Salom", cfg, silent=False)
    assert client.send_message.await_args_list[0].kwargs["silent"] is True
    assert client.send_message.await_args_list[1].kwargs["silent"] is False


def test_juma_send_window_and_deadline():
    cfg = JumaRateConfig(shom_hour=17, shom_minute=0)
    thu_before = datetime(2026, 11, 19, 16, 59, tzinfo=TASHKENT_TZ)
    thu_at = datetime(2026, 11, 19, 17, 0, tzinfo=TASHKENT_TZ)
    fri_morning = datetime(2026, 11, 20, 8, 0, tzinfo=TASHKENT_TZ)
    fri_shom = datetime(2026, 11, 20, 17, 0, tzinfo=TASHKENT_TZ)
    sat = datetime(2026, 11, 21, 10, 0, tzinfo=TASHKENT_TZ)

    assert is_juma_send_window(thu_before, cfg) is False
    assert is_juma_send_window(thu_at, cfg) is True
    assert is_juma_send_window(fri_morning, cfg) is True
    assert is_juma_send_window(fri_shom, cfg) is False
    assert is_juma_send_window(sat, cfg) is False

    expected_deadline = datetime(2026, 11, 20, 17, 0, tzinfo=TASHKENT_TZ)
    assert compute_juma_deadline(thu_at, cfg) == expected_deadline
    assert compute_juma_deadline(fri_morning, cfg) == expected_deadline


def test_next_delay_seconds_and_estimate():
    cfg = JumaRateConfig()
    rng = random.Random(42)

    d1, is_b1 = next_delay_seconds(1, cfg, rng=rng)
    assert is_b1 is False
    assert 90.0 <= d1 <= 180.0

    d15, is_b15 = next_delay_seconds(15, cfg, rng=rng)
    d30, is_b30 = next_delay_seconds(30, cfg, rng=rng)
    assert is_b15 is True and 900.0 <= d15 <= 1200.0
    assert is_b30 is True and 900.0 <= d30 <= 1200.0

    assert estimate_duration_minutes(0, cfg) == 0.0
    est_50 = estimate_duration_minutes(50, cfg)
    assert est_50 > 120.0


def test_load_custom_greetings_and_pick(tmp_path):
    dict_path = tmp_path / "dict.json"
    dict_path.write_text(
        json.dumps({"101": "Salom 101", "@Ali_Biz": "Salom Ali", "999": "   "}),
        encoding="utf-8",
    )
    loaded = load_custom_greetings(dict_path)
    assert pick_greeting_text({"id": 101, "username": "x"}, loaded, JUMA_TEMPLATES) == "Salom 101"
    assert pick_greeting_text({"id": 202, "username": "ali_biz"}, loaded, JUMA_TEMPLATES) == "Salom Ali"
    fallback = pick_greeting_text({"id": 999, "username": "unknown"}, loaded, JUMA_TEMPLATES, rng=random.Random(1))
    assert fallback in JUMA_TEMPLATES

    list_path = tmp_path / "list.json"
    list_path.write_text(
        json.dumps([{"id": 55, "username": "@Zafar", "message": "Maxsus tabrik"}, {"id": 56, "text": ""}]),
        encoding="utf-8",
    )
    loaded_list = load_custom_greetings(list_path)
    assert pick_greeting_text({"id": 55}, loaded_list, JUMA_TEMPLATES) == "Maxsus tabrik"
    assert pick_greeting_text({"id": 77, "username": "zafar"}, loaded_list, JUMA_TEMPLATES) == "Maxsus tabrik"


def test_select_target_groups():
    tn7 = select_target_groups("TN7")
    assert len(tn7) == 1
    assert tn7[0]["id"] == -1003926176795

    both = select_target_groups("TN7,TN6")
    assert [g["code"] for g in both] == ["TN7", "TN6"]

    all_groups = select_target_groups("all")
    assert len(all_groups) == 6
    assert all_groups[0]["code"] == "TN7"


def test_scripts_import_cleanly_without_api_env_or_day_exit(monkeypatch):
    monkeypatch.delenv("API_ID", raising=False)
    monkeypatch.delenv("API_HASH", raising=False)
    mod_greetings = importlib.import_module("scripts.send_juma_greetings")
    mod_oneoff = importlib.import_module("scripts.send_juma_oneoff")
    assert hasattr(mod_greetings, "run")
    assert hasattr(mod_oneoff, "run")


async def test_juma_scripts_safety_guards():
    mod_greetings = importlib.import_module("scripts.send_juma_greetings")
    mod_oneoff = importlib.import_module("scripts.send_juma_oneoff")

    bad_args = SimpleNamespace(ignore_day_check=True, dry_run=False, cold_limit=None)
    with pytest.raises(ValueError, match="dry-run"):
        await mod_greetings.run(bad_args)

    for blocked_user in ("@Sherbek_PCG", "@Asxab_sotuv", "@patentlab", "@nurmuhammadabdulaziz"):
        oneoff_blocked = SimpleNamespace(
            test_user=blocked_user, broadcast=False, cold_limit=None, messages_json=""
        )
        with pytest.raises(ValueError, match="bloklangan"):
            await mod_oneoff.run(oneoff_blocked)


class _FakeCursor:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def fetchall(self):
        return self._rows

    async def fetchone(self):
        return self._one


class _FakeConn:
    def __init__(self, db_rows):
        self.db_rows = db_rows
        self.sent_inserts = []
        self.committed = 0

    def execute(self, query, params=()):
        if "FROM users" in query:
            return _FakeCursor(rows=self.db_rows)
        if "SELECT 1 FROM juma_sent_logs" in query:
            return _FakeCursor(one=None)
        if "INSERT INTO juma_sent_logs" in query:
            self.sent_inserts.append(params)
        return _FakeCursor()

    async def commit(self):
        self.committed += 1


class _FakeDb:
    def __init__(self, conn):
        self._conn = conn
        self.marked = []

    async def get_connection(self):
        return self._conn

    async def mark_job_run(self, job, date_str):
        self.marked.append((job, date_str))


async def test_juma_notifier_excludes_pcg_and_competitors(monkeypatch):
    from src.services.core import juma_notifier as jn_mod

    conn = _FakeConn(
        db_rows=[
            (1, "Ali TN7", "pcg_curator"),
            (2, "Vali TN7", "vali_biz"),
            (3, "Lochinbek Bifoza", "lochin_uz"),
            (4, "Jamshid TN7", "rahimov_erpflow"),
            (5190113669, "Alisher Teshayev", "alisher_tn7"),
        ]
    )
    db = _FakeDb(conn)
    client = AsyncMock()
    tn7_participants = [
        SimpleNamespace(id=5, first_name="Alisher", last_name="TN7", username="Alisher_PCG", bot=False, is_self=False),
        SimpleNamespace(id=6, first_name="Samandar", last_name="ASXAB", username="samandar_d", bot=False, is_self=False),
        SimpleNamespace(id=8691281355, first_name="Rano", last_name="TN7", username="rano_tn7", bot=False, is_self=False),
        SimpleNamespace(id=7, first_name="Kamol", last_name="TN7", username="kamol_uz", bot=False, is_self=False),
    ]

    async def fake_get_participants(g_id, limit=200):
        return tn7_participants if g_id == -1003926176795 else []

    client.get_participants.side_effect = fake_get_participants
    notifier = jn_mod.JumaNotifier(client=client, db=db)

    classmates = await notifier.get_tn5_classmates()
    assert [c["id"] for c in classmates] == [2, 7]
    assert client.get_participants.call_args_list[0].args[0] == -1003926176795

    monkeypatch.setattr(jn_mod, "automatic_customer_send_allowed", lambda kind: True)
    monkeypatch.setattr(jn_mod.asyncio, "sleep", AsyncMock())
    notifier.get_tn5_classmates = AsyncMock(
        return_value=[
            {"id": 10, "name": "PCG User", "username": "pcg_team"},
            {"id": 11, "name": "Patent Lab", "username": "ali_p"},
            {"id": 12, "name": "Nurmuhammad", "username": "nurmuhammadabdulaziz"},
            {"id": 8691281355, "name": "Rano", "username": "rano_tn7"},
            {"id": 13, "name": "Real User", "username": "real_biz"},
        ]
    )
    await notifier.send_greetings("2026-11-20")
    assert client.send_message.await_count == 1
    assert client.send_message.await_args.args[0] == 13


def test_upsert_juma_env_writes_outside_repo_and_preserves_other_keys(tmp_path):
    mod = importlib.import_module("scripts.juma_session_login")
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    env_file = tmp_path / "etc_oisha" / "juma.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("OTHER_KEY=keep_me\nJUMA_SESSION_STRING=old_val\n", encoding="utf-8")

    mod.upsert_juma_env(env_file, "fresh_juma_session", repo_root=fake_repo)
    content = env_file.read_text(encoding="utf-8").splitlines()
    assert "OTHER_KEY=keep_me" in content
    assert "JUMA_SESSION_STRING=fresh_juma_session" in content
    assert "JUMA_SESSION_STRING=old_val" not in content


def test_upsert_juma_env_refuses_path_inside_repo(tmp_path):
    mod = importlib.import_module("scripts.juma_session_login")
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    with pytest.raises(ValueError, match="repo"):
        mod.upsert_juma_env(fake_repo / ".env", "fresh_juma_session", repo_root=fake_repo)
    with pytest.raises(ValueError):
        mod.upsert_juma_env(tmp_path / "outside.env", "   ", repo_root=fake_repo)


def test_assert_not_prod_session_rejects_prod_key_and_allows_distinct(tmp_path):
    mod = importlib.import_module("scripts.juma_session_login")
    prod_file = tmp_path / "userbot_session_string.txt"
    prod_file.write_text("prod_file_secret\n", encoding="utf-8")

    with pytest.raises(ValueError, match="alohida"):
        mod.assert_not_prod_session(
            "prod_env_secret",
            env={"USERBOT_SESSION_STRING": "prod_env_secret"},
            shared_files=(str(prod_file),),
        )
    with pytest.raises(ValueError, match="alohida"):
        mod.assert_not_prod_session(
            "prod_file_secret",
            env={},
            shared_files=(str(prod_file),),
        )
    mod.assert_not_prod_session(
        "dedicated_juma_secret",
        env={"USERBOT_SESSION_STRING": "prod_env_secret"},
        shared_files=(str(prod_file),),
    )
