import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GlobalServices:
    """Dunyodagi eng yaxshi bepul biznes API'lar bilan ishlash moduli."""
    
    # Eslatma: Foydalanuvchi o'z API keylarini keyinchalik config.py ga qo'shishi mumkin.
    # Hozircha umumiy va bepul (key talab qilmaydigan yoki fallbackli) funksiyalar.
    
    @staticmethod
    def search_news(query, api_key=None):
        """Global bozor yangiliklarini qidirish (NewsAPI)."""
        if not api_key:
            return "NewsAPI kaliti ko'rsatilmadi. Iltimos, config.py ga NEWS_API_KEY ni qo'shing."
        
        url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&language=uz&apiKey={api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                articles = response.json().get('articles', [])
                summary = f"'{query}' bo'yicha so'nggi yangiliklar (Global):\n"
                for art in articles[:3]:
                    summary += f"- {art['title']} ({art['source']['name']})\n"
                return summary
            return "Yangiliklarni olishda xatolik yuz berdi."
        except Exception as e:
            logger.error(f"[NEWS API ERROR] {e}")
            return f"Yangiliklar xatosi: {e}"

    @staticmethod
    def search_duckduckgo(query):
        """DuckDuckGo orqali bepul va cheksiz qidiruv (Instant Answers API)."""
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                abstract = data.get('AbstractText', '')
                if abstract:
                    return f"DuckDuckGo ma'lumoti: {abstract}"
                
                # Agar abstract yo'q bo'lsa, RelatedTopics'dan birinchisini olamiz
                related = data.get('RelatedTopics', [])
                if related and 'Text' in related[0]:
                    return f"Mavzu bo'yicha: {related[0]['Text']}"
            return "Ma'lumot topilmadi."
        except Exception as e:
            logger.error(f"[DDG SEARCH ERROR] {e}")
            return f"Qidiruv xatosi: {e}"

    @staticmethod
    def validate_email(email, api_key=None):
        """Email manzilini tekshirish (Abstract API - Free Tier)."""
        if not api_key:
            return None # API key bo'lmasa ishlamaydi
        
        url = f"https://emailvalidation.abstractapi.com/v1/?api_key={api_key}&email={email}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                is_deliverable = data.get('deliverability') == 'DELIVERABLE'
                return {
                    'is_valid': is_deliverable,
                    'is_disposable': data.get('is_disposable_email', {}).get('value', False),
                    'score': data.get('quality_score', 0)
                }
            return None
        except Exception as e:
            logger.error(f"[ABSTRACT EMAIL ERROR] {e}")
            return None

    @staticmethod
    def get_crypto_price(coin_id="bitcoin"):
        """CoinGecko orqali kripto narxini olish (Bepul)."""
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,uzs"
        try:
            # Eslatma: CoinGecko free tier ba'zan rate limit berishi mumkin
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json().get(coin_id, {})
                return {
                    'usd': data.get('usd'),
                    'uzs': data.get('uzs')
                }
            return None
        except Exception as e:
            logger.error(f"[COINGECKO ERROR] {e}")
            return None

    @staticmethod
    def get_ip_info(ip_address=""):
        """IP-API orqali IP haqida ma'lumot olish (Bepul, non-commercial)."""
        # ip_address bo'sh bo'lsa serverning o'z IP sini tekshiradi
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode,regionName,city,zip,timezone,isp,org,as,query"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data
            return None
        except Exception as e:
            logger.error(f"[IP-API ERROR] {e}")
            return None
