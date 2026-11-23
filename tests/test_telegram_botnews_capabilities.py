import pytest

from src.services.api_server.webhooks import process_telegram_ai_update
from src.services.core.telegram.telegram_ai_features import (
    TelegramBotAPI10Client,
    bootstrap_owner_private_topics,
    build_date_time_entity,
    build_ephemeral_parameters,
    build_input_checklist,
    build_styled_inline_button,
    enrich_lead_from_personal_channel,
    extract_checklist_tasks_done,
    extract_stopped_message_generation,
    get_owner_topic_id,
    rich_button_row,
    rich_table,
    send_client_native_checklist,
    send_oisha_kpi_report,
    sync_team_member_tags,
)
from src.services.core.telegram.widgets.runtime import build_widget_router


@pytest.mark.asyncio
async def test_bootstrap_owner_private_topics_enables_sidebar_and_creates_5_topics():
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        if method == "setMySettings":
            return {"ok": True, "result": True}
        if method == "createForumTopic":
            return {
                "ok": True,
                "result": {
                    "message_thread_id": len(calls) * 10,
                    "name": payload["name"],
                    "icon_color": payload["icon_color"],
                },
            }
        return {"ok": True, "result": True}

    client = TelegramBotAPI10Client("token", transport=transport)
    res = await bootstrap_owner_private_topics(
        client,
        owner_chat_id=999,
        bot_username="@jonairobot",
    )

    assert calls[0][0] == "setMySettings"
    assert calls[0][1]["has_topics_enabled"] is True
    assert calls[0][1]["has_topic_sidebar"] is True
    assert calls[0][1]["callback_query_mode"] == "auto"

    topics = res["topics"]
    assert set(topics.keys()) == {"finance", "sales", "marketing", "hr", "system"}
    assert topics["finance"]["deep_link"] == "https://t.me/jonairobot/20"

    with pytest.raises(ValueError, match="Unsupported icon_color"):
        await client.create_forum_topic(999, "Notoʻgʻri rang", icon_color=123)


@pytest.mark.asyncio
async def test_native_checklist_send_edit_and_webhook_extraction():
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 404}}

    client = TelegramBotAPI10Client("token", transport=transport)
    sent = await send_client_native_checklist(
        client,
        business_connection_id="biz-1",
        chat_id=555,
        client_name="AgroBank",
        items=[
            {"id": 1, "label": "Brif toʻldirish"},
            {"id": 2, "label": "Shartnoma va hisob"},
        ],
    )

    assert sent == {"message_id": 404}
    assert calls[0][0] == "sendChecklist"
    assert calls[0][1]["business_connection_id"] == "biz-1"
    assert calls[0][1]["checklist"]["title"] == "AgroBank — Loyiha cheklisti"
    assert len(calls[0][1]["checklist"]["tasks"]) == 2

    edited = await client.edit_message_checklist(
        "biz-1",
        555,
        404,
        build_input_checklist("Yangilangan", [(1, "Brif"), (2, "Toʻlov")]),
    )
    assert edited == {"message_id": 404}
    assert calls[1][0] == "editMessageChecklist"

    update = {
        "update_id": 800,
        "business_message": {
            "message_id": 405,
            "chat": {"id": 555},
            "from": {"id": 555, "first_name": "Aziz"},
            "checklist_tasks_done": {
                "checklist_message": {"message_id": 404},
                "marked_as_done_task_ids": [1],
                "marked_as_not_done_task_ids": [2],
            },
        },
    }
    parsed = extract_checklist_tasks_done(update)
    assert parsed is not None
    assert parsed["checklist_message_id"] == 404
    assert parsed["marked_as_done_task_ids"] == [1]

    executed_sql = []

    class FakeConn:
        async def execute(self, sql, params):
            executed_sql.append((sql.strip(), params))

        async def commit(self):
            executed_sql.append(("COMMIT", ()))

    class FakeDB:
        async def get_connection(self):
            return FakeConn()

    import src.services.api_server.webhooks as wh_mod
    orig_get_db = wh_mod._get_db_instance
    wh_mod._get_db_instance = lambda: FakeDB()
    try:
        webhook_res = await process_telegram_ai_update(update)
    finally:
        wh_mod._get_db_instance = orig_get_db

    assert webhook_res["handled"] is True
    assert webhook_res["update_type"] == "checklist_tasks_done"
    assert webhook_res["synced_count"] == 2
    assert any("UPDATE client_checklists" in item[0] for item in executed_sql)


