from src.settings import AppSettings, normalize_telegram_chat_id


def test_normalize_telegram_chat_id_converts_raw_supergroup_id():
    assert normalize_telegram_chat_id(-4860594772) == -1004860594772


def test_normalize_telegram_chat_id_preserves_canonical_and_small_group_ids():
    assert normalize_telegram_chat_id(-1002566480563) == -1002566480563
    assert normalize_telegram_chat_id(-12345) == -12345


def test_tasks_group_id_is_normalized_for_topic_delivery():
    settings = AppSettings(TASKS_GROUP_ID=-4860594772)

    assert settings.TASKS_GROUP_ID == -1004860594772
