"""scripts/telethon_guard.py — prod userbot session ni AuthKeyDuplicated dan saqlaydi.

Regressiya konteksti: verify-session.yml va qurbon-greeting.yml GitHub-hosted
runner da prod USERBOT_SESSION_STRING bilan Telethon ga ulanardi. Runner IP si
Oracle VM dan boshqa bo'lgani uchun Telegram auth key ni butunlay bekor qilardi
va Juma tabrigi "used under two different IP addresses simultaneously" xatosi
bilan yiqilardi.
"""

import os

import pytest

from scripts.telethon_guard import (
    ALLOW_SHARED_ENV,
    GENERIC_DEDICATED_ENV,
    OWNER_HOST_ENV,
    SHARED_PROD_ENV,
    SessionConflictError,
    SessionMissingError,
    SessionSource,
    assert_owner_host,
    burned_session_report,
    guarded_connect,
    guarded_is_authorized,
    is_auth_key_duplicated,
    is_github_hosted_runner,
    parse_bool,
    prepare,
    resolve_session,
    single_flight,
)

HOSTED_ENV = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}
SELF_HOSTED_ENV = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"}


def _shared(origin: str = f"env:{SHARED_PROD_ENV}") -> SessionSource:
    return SessionSource(string="prod-key", origin=origin, is_shared_prod=True)


def _dedicated() -> SessionSource:
    return SessionSource(
        string="oneoff-key", origin=f"env:{GENERIC_DEDICATED_ENV}", is_shared_prod=False
    )


# --------------------------------------------------------------------------
# parse_bool / runner detection
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        (" yes ", True),
        ("on", True),
        ("\ufeff1", True),
        ("0", False),
        ("false", False),
        ("", False),
        (None, False),
    ],
)
def test_parse_bool(value, expected):
    assert parse_bool(value) is expected


def test_github_hosted_runner_detected():
    assert is_github_hosted_runner(HOSTED_ENV) is True


def test_self_hosted_runner_is_not_hosted():
    assert is_github_hosted_runner(SELF_HOSTED_ENV) is False


def test_plain_vm_shell_is_not_a_runner():
    """appleboy/ssh-action Oracle VM ga GITHUB_ACTIONS ni uzatmaydi."""
    assert is_github_hosted_runner({}) is False


def test_unknown_runner_environment_is_treated_as_hosted():
    """Fail-safe: noaniq hostda prod kalitini ochgandan ko'ra to'xtagan yaxshi."""
    assert is_github_hosted_runner({"GITHUB_ACTIONS": "true"}) is True


# --------------------------------------------------------------------------
# resolve_session
# --------------------------------------------------------------------------


def test_dedicated_env_wins_over_prod_key():
    source = resolve_session(
        dedicated_env="JUMA_SESSION_STRING",
        env={"JUMA_SESSION_STRING": "juma", SHARED_PROD_ENV: "prod"},
        shared_files=(),
    )
    assert source.string == "juma"
    assert source.is_shared_prod is False


def test_generic_dedicated_env_used_when_script_specific_missing():
    source = resolve_session(
        dedicated_env="JUMA_SESSION_STRING",
        env={GENERIC_DEDICATED_ENV: "oneoff", SHARED_PROD_ENV: "prod"},
        shared_files=(),
    )
    assert source.string == "oneoff"
    assert source.is_shared_prod is False


def test_prod_file_is_flagged_shared(tmp_path):
    path = tmp_path / "userbot_session_string.txt"
    path.write_text("  file-key  ", encoding="utf-8")
    source = resolve_session(env={}, shared_files=(str(path),))
    assert source.string == "file-key"
    assert source.is_shared_prod is True
    assert source.origin == f"file:{path}"


def test_prod_env_is_flagged_shared():
    source = resolve_session(env={SHARED_PROD_ENV: "prod"}, shared_files=())
    assert source.is_shared_prod is True
    assert source.origin == f"env:{SHARED_PROD_ENV}"


def test_blank_values_are_ignored():
    source = resolve_session(
        dedicated_env="JUMA_SESSION_STRING",
        env={"JUMA_SESSION_STRING": "   ", SHARED_PROD_ENV: "prod"},
        shared_files=(),
    )
    assert source.string == "prod"


