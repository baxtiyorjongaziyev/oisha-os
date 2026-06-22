"""User repository for user-related database operations."""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class UserRepository(BaseRepository):
    """Repository for user operations."""

    async def init_table(self) -> None:
        """Create users table and run migrations."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                business_type TEXT,
                region TEXT,
                brand_name TEXT,
                service_type TEXT,
                deadline TEXT,
                role TEXT,
                is_lead_forwarded BOOLEAN DEFAULT 0,
                last_seen DATETIME,
                created_at DATETIME,
                last_name TEXT,
                contact_name TEXT,
                bio TEXT,
                avatar_analysis TEXT,
                mutual_groups_count INTEGER DEFAULT 0,
                social_analysis TEXT,
                lead_score INTEGER DEFAULT 0,
                position TEXT,
                intent TEXT,
                crm_synced BOOLEAN DEFAULT 0,
                processed_at DATETIME,
                detailed_role TEXT,
                meeting_time TEXT,
                meeting_status TEXT DEFAULT 'pending',
                lead_quality TEXT,
                journey_stage TEXT,
                journey_status TEXT,
                journey_next_action TEXT,
                close_probability REAL DEFAULT 0,
                last_client_message_at DATETIME,
                last_ai_message_at DATETIME,
                lifecycle_updated_at DATETIME
            )
        """)

        cols = [
            ("last_name", "TEXT"),
            ("contact_name", "TEXT"),
            ("bio", "TEXT"),
            ("avatar_analysis", "TEXT"),
            ("mutual_groups_count", "INTEGER DEFAULT 0"),
            ("social_analysis", "TEXT"),
            ("lead_score", "INTEGER DEFAULT 0"),
            ("position", "TEXT"),
            ("intent", "TEXT"),
            ("crm_synced", "BOOLEAN DEFAULT 0"),
            ("processed_at", "DATETIME"),
            ("detailed_role", "TEXT"),
            ("lead_quality", "TEXT"),
            ("journey_stage", "TEXT"),
            ("journey_status", "TEXT"),
            ("journey_next_action", "TEXT"),
            ("close_probability", "REAL DEFAULT 0"),
            ("last_client_message_at", "DATETIME"),
            ("last_ai_message_at", "DATETIME"),
            ("lifecycle_updated_at", "DATETIME"),
        ]
        for col, col_type in cols:
            await self._add_column_if_missing("users", col, col_type)

        # Indexes
        await self._execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
        await self._execute("CREATE INDEX IF NOT EXISTS idx_users_intent ON users(intent)")
        await self._execute("CREATE INDEX IF NOT EXISTS idx_users_crm_synced ON users(crm_synced)")

    async def upsert_user(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        phone: str = None,
        **kwargs,
    ) -> None:
        """Insert or update a user."""
        now = datetime.now(timezone.utc).isoformat()
        existing = await self._fetch_one(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        )
        if existing:
            fields = []
            values = []
            if username is not None:
                fields.append("username = ?")
                values.append(username)
            if first_name is not None:
                fields.append("first_name = ?")
                values.append(first_name)
            if phone is not None:
                fields.append("phone = ?")
                values.append(phone)
            for key, val in kwargs.items():
                if val is not None:
                    fields.append(f"{key} = ?")
                    values.append(val)
            if fields:
                fields.append("last_seen = ?")
                values.append(now)
                values.append(user_id)
                await self._execute(
                    f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?",  # nosec B608
                    tuple(values),
                )
        else:
            cols = ["user_id", "created_at"]
            vals = [user_id, now]
            if username:
                cols.append("username")
                vals.append(username)
            if first_name:
                cols.append("first_name")
                vals.append(first_name)
            if phone:
                cols.append("phone")
                vals.append(phone)
            for key, val in kwargs.items():
                if val is not None:
                    cols.append(key)
                    vals.append(val)
            placeholders = ", ".join(["?"] * len(vals))
            await self._execute(
                f"INSERT INTO users ({', '.join(cols)}) VALUES ({placeholders})",  # nosec B608
                tuple(vals),
            )

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        return await self._fetch_one(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )

    async def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get user by phone number."""
        return await self._fetch_one(
            "SELECT * FROM users WHERE phone = ?", (phone,)
        )

    async def get_user_id_by_phone(self, phone: str) -> Optional[int]:
        """Get user ID by phone number."""
        row = await self._fetch_one(
            "SELECT user_id FROM users WHERE phone = ?", (phone,)
        )
        return row["user_id"] if row else None

    async def get_all_user_ids(self) -> List[int]:
        """Get all user IDs."""
        return await self._fetch_all_flat("SELECT user_id FROM users")

    async def get_user_by_role(self, role: str) -> Optional[Dict[str, Any]]:
        """Get first user with given role (supports operational aliases)."""
        normalized = str(role or "").strip().lower()
        if not normalized:
            return None
        aliases = {
            "pm": ("pm", "project manager", "farmer"),
            "project manager": ("pm", "project manager", "farmer"),
            "farmer": ("pm", "project manager", "farmer"),
            "finance": ("finance", "moliya", "accountant", "buxgalter"),
            "moliya": ("finance", "moliya", "accountant", "buxgalter"),
            "accountant": ("finance", "moliya", "accountant", "buxgalter"),
            "buxgalter": ("finance", "moliya", "accountant", "buxgalter"),
        }.get(normalized, (normalized,))
        placeholders = ", ".join("?" for _ in aliases)
        params = tuple(aliases) * 3
        return await self._fetch_one(
            f"""
            SELECT user_id, first_name, username, role, detailed_role, position
            FROM users
            WHERE LOWER(TRIM(COALESCE(role, ''))) IN ({placeholders})
               OR LOWER(TRIM(COALESCE(detailed_role, ''))) IN ({placeholders})
               OR LOWER(TRIM(COALESCE(position, ''))) IN ({placeholders})
            ORDER BY
                CASE WHEN LOWER(TRIM(COALESCE(role, ''))) = ? THEN 0 ELSE 1 END,
                user_id
            LIMIT 1
            """,  # nosec
            params + (normalized,),
        )

    async def get_team_roles(self) -> List[Dict[str, Any]]:
        """Get all team members with roles."""
        return await self._fetch_all(
            "SELECT user_id, username, first_name, role FROM users WHERE role IS NOT NULL"
        )

    async def is_crm_synced(self, user_id: int) -> bool:
        """Check if user is synced to CRM."""
        row = await self._fetch_one(
            "SELECT crm_synced FROM users WHERE user_id = ?", (user_id,)
        )
        return bool(row and row.get("crm_synced"))

    async def set_crm_synced(self, user_id: int) -> None:
        """Mark user as CRM synced."""
        await self._execute(
            "UPDATE users SET crm_synced = 1 WHERE user_id = ?", (user_id,)
        )

    async def ensure_owner_admin(self, owner_id: int) -> None:
        """Ensure the owner user exists with admin role."""
        if not owner_id:
            return
        import datetime
        now = datetime.datetime.now().isoformat()
        existing = await self._fetch_one(
            "SELECT user_id FROM users WHERE user_id = ?", (owner_id,)
        )
        if not existing:
            await self._execute(
                "INSERT INTO users (user_id, first_name, role, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
                (owner_id, "Owner", "admin", now, now),
            )
        else:
            await self._execute(
                "UPDATE users SET role = COALESCE(role, ?) WHERE user_id = ?",
                ("admin", owner_id),
            )

    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user info for message controller."""
        return await self._fetch_one(
            """SELECT first_name, username, phone, business_type, region, brand_name,
               service_type, deadline, role, detailed_role, intent,
               is_lead_forwarded, lead_quality FROM users WHERE user_id = ?""",
            (user_id,),
        )

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by Telegram username."""
        return await self._fetch_one(
            "SELECT user_id, first_name, username FROM users WHERE username = ?",
            (username,),
        )

    async def update_lead_journey(
        self,
        user_id: int,
        *,
        stage: str,
        status: str,
        next_action: str,
        close_probability: float = 0.0,
        lifecycle_updated_at: Optional[str] = None,
    ) -> bool:
        """Update lead journey stage."""
        import datetime
        now = lifecycle_updated_at or datetime.datetime.now().isoformat()
        await self._execute(
            "UPDATE users SET journey_stage = ?, journey_status = ?, journey_next_action = ?, close_probability = ?, lifecycle_updated_at = ? WHERE user_id = ?",
            (stage, status, next_action, float(close_probability or 0.0), now, user_id),
        )
        conn = await self._get_conn()
        await conn.commit()
        return True
