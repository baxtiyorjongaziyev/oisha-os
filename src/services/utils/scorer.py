import logging

logger = logging.getLogger(__name__)


class Scorer:
    @staticmethod
    def calculate_score(user_data, dosye=None):
        """
        Mijoz ballini hisoblash (1-100).
        user_data: dict (DB dan yoki Telegramdan olingan asosiy info)
        dosye: dict (Scouter dan olingan chuqur ma'lumotlar)
        """
        score = 0

        # 1. Profil to'liqligi (Max 10)
        if user_data.get("username"):
            score += 5
        if user_data.get("phone"):
            score += 5

        if not dosye:
            return min(score, 100)

        # 2. Bio Tahlili (Max 25)
        bio = str(dosye.get("bio", "")).lower()
        expert_keywords = [
            "ceo",
            "founder",
            "asoschi",
            "rahbar",
            "manager",
            "direktor",
            "director",
            "owner",
            "tadbirkor",
        ]
        business_keywords = [
            "marketing",
            "brending",
            "branding",
            "biznes",
            "business",
            "loyiha",
            "project",
            "invest",
        ]

        for kw in expert_keywords:
            if kw in bio:
                score += 15
                break
        for kw in business_keywords:
            if kw in bio:
                score += 10
                break

        # 3. Ijtimoiy aloqalar (Umumiy guruhlar) (Max 25)
        mutual_count = len(dosye.get("common_groups", []))
        if mutual_count > 0:
            if mutual_count >= 5:
                score += 25
            elif mutual_count >= 3:
                score += 15
            else:
                score += 10

        # 4. Suhbat mazmuni (Mijozning guruhlardagi gaplari) (Max 40)
        messages = dosye.get("messages_in_groups", [])
        hot_keywords = [
            "narx",
            "qancha",
            "xizmat",
            "shartnoma",
            "loyiha",
            "branding",
            "logo",
            "sayt",
            "uchrashuv",
            "zakaz",
            "buyurtma",
        ]

        msg_hits = 0
        for msg in messages:
            msg_lower = str(msg).lower()
            for kw in hot_keywords:
                if kw in msg_lower:
                    msg_hits += 1
                    break

        if msg_hits >= 3:
            score += 40
        elif msg_hits >= 1:
            score += 20

        final_score = min(score, 100)
        logger.info(f"[SCORER] User {user_data.get('user_id')} score: {final_score}")
        return final_score

    @staticmethod
    def get_tier(score):
        if score >= 80:
            return "VIP (🔥 ISSIQ)"
        if score >= 50:
            return "Sifatli (ILIQ)"
        return "Oddiy (SOVUQ)"