def test_missing_session_raises():
    with pytest.raises(SessionMissingError):
        resolve_session(env={}, shared_files=())


def test_dedicated_env_equal_to_prod_key_is_flagged_shared():
    """Operator prod stringni atalgan env ga qo'yib guard'ni chetlab o'tolmaydi."""
    source = resolve_session(
        dedicated_env="JUMA_SESSION_STRING",
        env={"JUMA_SESSION_STRING": "prod", SHARED_PROD_ENV: "prod"},
        shared_files=(),
    )
    assert source.string == "prod"
    assert source.is_shared_prod is True


def test_dedicated_env_equal_to_prod_file_is_flagged_shared(tmp_path):
    path = tmp_path / "userbot_session_string.txt"
    path.write_text("prod", encoding="utf-8")
    source = resolve_session(
        env={GENERIC_DEDICATED_ENV: "prod"}, shared_files=(str(path),)
    )
    assert source.is_shared_prod is True


def test_duplicated_dedicated_env_is_blocked_on_hosted_runner():
    """Asosiy regressiya: bir xil qiymat hosted runner da ham bloklanishi kerak."""
    source = resolve_session(
        dedicated_env="JUMA_SESSION_STRING",
        env={"JUMA_SESSION_STRING": "prod", SHARED_PROD_ENV: "prod"},
        shared_files=(),
    )
    with pytest.raises(SessionConflictError):
        assert_owner_host(source, env=HOSTED_ENV)


def test_genuinely_distinct_dedicated_env_stays_unflagged():
    source = resolve_session(
        dedicated_env="JUMA_SESSION_STRING",
        env={"JUMA_SESSION_STRING": "juma", SHARED_PROD_ENV: "prod"},
        shared_files=(),
    )
    assert source.is_shared_prod is False
    assert_owner_host(source, env=HOSTED_ENV)


# --------------------------------------------------------------------------
# assert_owner_host — asosiy regressiya
# --------------------------------------------------------------------------


def test_prod_key_on_github_hosted_runner_is_blocked():
    with pytest.raises(SessionConflictError) as exc:
        assert_owner_host(_shared(), env=HOSTED_ENV)
    assert "AuthKeyDuplicated" in str(exc.value)


def test_prod_key_on_self_hosted_oracle_runner_is_allowed():
    assert_owner_host(_shared(), env=SELF_HOSTED_ENV)


def test_prod_key_on_vm_shell_is_allowed():
    assert_owner_host(_shared(), env={})


def test_dedicated_key_is_allowed_even_on_hosted_runner():
    """Atalgan session prod kaliti bilan raqobatlashmaydi — cheklov yo'q."""
    assert_owner_host(_dedicated(), env=HOSTED_ENV)


def test_escape_hatch_allows_prod_key_on_hosted_runner():
    assert_owner_host(_shared(), env={**HOSTED_ENV, ALLOW_SHARED_ENV: "1"})


def test_owner_host_mismatch_is_blocked():
    with pytest.raises(SessionConflictError) as exc:
        assert_owner_host(
            _shared(), env={OWNER_HOST_ENV: "oisha-oracle"}, hostname="some-laptop"
        )
    assert "oisha-oracle" in str(exc.value)


def test_owner_host_match_is_allowed():
    assert_owner_host(
        _shared(), env={OWNER_HOST_ENV: "oisha-oracle"}, hostname="OISHA-ORACLE"
    )


