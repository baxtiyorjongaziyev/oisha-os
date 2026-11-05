from src.services.core.crm.meeting_confirmation import (
    AWAITING_CLIENT_CONFIRMATION,
    AWAITING_OUR_CONFIRMATION,
    CONFIRMED,
    NO_MEETING,
    Message,
    classify_meeting,
    pre_visit_warning,
)


def test_client_named_time_without_our_confirmation():
    # 2026-11-04 Saidov Sh. yozishmasi (owner taqdim etgan matn)
    msgs = [
        Message(False, "Lokatsiya tashlab berolasizmi?"),
        Message(True, "Воалайкум ассалом"),
        Message(False, "qachon borganimiz qulay boladi sizga Bugun ertaga"),
        Message(True, "Бугун обеддан кейин"),
        Message(True, "Соат 16:00"),
        Message(False, "Biz keldik"),
    ]
    status = classify_meeting(msgs)
    assert status == AWAITING_OUR_CONFIRMATION
    assert pre_visit_warning(status)


def test_confirmed_when_we_agree_after_client_time():
    msgs = [Message(True, "Соат 16:00"), Message(False, "Xop, 16:00 da boramiz")]
    assert classify_meeting(msgs) == CONFIRMED
    assert pre_visit_warning(CONFIRMED) is None


def test_awaiting_client_when_we_propose():
    msgs = [Message(False, "Ertaga soat 11:00 mos bo'ladimi?")]
    assert classify_meeting(msgs) == AWAITING_CLIENT_CONFIRMATION


def test_no_meeting_without_time():
    assert classify_meeting([Message(True, "Salom")]) == NO_MEETING
