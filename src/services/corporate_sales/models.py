"""
Korporativ sotuvchilar va Telegram muloqotlari modellari.
Jon Branding sotuv sifat nazorati tizimi uchun maʼlumotlar tuzilmasi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageSenderType(str, Enum):
    """Xabar yuboruvchi turi."""
    SELLER = "seller"
    CLIENT = "client"
    UNKNOWN = "unknown"


@dataclass
class CorporateSeller:
    """Korporativ sotuvchi hisobi."""
    seller_id: int
    name: str
    phone: str
    session_string: str
    is_active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Modelni lugʻat koʻrinishiga oʻtkazish."""
        return {
            "seller_id": self.seller_id,
            "name": self.name,
            "phone": self.phone,
            "session_string": self.session_string,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: Any) -> "CorporateSeller":
        """Maʼlumotlar bazasi qatoridan model yasash."""
        if isinstance(row, dict):
            return cls(
                seller_id=row["seller_id"],
                name=row["name"],
                phone=row["phone"],
                session_string=row.get("session_string", ""),
                is_active=bool(row.get("is_active", 1)),
                created_at=row.get("created_at", ""),
                updated_at=row.get("updated_at", ""),
            )
        return cls(
            seller_id=row[0],
            name=row[1],
            phone=row[2],
            session_string=row[3] if len(row) > 3 else "",
            is_active=bool(row[4]) if len(row) > 4 else True,
            created_at=row[5] if len(row) > 5 else "",
            updated_at=row[6] if len(row) > 6 else "",
        )


@dataclass
class MonitoredChatMessage:
    """Kuzatilgan bitta xabar yozuvi."""
    message_id: int
    sender_type: MessageSenderType
    sender_name: str
    text: str
    sent_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_voice: bool = False
    duration_seconds: int = 0

    def to_transcript_line(self) -> str:
        """Suhbat transkripti qatorini shakllantirish."""
        role = "Menejer" if self.sender_type == MessageSenderType.SELLER else "Mijoz"
        clean_text = self.text.strip() if self.text else "[Matnsiz media]"
        time_str = self.sent_at.strftime("%H:%M")
        return f"[{time_str}] [{role} ({self.sender_name})]: {clean_text}"


@dataclass
class ConversationBuffer:
    """Menejer va bitta mijoz oʻrtasidagi faol dialog buferi."""
    seller_id: int
    seller_name: str
    client_peer_id: int
    client_name: str = ""
    client_username: str = ""
    client_phone: str = ""
    messages: List[MonitoredChatMessage] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_message(self, message: MonitoredChatMessage) -> None:
        """Yangi xabarni buferga qoʻshish."""
        self.messages.append(message)
        self.last_activity_at = datetime.now(timezone.utc)

    def is_idle(self, timeout_seconds: int = 300) -> bool:
        """Dialog belgilangan vaqt davomida tinch turganini tekshirish."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_activity_at).total_seconds()
        return elapsed >= timeout_seconds

    def to_transcript(self) -> str:
        """Toʻliq transkript matnini olish."""
        return "\n".join(msg.to_transcript_line() for msg in self.messages)

    def get_message_count(self) -> int:
        """Xabarlar sonini qaytarish."""
        return len(self.messages)

    def get_seller_message_count(self) -> int:
        """Menejer yuborgan xabarlar soni."""
        return sum(
            1 for m in self.messages if m.sender_type == MessageSenderType.SELLER
        )

    def get_client_message_count(self) -> int:
        """Mijoz yuborgan xabarlar soni."""
        return sum(
            1 for m in self.messages if m.sender_type == MessageSenderType.CLIENT
        )

    def is_substantive(self) -> bool:
        """Suhbat tahlil qilish uchun yetarli hajmga egaligini tekshirish."""
        return (
            self.get_seller_message_count() >= 1
            and self.get_client_message_count() >= 1
            and self.get_message_count() >= 3
        )

    def clear(self) -> None:
        """Buferni tozalash."""
        self.messages.clear()
        self.last_activity_at = datetime.now(timezone.utc)


@dataclass
class SellerPerformanceSummary:
    """Sotuvchi boʻyicha jamlangan sifat koʻrsatkichlari."""
    seller_id: int
    seller_name: str
    phone: str
    total_dialogs: int = 0
    average_score: float = 0.0
    excellent_count: int = 0
    good_count: int = 0
    critical_count: int = 0
    common_weaknesses: List[str] = field(default_factory=list)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Lugʻat koʻrinishida olish."""
        return {
            "seller_id": self.seller_id,
            "seller_name": self.seller_name,
            "phone": self.phone,
            "total_dialogs": self.total_dialogs,
            "average_score": self.average_score,
            "excellent_count": self.excellent_count,
            "good_count": self.good_count,
            "critical_count": self.critical_count,
            "common_weaknesses": self.common_weaknesses,
            "updated_at": self.updated_at,
        }
