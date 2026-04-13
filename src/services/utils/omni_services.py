import requests
import logging
import json

logger = logging.getLogger(__name__)

class OmniServices:
    """Omni-Channel integratsiyalar (YouTube, WhatsApp, TikTok, Google) moduli."""
    
    @staticmethod
    def youtube_search(query, api_key=None):
        """YouTube dan videolar qidirish (Quota limits apply)."""
        if not api_key:
            return "YouTube API key topilmadi."
        
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&maxResults=3&key={api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                items = response.json().get('items', [])
                summary = f"YouTube natijalari ('{query}'):\n"
                for item in items:
                    title = item['snippet']['title']
                    video_id = item['id'].get('videoId', '')
                    summary += f"- {title} (https://youtu.be/{video_id})\n"
                return summary
            return "YouTube qidiruvida xatolik."
        except Exception as e:
            logger.error(f"[YOUTUBE ERROR] {e}")
            return f"YouTube xatosi: {e}"

    @staticmethod
    def send_whatsapp_message(phone, text, api_token=None, phone_id=None):
        """WhatsApp Cloud API orqali xabar yuborish (1000 free monthly)."""
        if not api_token or not phone_id:
            return False
            
        url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        data = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text}
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[WHATSAPP ERROR] {e}")
            return False

    @staticmethod
    def google_search_limited(query, api_key=None, cx=None):
        """Google Custom Search (100 bepul query kuniga)."""
        if not api_key or not cx:
            return "Google Search API/CX topilmadi."
            
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={api_key}&cx={cx}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                items = response.json().get('items', [])
                summary = f"Google natijalari ('{query}'):\n"
                for item in items[:3]:
                    summary += f"- {item['title']} ({item['link']})\n"
                return summary
            return "Google Search xatolik."
        except Exception as e:
            logger.error(f"[GOOGLE SEARCH ERROR] {e}")
            return f"Google xatosi: {e}"

    @staticmethod
    def get_huggingface_model_info(model_id):
        """HuggingFace dan model haqida ma'lumot (Bepul API)."""
        url = f"https://huggingface.co/api/models/{model_id}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('id'),
                    'downloads': data.get('downloads', 0),
                    'likes': data.get('likes', 0),
                    'pipeline': data.get('pipeline_tag')
                }
            return None
        except Exception as e:
            logger.error(f"[HF API ERROR] {e}")
            return None
