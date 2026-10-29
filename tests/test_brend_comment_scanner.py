"""
Tests for InstagramCommentStore and BrendCommentScanner.
Verifies deduplication, restart resumption without duplicate DMs,
multi-comment handling, and error recovery.
"""
from __future__ import annotations

import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.services.core.instagram.comment_store import InstagramCommentStore
from src.services.core.instagram.brend_comment_scanner import (
    scan_and_process_brend_comments,
    _is_own_account,
    _has_existing_reply,
)
from src.services.core.instagram.agent_constants import (
    TARGET_BREND_VIDEO_SHORTCODE,
    BREND_COMMENT_DM_TEMPLATE,
)


@pytest.fixture
def temp_store(tmp_path):
    """Provides a fresh isolated SQLite comment store for each test."""
    db_file = tmp_path / "test_instagram_comments.db"
    return InstagramCommentStore(db_path=db_file)


def test_comment_store_claim_and_idempotency(temp_store):
    """Verifies atomic comment claim and prevents duplicate claims."""
    cid = "comm_1001"
    mid = "media_555"

    assert not temp_store.is_comment_processed(cid)

    # First claim succeeds
    claimed = temp_store.claim_comment(
        comment_id=cid,
        media_id=mid,
        user_id="user_1",
        username="alisher",
        text="Brend",
        keyword="brend",
    )
    assert claimed is True

    # Second claim for same comment_id fails immediately (idempotency)
    claimed_again = temp_store.claim_comment(
        comment_id=cid,
        media_id=mid,
        user_id="user_1",
        username="alisher",
        text="Brend",
        keyword="brend",
    )
    assert claimed_again is False


def test_comment_store_dm_success_and_user_dedup(temp_store):
    """Verifies recording DM success and user contact tracking."""
    cid = "comm_1002"
    mid = "media_555"
    uid = "user_2"
    uname = "jasur_biz"

    temp_store.claim_comment(cid, mid, uid, uname, "Brend narxi qancha?", "brend")
    assert not temp_store.has_user_received_dm(uid, uname, mid)

    temp_store.record_dm_success(
        comment_id=cid,
        media_id=mid,
        user_id=uid,
        username=uname,
        dm_text="Assalomu alaykum!",
        public_reply_text="Direct'da yozdim",
    )

    # Now marked as processed
    assert temp_store.is_comment_processed(cid)

    # User is now registered as contacted for this campaign
    assert temp_store.has_user_received_dm(uid, uname, mid)

    # Another comment from the same user should be detected as already contacted
    assert temp_store.has_user_received_dm(uid, "different_name", mid)


def test_comment_store_skipped_and_checkpoints(temp_store):
    """Verifies skipped statuses and resumption checkpoints."""
    cid = "comm_1003"
    mid = "media_777"

    temp_store.record_skipped(
        comment_id=cid,
        media_id=mid,
        user_id="user_3",
        username="nodir",
        text="Salom zo'r ekan",
        reason="no_keyword",
    )

    assert temp_store.is_comment_processed(cid)

    temp_store.update_checkpoint(
        media_id=mid,
        last_comment_id=cid,
        last_comment_ts="2026-10-16T12:00:00Z",
        scanned_count=10,
        dm_count=2,
    )

    cp = temp_store.get_checkpoint(mid)
    assert cp is not None
    assert cp["last_comment_id"] == cid
    assert cp["total_scanned"] == 10
    assert cp["total_dms"] == 2


def test_is_own_account_check():
    """Verifies detection of own account comments."""
    assert _is_own_account(None, "12345") is True  # Missing from = media owner
    assert _is_own_account({}, "12345") is True
    assert _is_own_account({"id": "12345", "username": "baxtiyorjongaziyev"}, "12345") is True
    assert _is_own_account({"id": "99999", "username": "baxtiyorjongaziyev"}, "12345") is True
    assert _is_own_account({"id": "99999", "username": "jonbranding"}, "12345") is True
    assert _is_own_account({"id": "55555", "username": "other_user"}, "12345") is False


def test_has_existing_reply():
    """Verifies detection of already replied comments from Instagram thread."""
    own_id = "12345"
    comment_without_replies = {"replies": {"data": []}}
    assert _has_existing_reply(comment_without_replies, own_id) is False

    comment_with_our_reply = {
        "replies": {
            "data": [
                {"from": {"id": "12345", "username": "baxtiyorjongaziyev"}, "text": "Rahmat!"}
            ]
        }
    }
    assert _has_existing_reply(comment_with_our_reply, own_id) is True


