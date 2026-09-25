import pytest
from unittest.mock import patch, MagicMock
from src.services.core.instagram.leadgen_watchdog import send_lead_sos_alert, _DISPATCHED_SOS


def test_send_lead_sos_alert():
    _DISPATCHED_SOS.clear()

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        with patch.dict("os.environ", {"BOT_TOKEN": "mock_token", "TARGET_LEADS_GROUP_ID": "-100123", "TARGET_LEADS_TOPIC_ID": "1020"}):
            # First send: should succeed
            res1 = send_lead_sos_alert("12345", 999, "sheets", "Quota exceeded")
            assert res1 is True
            assert mock_post.call_count == 1

            # Second send with same key: should be deduplicated
            res2 = send_lead_sos_alert("12345", 999, "sheets", "Quota exceeded")
            assert res2 is False
            assert mock_post.call_count == 1

            # Different channel: should send
            res3 = send_lead_sos_alert("12345", 999, "telegram", "Chat not found")
            assert res3 is True
            assert mock_post.call_count == 2
