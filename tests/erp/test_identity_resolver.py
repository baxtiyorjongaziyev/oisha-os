from src.services.erp.identity_resolver import (
    CLIENT_ACTION_THRESHOLD,
    IdentityProfile,
    resolve_identity,
)


def test_exact_phone_is_verified_identity_evidence():
    resolution = resolve_identity(
        IdentityProfile(phone="+998 90 123 45 67", name="Farrux aka"),
        IdentityProfile(phone="998901234567", name="Farrux"),
    )

    assert resolution.verified is True
    assert resolution.confidence == 1.0
    assert resolution.strongest_evidence == "phone_exact"


def test_exact_telegram_user_id_is_verified_even_when_names_differ():
    resolution = resolve_identity(
        IdentityProfile(telegram_user_id=777, name="Farrux"),
        IdentityProfile(telegram_user_id=777, name="Farruxjon"),
    )

    assert resolution.verified is True
    assert resolution.confidence == 1.0
    assert resolution.strongest_evidence == "telegram_user_id_exact"


def test_conflicting_strong_identity_blocks_match():
    resolution = resolve_identity(
        IdentityProfile(phone="+998901111111", telegram_user_id=777),
        IdentityProfile(phone="+998902222222", telegram_user_id=888),
    )

    assert resolution.verified is False
    assert resolution.confidence == 0.0
    assert "phone_conflict" in resolution.reasons
    assert "telegram_user_id_conflict" in resolution.reasons


def test_name_only_is_below_client_action_threshold():
    resolution = resolve_identity(
        IdentityProfile(name="Saidazimxoja aka"),
        IdentityProfile(name="Saidazimxoja"),
    )

    assert resolution.verified is False
    assert resolution.confidence < CLIENT_ACTION_THRESHOLD
    assert resolution.strongest_evidence == "name_only"


def test_honorific_only_is_zero_identity_evidence():
    resolution = resolve_identity(
        IdentityProfile(name="aka"),
        IdentityProfile(name="Aka"),
    )

    assert resolution.verified is False
    assert resolution.confidence == 0.0
    assert resolution.strongest_evidence == "none"
