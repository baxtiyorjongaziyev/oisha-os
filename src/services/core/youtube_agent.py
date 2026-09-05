"""
YouTube agent — upload Shorts and auto-reply to comments in Baxtiyor
Gaziyev's first-person voice (mirrors the Instagram comment flow).

Auth: an OAuth *user* refresh token for the channel owner. Put these in .env:
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN
    YOUTUBE_CHANNEL_ID          (UC...  — the channel we own; loop guard)

Scopes needed on the refresh token:
    https://www.googleapis.com/auth/youtube.upload
    https://www.googleapis.com/auth/youtube.force-ssl   (read + write comments)

Nothing here runs until all four env vars are set — see `configured`.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import structlog

logger = structlog.get_logger("YouTubeAgent")

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

COMMENT_REPLY_SYSTEM = (
    "Sen — Baxtiyor Gaziyevning O'ZISAN. Brending eksperti va art-direktor, "
    "o'zingning YouTube kanalingdagi izohlarga javob yozyapsan. Kanal mazmuni: "
    "brending, nomlash (naming), logo dizayn, keyslar, ijodiy strategiya.\n"
    "Yozish uslubi:\n"
    "- TIRIK ODAM kabi yoz. Robot, rasmiy, 'aqlli yordamchi' ohangi TAQIQLANADI.\n"
    "- 1-shaxsda gapir: 'men', 'menimcha', 'rahmat'. O'zingni 'Oisha' yoki 'bot' dema.\n"
    "- Do'stona, iliq, jonli — tanishingga javob yozayotgandek.\n"
    "- 'Jon Branding' so'zini ishlatma — bu shaxsiy kanaling.\n"
    "- Izoh nima haqida bo'lsa, o'shanga javob ber. Nom so'ralsa — har kimga "
    "alohida, jarangdor yangi variant.\n"
    "- O'zbekcha, 1-2 gap. Emoji 0-1 ta.\n"
    "- Shablon javob YOZMA."
)


def _env(name: str) -> str:
    from src.settings import settings
    val = getattr(settings, name, None)
    if val is None:
        return os.getenv(name, "").strip()
    getter = getattr(val, "get_secret_value", None)
    return (getter() if callable(getter) else str(val)).strip()


class YouTubeClient:
    """Thin wrapper over the YouTube Data API v3 for our own channel."""

    def __init__(self) -> None:
        self.client_id = _env("YOUTUBE_CLIENT_ID")
        self.client_secret = _env("YOUTUBE_CLIENT_SECRET")
        self.refresh_token = _env("YOUTUBE_REFRESH_TOKEN")
        self.channel_id = _env("YOUTUBE_CHANNEL_ID")

    @property
    def configured(self) -> bool:
        return bool(
            self.client_id
            and self.client_secret
            and self.refresh_token
            and self.channel_id
        )

    def _service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=_SCOPES,
        )
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    # --- upload ---------------------------------------------------------------

    def upload_short(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        privacy: str = "public",
    ) -> dict:
        """Upload a vertical video as a Short. Add #Shorts to the title/desc so
        YouTube classifies it. Returns {ok, video_id, url} or {ok: False, error}."""
        if not self.configured:
            return {"ok": False, "error": "youtube_not_configured"}
        if not os.path.exists(video_path):
            return {"ok": False, "error": f"file_not_found: {video_path}"}

        from googleapiclient.http import MediaFileUpload

        yt = self._service()
        body = {
            "snippet": {
                "title": title if "#Shorts" in title else f"{title} #Shorts",
                "description": description,
                "tags": tags or ["branding", "naming", "logo", "dizayn"],
                "categoryId": "22",  # People & Blogs
            },
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
        try:
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            vid = resp["id"]
            logger.info("[YT] Short uploaded", video_id=vid)
            return {"ok": True, "video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}
        except Exception as exc:  # noqa: BLE001
            logger.error("[YT] upload failed", error=str(exc))
            return {"ok": False, "error": str(exc)}

    # --- comments ----------------------------------------------------------

    def list_unanswered_comments(self, max_videos: int = 10, per_video: int = 50) -> list[dict]:
        """Top-level comments on our recent uploads that we have NOT replied to.

        Each item: {comment_id, text, author, video_id}.
        """
        if not self.configured:
            return []
        yt = self._service()
        out: list[dict] = []
        try:
            search = yt.search().list(
                part="id", channelId=self.channel_id, order="date",
                type="video", maxResults=max_videos,
            ).execute()
            video_ids = [i["id"]["videoId"] for i in search.get("items", [])]
        except Exception as exc:  # noqa: BLE001
            logger.error("[YT] search failed", error=str(exc))
            return []

        for vid in video_ids:
            try:
                page = yt.commentThreads().list(
                    part="snippet,replies", videoId=vid,
                    maxResults=per_video, order="time", textFormat="plainText",
                ).execute()
            except Exception as exc:  # noqa: BLE001
                logger.warning("[YT] commentThreads failed", video_id=vid, error=str(exc))
                continue

            for thread in page.get("items", []):
                top = thread["snippet"]["topLevelComment"]
                cid = top["id"]
                sn = top["snippet"]
                author_cid = sn.get("authorChannelId", {}).get("value", "")
                if author_cid == self.channel_id:
                    continue  # our own comment
                replies = thread.get("replies", {}).get("comments", [])
                mine = any(
                    r["snippet"].get("authorChannelId", {}).get("value") == self.channel_id
                    for r in replies
                )
                if mine:
                    continue
                out.append({
                    "comment_id": cid,
                    "text": sn.get("textDisplay", "") or sn.get("textOriginal", ""),
                    "author": sn.get("authorDisplayName", ""),
                    "video_id": vid,
                })
        return out

    def reply_to_comment(self, parent_comment_id: str, text: str) -> bool:
        if not self.configured:
            return False
        yt = self._service()
        try:
            yt.comments().insert(
                part="snippet",
                body={"snippet": {"parentId": parent_comment_id, "textOriginal": text}},
            ).execute()
            logger.info("[YT] comment reply sent", comment_id=parent_comment_id)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("[YT] comment reply failed", comment_id=parent_comment_id, error=str(exc))
            return False


async def generate_comment_reply(comment_text: str, video_title: str = "", author: str = "") -> str:
    """Context-aware YouTube comment reply via the free-AI router."""
    ctx = f'\nVideo: "{video_title[:200]}"' if video_title else ""
    prompt = (
        f"{ctx}\n"
        f'{author or "Bir odam"} yozgan izoh: "{comment_text}"\n\n'
        f"Shu izohga Baxtiyor nomidan javob yoz:"
    )
    try:
        from src.services.utils.free_ai_router import get_free_ai_router
        result = await get_free_ai_router().generate_text(
            prompt, system=COMMENT_REPLY_SYSTEM, max_tokens=140, temperature=0.7
        )
        reply = (result.text or "").strip().strip('"')
        if reply:
            return reply
    except Exception as exc:  # noqa: BLE001
        logger.warning("[YT] generate_comment_reply fallback: %s", exc)
    import random
    return random.choice(
        ["Izohingiz uchun rahmat! 🙌", "Fikringiz uchun tashakkur 🙏", "Rahmat, yozganingizdan xursandman ✨"]
    )


async def backfill_youtube_comments(*, max_videos: int = 10, max_replies: int = 20, dry_run: bool = False) -> dict:
    """Scan recent uploads, reply to every comment we haven't answered yet."""
    client = YouTubeClient()
    if not client.configured:
        return {"ok": False, "error": "youtube_not_configured"}

    summary = {"scanned": 0, "answered": 0, "errors": 0, "dry_run": dry_run}
    pending = client.list_unanswered_comments(max_videos=max_videos)
    for c in pending:
        if summary["answered"] >= max_replies:
            break
        summary["scanned"] += 1
        if dry_run:
            logger.info("[YT] would answer", comment_id=c["comment_id"], text=c["text"][:60])
            summary["answered"] += 1
            continue
        try:
            reply = await generate_comment_reply(c["text"], author=c["author"])
            import re
            reply = re.sub(r"\[.*?\]", "", reply).strip()
            if client.reply_to_comment(c["comment_id"], reply):
                summary["answered"] += 1
            else:
                summary["errors"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("[YT] backfill reply failed", error=str(exc))
            summary["errors"] += 1
        import asyncio
        await asyncio.sleep(4)  # gentle on quota + AI providers

    logger.info("[YT] backfill complete", **summary)
    return {"ok": True, **summary}
