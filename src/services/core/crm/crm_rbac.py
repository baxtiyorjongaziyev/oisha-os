"""Role-Based Access Control (RBAC — amoCRM Enterprise Xodimlar Ruxsatlari).

amoCRM Enterprise tarifidagi kabi:
- Administrator (Baxtiyorjon): barcha sdelkalar, o'chirish, eksport, sozlamalar.
- ROP (Head of Sales): barcha sdelkalarni nazorat qilish, rejalarni boshqarish.
- Sotuvchi (Shahnoza, Rayxona, Mumtozmaxal): faqat o'z sdelkalari, o'chirish va eksport bloklangan.
- Maydonlar darajasidagi ruxsatlar (Field-level permissions: byudjetni o'zgartirish, mas'ulni almashtirish).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# amoCRM Enterprise standart rollar matrisasi
ROLES_PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "admin": {
        "view_all_leads": True,
        "edit_all_leads": True,
        "delete_leads": True,
        "export_data": True,
        "change_responsible": True,
        "manage_automations": True,
        "manage_targets": True,
        "manage_users": True,
        "view_profit_margin": True,
    },
    "rop": {
        "view_all_leads": True,
        "edit_all_leads": True,
        "delete_leads": False,
        "export_data": True,
        "change_responsible": True,
        "manage_automations": True,
        "manage_targets": True,
        "manage_users": False,
        "view_profit_margin": True,
    },
    "seller": {
        "view_all_leads": True,
        "edit_all_leads": False,
        "delete_leads": False,
        "export_data": False,
        "change_responsible": False,
        "manage_automations": False,
        "manage_targets": False,
        "manage_users": False,
        "view_profit_margin": False,
    },
}

DEFAULT_USERS_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": 8128012,
        "name": "Baxtiyorjon Gaziyev",
        "email": "baxtiyorjon@jonbranding.uz",
        "role": "admin",
        "role_title": "Bosh Administrator & Ta'sischi",
        "status": "Faol",
    },
    {
        "id": 13021974,
        "name": "Shahnoza Abdijabborova",
        "email": "shahnoza@jonbranding.uz",
        "role": "seller",
        "role_title": "Yetakchi Sotuvchi Menejer",
        "status": "Faol",
    },
    {
        "id": 9000001,
        "name": "Rayxona",
        "email": "rayxona@jonbranding.uz",
        "role": "seller",
        "role_title": "Sotuvchi Menejer",
        "status": "Faol",
    },
    {
        "id": 9000002,
        "name": "Mumtozmaxal",
        "email": "mumtozmaxal@jonbranding.uz",
        "role": "seller",
        "role_title": "Sotuvchi Menejer",
        "status": "Faol",
    },
]


class CrmRbacGuard:
    """Xodimlar huquqlarini tekshiruvchi va sdelkalarni filtrlovchi qo'riqchi."""

    def __init__(self, users_registry: Optional[List[Dict[str, Any]]] = None) -> None:
        self.users = users_registry or DEFAULT_USERS_REGISTRY
        self.permissions = ROLES_PERMISSIONS

    def get_user_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Ism bo'yicha foydalanuvchini topish."""
        n_clean = name.strip().lower()
        for u in self.users:
            if n_clean in u["name"].lower():
                return u
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """ID bo'yicha foydalanuvchini topish."""
        for u in self.users:
            if u["id"] == user_id:
                return u
        return None

    def can_perform(self, role: str, action: str) -> bool:
        """Berilgan rol uchun ushbu amalga ruxsat bormi?"""
        role_rules = self.permissions.get(role, self.permissions["seller"])
        return role_rules.get(action, False)

    def can_edit_lead(self, user_role: str, user_name: str, lead_responsible: str) -> bool:
        """Sdelkani tahrirlash huquqi tekshiruvi."""
        if self.can_perform(user_role, "edit_all_leads"):
            return True
        return user_name.strip().lower() in lead_responsible.strip().lower()

    def can_change_lead_responsible(self, user_role: str) -> bool:
        """Sdelkaning mas'ul xodimini o'zgartirish ruxsati."""
        return self.can_perform(user_role, "change_responsible")

    def filter_leads_for_user(
        self,
        leads: List[Dict[str, Any]],
        user_name: str,
        user_role: str,
        scope: str = "all",
    ) -> List[Dict[str, Any]]:
        """Menejer faqat o'z sdelkalarini ko'rish rejimi yoqilganda filtrlash."""
        if scope == "mine" or (user_role == "seller" and scope == "mine_strict"):
            return [
                l for l in leads
                if user_name.strip().lower() in str(l.get("responsible_name") or "").lower()
            ]
        return leads

    def validate_action(
        self,
        user_name: str,
        action: str,
        lead_responsible: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Amalni to'liq tekshirish va rad etilsa tushunarli sabab qaytarish."""
        user = self.get_user_by_name(user_name)
        role = user["role"] if user else "seller"

        if action in ("delete_leads", "export_data", "manage_automations", "manage_targets"):
            allowed = self.can_perform(role, action)
            if not allowed:
                return {
                    "allowed": False,
                    "reason": f"Ushbu amal faqat Administrator yoki ROP uchun ruxsat etilgan ({action})",
                }

        if action == "edit_lead" and lead_responsible:
            if not self.can_edit_lead(role, user_name, lead_responsible):
                return {
                    "allowed": False,
                    "reason": "Siz faqat o'zingizga biriktirilgan sdelkalarni tahrirlashingiz mumkin",
                }

        return {"allowed": True, "role": role}

    def get_users_list(self) -> List[Dict[str, Any]]:
        """Barcha ro'yxatdan o'tgan foydalanuvchilar va ularning huquqlari."""
        res = []
        for u in self.users:
            role = u["role"]
            perms = self.permissions.get(role, {})
            res.append({
                **u,
                "permissions": perms,
            })
        return res