@pytest.mark.asyncio
async def test_lead_profile_enrichment_and_business_read_receipt():
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        if method == "getUserPersonalChatMessages":
            return {
                "ok": True,
                "result": [
                    {
                        "message_id": 1,
                        "chat": {"title": "Smile Stomatologiya", "username": "smile_dent_uz"},
                        "text": "Zamonaviy stomatologiya klinikasi va implantatsiya xizmatlari",
                    },
                    {
                        "message_id": 2,
                        "text": "Yangi filialimiz ochildi, doktor koʻrigi bepul",
                    },
                ],
            }
        return {"ok": True, "result": True}

    client = TelegramBotAPI10Client("token", transport=transport)
    profile = await enrich_lead_from_personal_channel(
        client,
        user_id=707,
        user_info={"user_rating": {"level": 4}, "birthdate": {"day": 10, "month": 5}},
    )

    assert profile["channel_title"] == "Smile Stomatologiya"
    assert profile["channel_username"] == "smile_dent_uz"
    assert "medical" in profile["detected_industries"]
    assert profile["user_rating"] == {"level": 4}

    read_ok = await client.read_business_message("biz-conn-1", 707, 99)
    assert read_ok is True
    assert calls[-1] == (
        "readBusinessMessage",
        {"business_connection_id": "biz-conn-1", "chat_id": 707, "message_id": 99},
    )


@pytest.mark.asyncio
async def test_member_role_tags_and_streaming_stop_button():
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        return {"ok": True, "result": True}

    client = TelegramBotAPI10Client("token", transport=transport)
    tag_res = await sync_team_member_tags(
        client,
        -100999,
        {101: "Hunter", 102: "Setter", 103: "Moliyachi"},
    )
    assert tag_res["applied"] == {101: "Hunter", 102: "Setter", 103: "Moliyachi"}
    assert not tag_res["failed"]

    with pytest.raises(ValueError, match="at most 16 characters"):
        await client.set_chat_member_tag(-100999, 101, tag="JudaUzunLavozimNomi123")

    await client.send_message_draft(
        101,
        1,
        text="Hisoblanmoqda...",
        can_stop=True,
        keep_on_stop=True,
    )
    assert calls[-1][0] == "sendMessageDraft"
    assert calls[-1][1]["can_stop"] is True
    assert calls[-1][1]["keep_on_stop"] is True

    stop_update = {
        "update_id": 901,
        "stopped_message_generation": {
            "chat": {"id": 101},
            "draft_id": 1,
            "date": 1795350000,
        },
    }
    stopped = extract_stopped_message_generation(stop_update)
    assert stopped is not None
    assert stopped["draft_id"] == 1
    wh = await process_telegram_ai_update(stop_update)
    assert wh["handled"] is True
    assert wh["update_type"] == "stopped_message_generation"
    from src.services.core.telegram.telegram_ai_features import consume_draft_stopped
    assert consume_draft_stopped(101, 1) is True
    assert consume_draft_stopped(101, 1) is False


