import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def _parse_id_role_pairs(raw: str) -> Dict[int, str]:
    """Parses "id:ROLE,id:ROLE" env value into {id: role}."""
    pairs: Dict[int, str] = {}
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        raw_id, role = chunk.split(":", 1)
        try:
            pairs[int(raw_id.strip())] = role.strip().upper()
        except ValueError:
            continue
    return pairs


class AccessManager:
    """
    Oisha-OS Role-Based Access Control (RBAC).
    Handles permissions for Owner, CEO, PM, and Sales.
    """

    ROLES = {
        "OWNER": "Asoschi (Baxtiyor aka) 👑",
        "CEO": "CEO (Hasan aka) 📈",
        "PM": "Project Manager (Inomjon aka) 📅",
        "SALES": "Sales (Oisha/Oydin opa) 🚀",
    }

    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        # Default mapping based on IDs
        self.user_roles: Dict[int, str] = {owner_id: "OWNER"}

        # Extra standing role grants (e.g. a secondary owner account, a
        # legacy sales fallback) — configurable via .env instead of being
        # invisible hardcoded IDs. Format: "id:ROLE,id:ROLE".
        # ACCESS_MANAGER_FAILSAFE_ROLES defaults to the two IDs this file
        # used to hardcode unconditionally, to avoid a silent access change
        # on upgrade — override/clear it in .env to revoke them.
        failsafe_raw = os.getenv(
            "ACCESS_MANAGER_FAILSAFE_ROLES",
            "150074828:OWNER,8343217526:SALES",
        )
        failsafe_roles = _parse_id_role_pairs(failsafe_raw)
        if failsafe_roles:
            logger.warning(
                "[ACCESS] Fail-safe role grants active (ACCESS_MANAGER_FAILSAFE_ROLES): %s",
                failsafe_roles,
            )
        self.user_roles.update(failsafe_roles)

        # Hardcoded IDs for the team (can be moved to .env later)
        # Hasan aka, Inomjon aka IDs should be added here
        self.team_ids = {
            # Add Hasan aka ID here
            # Add Inomjon aka ID here
        }

    def get_role(self, user_id: int) -> Optional[str]:
        """User uchun rolni aniqlash."""
        return self.user_roles.get(user_id)

    def get_role_name(self, role: str) -> str:
        """Rolning chiroyli nomini qaytarish."""
        return self.ROLES.get(role, "Mehmon 👤")

    def is_authorized(self, user_id: int) -> bool:
        """User tizimga kiritilganmi?"""
        return user_id in self.user_roles or user_id in self.team_ids

    def is_admin(self, user_id: int) -> bool:
        """User admin huquqiga egami (OWNER yoki CEO)?"""
        role = self.get_role(user_id)
        return role in ["OWNER", "CEO"]

    def register_user(self, user_id: int, role: str):
        """Yangi userni rolni bilan ro'yxatdan o'tkazish."""
        if role in self.ROLES:
            self.user_roles[user_id] = role
            logger.info(f"[ACCESS] User {user_id} assigned to role {role}")