@pytest.mark.asyncio
async def test_brend_comment_scanner_deduplication_and_resumption(temp_store):
    """
    Critical test:
    1. First run processes comments: sends 1 DM to user A (even if user A commented twice).
    2. Second run (simulating bot restart) scans again:
       MUST skip all previously processed comments and send ZERO duplicate DMs!
    """
    mock_comments = [
        {
            "id": "c_1",
            "text": "Brend",
            "timestamp": "2026-10-16T14:00:00Z",
            "from": {"id": "u_1", "username": "client_one"},
            "replies": {"data": []},
        },
        {
            "id": "c_2",
            "text": "Brend",  # Same user commented 'Brend' a second time!
            "timestamp": "2026-10-16T14:02:00Z",
            "from": {"id": "u_1", "username": "client_one"},
            "replies": {"data": []},
        },
        {
            "id": "c_3",
            "text": "Zo'r gap yo'q",  # General comment, no brend keyword
            "timestamp": "2026-10-16T14:05:00Z",
            "from": {"id": "u_2", "username": "client_two"},
            "replies": {"data": []},
        },
        {
            "id": "c_4",
            "text": "Brend kerak bizga",  # Second qualified user
            "timestamp": "2026-10-16T14:06:00Z",
            "from": {"id": "u_3", "username": "client_three"},
            "replies": {"data": []},
        },
    ]

    with (
        patch("src.services.core.instagram.brend_comment_scanner._fetch_media_comments", return_value=mock_comments),
        patch("src.services.core.instagram.brend_comment_scanner.send_ig_private_reply", return_value=True) as mock_dm,
        patch("src.services.core.instagram.brend_comment_scanner.like_comment", return_value=True) as mock_like,
        patch("src.services.core.instagram.brend_comment_scanner.reply_to_comment", return_value=True) as mock_reply,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        # RUN 1: Fresh scan
        res1 = await scan_and_process_brend_comments(
            media_id="test_media_1",
            access_token="fake_token",
            store=temp_store,
            dry_run=False,
            throttle_seconds=0.0,
        )

        assert res1["ok"] is True
        assert res1["total_comments_fetched"] == 4
        # Exactly 2 DMs sent: for c_1 (client_one) and c_4 (client_three).
        # c_2 was skipped because client_one was already contacted!
        # c_3 was skipped because no keyword.
        assert res1["dms_sent"] == 2
        assert res1["skipped_duplicate_user"] == 1
        assert res1["skipped_no_keyword"] == 1
        assert mock_dm.call_count == 2
        assert mock_like.call_count == 2
        assert mock_reply.call_count == 2

        # Reset mock call counts
        mock_dm.reset_mock()
        mock_like.reset_mock()
        mock_reply.reset_mock()

        # RUN 2: Bot restarts and runs scan again!
        res2 = await scan_and_process_brend_comments(
            media_id="test_media_1",
            access_token="fake_token",
            store=temp_store,
            dry_run=False,
            throttle_seconds=0.0,
        )

        assert res2["ok"] is True
        assert res2["total_comments_fetched"] == 4
        # ZERO DMs sent on second run because everything was already processed and persisted!
        assert res2["dms_sent"] == 0
        assert res2["already_processed"] == 4
        assert mock_dm.call_count == 0
        assert mock_like.call_count == 0
        assert mock_reply.call_count == 0


@pytest.mark.asyncio
async def test_brend_comment_scanner_handles_dm_failure_gracefully(temp_store):
    """Verifies that if Meta API rejects private reply, state is recorded and no crash occurs."""
    mock_comments = [
        {
            "id": "c_fail_1",
            "text": "Brend",
            "timestamp": "2026-10-16T14:00:00Z",
            "from": {"id": "u_fail", "username": "client_fail"},
            "replies": {"data": []},
        }
    ]

    with (
        patch("src.services.core.instagram.brend_comment_scanner._fetch_media_comments", return_value=mock_comments),
        patch("src.services.core.instagram.brend_comment_scanner.send_ig_private_reply", return_value=False),
        patch("src.services.core.instagram.brend_comment_scanner.like_comment", return_value=True),
    ):
        res = await scan_and_process_brend_comments(
            media_id="test_media_fail",
            access_token="fake_token",
            store=temp_store,
            dry_run=False,
            throttle_seconds=0.0,
        )

        assert res["ok"] is True
        assert res["dms_sent"] == 0
        assert res["dms_failed"] == 1
        # It shouldn't crash and should be stored as failure
        stats = temp_store.get_stats("test_media_fail")
        assert stats["breakdown"].get("dm_failed") == 1