@pytest.mark.asyncio
async def test_styled_buttons_ephemeral_10_4_and_adaptive_kpi_report(monkeypatch):
    monkeypatch.setenv("WIDGETS_ENABLED", "1")
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 500}}

    client = TelegramBotAPI10Client("token", transport=transport)

    ok_btn = build_styled_inline_button("Tasdiqlash", style="success", callback_data="ok:1")
    no_btn = build_styled_inline_button("Rad etish", style="danger", callback_data="no:1")
    locked_btn = build_styled_inline_button("Tasdiqlangan", style="primary", disabled=True)
    dt_ent = build_date_time_entity(0, 10, 1795350000, date_time_format="relative")

    assert ok_btn == {"text": "Tasdiqlash", "style": "success", "callback_data": "ok:1"}
    assert no_btn["style"] == "danger"
    assert locked_btn == {"text": "Tasdiqlangan", "style": "primary", "disabled": {}}
    assert dt_ent["type"] == "date_time"

    eph_params = build_ephemeral_parameters(
        callback_query_id="cb-99",
        replace_callback_query_message=True,
    )
    await client.send_ephemeral_message(
        None,
        "Faqat sizga koʻrinadi",
        ephemeral_message_parameters=eph_params,
    )
    assert calls[-1][0] == "sendMessage"
    assert calls[-1][1]["ephemeral_message_parameters"] == {
        "callback_query_id": "cb-99",
        "replace_callback_query_message": True,
    }

    # Private chat -> sends Bot API 10.4 HTML Widget and forwards message_thread_id
    await send_oisha_kpi_report(
        client,
        777,
        title="Kunlik Moliya va Sotuv",
        subtitle="2026-11-22",
        kpis=[("Tushum", "45M"), ("Lidlar", 18)],
        table_headers=["Menejer", "Sotuv"],
        table_rows=[["Ali", "25M"], ["Vali", "20M"]],
        numeric_cols=(1,),
        progress_done=18,
        progress_total=20,
        is_private_chat=True,
        message_thread_id=12,
    )
    assert calls[-1][0] == "sendWidget"
    assert calls[-1][1]["message_thread_id"] == 12

    # When widgets are disabled, text fallback preserves table rows and progress
    monkeypatch.setenv("WIDGETS_ENABLED", "0")
    await send_oisha_kpi_report(
        client,
        777,
        title="Kunlik Moliya va Sotuv",
        subtitle="2026-11-22",
        kpis=[("Tushum", "45M")],
        table_headers=["Menejer", "Sotuv"],
        table_rows=[["Ali", "25M"]],
        progress_done=18,
        progress_total=20,
        is_private_chat=True,
    )
    assert calls[-1][0] == "sendMessage"
    assert "Progress: 18/20" in calls[-1][1]["text"]
    assert "Ali | 25M" in calls[-1][1]["text"]

    # Group chat -> sends Bot API 10.1/10.5 Rich Message with compact table, progress & blockquote
    await send_oisha_kpi_report(
        client,
        -100777,
        title="Guruh Hisoboti",
        subtitle="2026-11-22",
        kpis=[("Reja", "90%")],
        table_headers=["Boʻlim", "Ball"],
        table_rows=[["Sotuv", 95]],
        numeric_cols=(1,),
        progress_done=9,
        progress_total=10,
        details_text="Qoʻshimcha tafsilotlar",
        is_private_chat=False,
    )
    assert calls[-1][0] == "sendRichMessage"
    blocks = calls[-1][1]["rich_message"]["blocks"]
    assert any(b["type"] == "paragraph" and "Progress: 9/10" in b["text"] for b in blocks)
    assert any(b["type"] == "table" and b.get("is_compact") is True for b in blocks)
    assert any(b["type"] == "expandable_blockquote" for b in blocks)
    assert rich_button_row([ok_btn])["type"] == "buttons"
    assert rich_table(["A"], [["1"]])["type"] == "table"

    # Widget router handles ack and refresh_kpi
    from src.services.core.telegram.widgets.client import WidgetClient
    router = build_widget_router("token", [777])
    router.client = WidgetClient(client)
    ack_res = await router.handle_update(
        {"widget_query": {"id": "wq-1", "from": {"id": 777}, "type": {"type": "data"}, "data": "ack"}}
    )
    assert ack_res["handled"] is True
    assert calls[-1][0] == "answerWidgetQuery"


def test_get_owner_topic_id_reads_env_safely(monkeypatch):
    monkeypatch.delenv("OWNER_TOPIC_FINANCE", raising=False)
    assert get_owner_topic_id("finance") is None

    monkeypatch.setenv("OWNER_TOPIC_FINANCE", "invalid")
    assert get_owner_topic_id("finance") is None

    monkeypatch.setenv("OWNER_TOPIC_FINANCE", "0")
    assert get_owner_topic_id("finance") is None

    monkeypatch.setenv("OWNER_TOPIC_FINANCE", "2199290")
    assert get_owner_topic_id("finance") == 2199290


@pytest.mark.asyncio
async def test_private_kpi_report_falls_back_to_rich_message_when_widget_rejected(monkeypatch):
    monkeypatch.setenv("WIDGETS_ENABLED", "1")
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        if method == "sendWidget":
            return {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: INPUT_MEDIA_WIDGET_NOT_ALLOWED",
            }
        return {"ok": True, "result": {"message_id": 601}}

    client = TelegramBotAPI10Client("token", transport=transport)
    res = await send_oisha_kpi_report(
        client,
        777,
        title="Moliya",
        subtitle="2026-11-22",
        kpis=[("Kirim", "10M")],
        table_headers=["Band", "Summa"],
        table_rows=[["Savdo", "10M"]],
        numeric_cols=(1,),
        progress_done=18,
        progress_total=20,
        is_private_chat=True,
        message_thread_id=2199290,
    )

    assert res["ok"] is True
    assert res["mode"] == "rich"
    assert [m for m, _ in calls] == ["sendWidget", "sendRichMessage"]
    rich_blocks = calls[-1][1]["rich_message"]["blocks"]
    assert rich_blocks[0] == {"type": "heading", "text": "Moliya", "size": 3}
    assert any(b["type"] == "paragraph" and "Progress: 18/20" in b["text"] for b in rich_blocks)
    assert calls[-1][1]["message_thread_id"] == 2199290

