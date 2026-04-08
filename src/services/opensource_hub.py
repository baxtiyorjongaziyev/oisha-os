import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OpenSourceHub:
    """GitHub va HuggingFace orqali ochiq kodli resurslarni qidirish moduli."""

    @staticmethod
    def search_github_trending_ai(query="ai-agent", days_back=30):
        """GitHub da trendda bo'lgan AI loyihalarni qidirish."""
        date_limit = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q={query}+created:>{date_limit}&sort=stars&order=desc"
        headers = {"Accept": "application/vnd.github.v3+json"}
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                items = response.json().get('items', [])
                summary = f"GitHub Trending AI ('{query}', last {days_back} days):\n"
                for repo in items[:5]:
                    summary += f"- {repo['full_name']} (⭐{repo['stargazers_count']}): {repo['description']}\n  Link: {repo['html_url']}\n"
                return summary
            return "GitHub qidiruvida xatolik yuz berdi."
        except Exception as e:
            logger.error(f"[GITHUB HUB ERROR] {e}")
            return f"GitHub xatosi: {e}"

    @staticmethod
    def search_huggingface_trending(task="text-generation"):
        """HuggingFace da trendda bo'lgan modellarni qidirish."""
        # HuggingFace API orqali modellarni filtrlab olish
        url = f"https://huggingface.co/api/models?pipeline_tag={task}&sort=downloads&direction=-1&limit=5"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                models = response.json()
                summary = f"HuggingFace Trending Models (Task: {task}):\n"
                for model in models:
                    summary += f"- {model['id']} (Downloads: {model.get('downloads', 0)})\n"
                return summary
            return "HuggingFace qidiruvida xatolik."
        except Exception as e:
            logger.error(f"[HF HUB ERROR] {e}")
            return f"HuggingFace xatosi: {e}"

    @staticmethod
    def get_repo_readme(repo_full_name):
        """GitHub repozitoriyasining README faylini olish (Bilim olish uchun)."""
        url = f"https://api.github.com/repos/{repo_full_name}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.text[:2000] # Birinchi 2000 ta belgini qaytaramiz (kontekst uchun)
            return None
        except Exception as e:
            logger.error(f"[GITHUB README ERROR] {e}")
            return None