def test_prepare_blocks_prod_key_on_hosted_runner(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(GENERIC_DEDICATED_ENV, raising=False)
    monkeypatch.delenv(ALLOW_SHARED_ENV, raising=False)
    monkeypatch.setenv(SHARED_PROD_ENV, "prod")
    for key, value in HOSTED_ENV.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(SessionConflictError):
        prepare("JUMA_SESSION_STRING")


def test_prepare_returns_dedicated_session_on_hosted_runner(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JUMA_SESSION_STRING", "juma")
    monkeypatch.setenv(SHARED_PROD_ENV, "prod")
    for key, value in HOSTED_ENV.items():
        monkeypatch.setenv(key, value)

    source = prepare("JUMA_SESSION_STRING")
    assert source.string == "juma"
    assert source.is_shared_prod is False


# --------------------------------------------------------------------------
# AuthKeyDuplicated aniqlash
# --------------------------------------------------------------------------


class _AuthKeyDuplicatedError(Exception):
    """Telethon xatosining o'rnini bosuvchi (real import kerak emas)."""


def test_detects_auth_key_duplicated_by_type_name():
    assert is_auth_key_duplicated(_AuthKeyDuplicatedError("boom")) is True


def test_detects_auth_key_duplicated_by_message():
    exc = RuntimeError(
        "The authorization key (session file) was used under two different IP "
        "addresses simultaneously, and can no longer be used."
    )
    assert is_auth_key_duplicated(exc) is True


def test_ordinary_errors_are_not_auth_key_duplicated():
    assert is_auth_key_duplicated(ConnectionError("network down")) is False


def test_burned_session_report_has_recovery_steps():
    report = burned_session_report(_shared(), _AuthKeyDuplicatedError("boom"))
    assert "systemctl stop oisha-os" in report
    assert GENERIC_DEDICATED_ENV in report
    assert f"env:{SHARED_PROD_ENV}" in report


# --------------------------------------------------------------------------
# guarded_connect
# --------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, error=None, authorized=True, authorize_error=None):
        self.error = error
        self.connected = False
        self._authorized = authorized
        self.authorize_error = authorize_error

    async def connect(self):
        if self.error:
            raise self.error
        self.connected = True

    async def is_user_authorized(self):
        if self.authorize_error:
            raise self.authorize_error
        return self._authorized


async def test_guarded_connect_passes_through_on_success():
    client = _FakeClient()
    await guarded_connect(client, _shared())
    assert client.connected is True


async def test_guarded_connect_translates_burned_key():
    client = _FakeClient(_AuthKeyDuplicatedError("two different IP addresses"))
    with pytest.raises(SessionConflictError) as exc:
        await guarded_connect(client, _shared())
    assert "SESSION KUYDI" in str(exc.value)


async def test_guarded_connect_reraises_other_errors():
    client = _FakeClient(ConnectionError("network down"))
    with pytest.raises(ConnectionError):
        await guarded_connect(client, _shared())


async def test_guarded_is_authorized_returns_state():
    assert await guarded_is_authorized(_FakeClient(authorized=True), _shared()) is True
    assert await guarded_is_authorized(_FakeClient(authorized=False), _shared()) is False


async def test_guarded_is_authorized_translates_burned_key():
    """Telethon transportda ulanib, kalit kuyganini birinchi RPC da bildiradi."""
    client = _FakeClient(authorize_error=_AuthKeyDuplicatedError("boom"))
    with pytest.raises(SessionConflictError) as exc:
        await guarded_is_authorized(client, _shared())
    assert "SESSION KUYDI" in str(exc.value)


async def test_guarded_is_authorized_reraises_other_errors():
    client = _FakeClient(authorize_error=TimeoutError("slow"))
    with pytest.raises(TimeoutError):
        await guarded_is_authorized(client, _shared())


# --------------------------------------------------------------------------
# single_flight
# --------------------------------------------------------------------------


def test_single_flight_blocks_a_second_holder(tmp_path):
    lock_dir = str(tmp_path / "locks")
    with single_flight("userbot_oneoff", lock_dir=lock_dir):
        with pytest.raises(SessionConflictError):
            with single_flight("userbot_oneoff", lock_dir=lock_dir):
                pytest.fail("ikkinchi skript lockni olmasligi kerak edi")


def test_single_flight_releases_after_exit(tmp_path):
    lock_dir = str(tmp_path / "locks")
    with single_flight("userbot_oneoff", lock_dir=lock_dir):
        pass
    with single_flight("userbot_oneoff", lock_dir=lock_dir):
        pass


def test_single_flight_separates_names(tmp_path):
    lock_dir = str(tmp_path / "locks")
    with single_flight("juma", lock_dir=lock_dir):
        with single_flight("qurbon", lock_dir=lock_dir):
            assert os.path.exists(os.path.join(lock_dir, "qurbon.lock"))
