import logging
import re
from googlesearch import search  # type: ignore

logger = logging.getLogger(__name__)


class OSINTExplorer:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def search_social_profiles(self, full_name, username=None, phone=None):
        """
        Internet tarmog'idan mijoz profillarini qidirish.
        """
        results = {"instagram": None, "linkedin": None, "facebook": None, "other": []}

        query = f'"{full_name}"'
        if username:
            query += f' OR "@{username}"'
        if phone:
            # Telefon raqamini turli formatlarda qidirish
            clean_phone = re.sub(r"\D", "", str(phone))
            query += f' OR "{phone}" OR "{clean_phone}"'

        logger.info(f"[OSINT] Searching for: {query}")

        try:
            # Google orqali qidiruv (birinchi 10 ta natija)
            search_results = list(search(query, num_results=10, sleep_interval=2))

            for url in search_results:
                if "instagram.com" in url.lower():
                    results["instagram"] = url
                elif "linkedin.com/in/" in url.lower():
                    results["linkedin"] = url
                elif "facebook.com" in url.lower() and not results["facebook"]:
                    # Ko'pincha asosiy sahifalar chiqishi mumkin, shuning uchun ehtiyot bo'lamiz
                    results["facebook"] = url
                else:
                    results["other"].append(url)

        except Exception as e:
            logger.error(f"[OSINT ERROR] {e}")

        return results

    def analyze_presence(self, profiles):
        """
        Topilgan profillar asosida qisqacha xulosa chiqarish.
        """
        summary = []
        if profiles["linkedin"]:
            summary.append("Professional (LinkedIn) mavjud.")
        if profiles["instagram"]:
            summary.append("Ijtimoiy (Instagram) faol.")
        if profiles["facebook"]:
            summary.append("Facebook profili topildi.")

        if not summary:
            return "Ochiq manbalarda ma'lumot kam."

        return " | ".join(summary)
