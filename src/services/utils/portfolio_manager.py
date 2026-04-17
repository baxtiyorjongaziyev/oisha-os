import logging
from typing import Dict, Any, Optional
from src.services.core.airtable_sync import AirtableSync

logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Tayyor loyihalarni portfolioga tayyorlash va joylash servisi.
    """
    def __init__(self, airtable: AirtableSync):
        self.airtable = airtable
        self.PORTFOLIO_TABLE = "Portfolio" # Placeholder for Airtable Portfolio table

    def format_project_for_portfolio(self, project_data: Dict[str, Any], description: str, image_url: str):
        """
        Loyiha ma'lumotlarini portfolio uchun formatlash va Airtable'ga yozish.
        """
        fields = {
            "Project Name": project_data.get("Project Name"),
            "Description": description,
            "Image": [{"url": image_url}],
            "Date": project_data.get("Created At"),
            "Client": project_data.get("Client")
        }
        
        # Portfolio jadvaliga yozish
        original_table = self.airtable.table_name
        self.airtable.table_name = self.PORTFOLIO_TABLE
        self.airtable.endpoint = f"https://api.airtable.com/v0/{self.airtable.base_id}/{self.airtable.table_name}"
        
        try:
            result = self.airtable.create_record(fields)
            return result is not None
        finally:
            self.airtable.table_name = original_table
            self.airtable.endpoint = f"https://api.airtable.com/v0/{self.airtable.base_id}/{self.airtable.table_name}"

    def ask_owner_for_details(self, project_name: str):
        """
        Owner-ga (Baxtiyor aka) xabar yuborish uchun matn tayyorlash.
        """
        return (
            f"✨ **Yangi Portfolio Imkoniyati!** 👸🛡️\n\n"
            f"Tabriklaymiz, '{project_name}' loyihasi muvaffaqiyatli yakunlandi! ✅\n\n"
            f"Ushbu ishni portfolioga qo'shamizmi? Agar ha bo'lsa, quyidagilarni yuboring:\n"
            f"1. **Rasm havolasi** (Direct Image Link)\n"
            f"2. **Qisqa matn** (Description)\n\n"
            f"Oisha sizning muvaffaqiyatingizni dunyoga ko'rsatishga tayyor! 👸📈"
        )
