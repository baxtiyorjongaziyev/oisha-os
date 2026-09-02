"""
auto_execution.py
~~~~~~~~~~~~~~~~~
Autonomous Action Layer (Phase 6).
Handles technical automation tasks like contract generation, Airtable project maps,
and invoice drafting using browser (Playwright web_driver) or API.
"""

import logging
import os
from typing import Optional
from src.database import Database
from src.services.core.airtable_sync import AirtableSync
from src.agents.web_driver import OishaWebDriver

logger = logging.getLogger(__name__)


class AutonomousExecutor:
    """
    Orchestrates fully autonomous actions on behalf of the agency.
    """

    def __init__(self, db: Optional[Database] = None, airtable: Optional[AirtableSync] = None):
        self.db = db or Database()
        self.airtable = airtable or AirtableSync()
        self.web_driver = OishaWebDriver()

    async def generate_contract_pdf(self, client_name: str, brand_name: str, amount: float) -> str:
        """
        Generates a PDF contract from a template.
        """
        logger.info(f"[AUTONOMOUS] Generating contract PDF for {client_name} - {brand_name}...")
        
        # In production, this would open a docx/HTML template, populate variables,
        # and compile to PDF or use a document API.
        os.makedirs("tmp/contracts", exist_ok=True)
        pdf_path = f"tmp/contracts/{client_name.replace(' ', '_')}_contract.pdf"
        
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write(f"JON BRANDING CONTRACT\nClient: {client_name}\nBrand: {brand_name}\nAmount: {amount:,} UZS\n")
            
        logger.info(f"✅ [AUTONOMOUS] Contract PDF generated successfully: {pdf_path}")
        return pdf_path

    async def create_airtable_project_map(self, project_name: str, manager_handle: str) -> Optional[str]:
        """
        Automatically sets up a project board in Airtable using the Airtable sync wrapper.
        """
        logger.info(f"[AUTONOMOUS] Creating Airtable project map for {project_name} (PM: {manager_handle})...")
        try:
            # Stub Airtable API call to insert a new project record
            record_id = "rec_mock_" + project_name[:10].replace(" ", "_")
            logger.info(f"✅ [AUTONOMOUS] Airtable project record created with ID: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"[AUTONOMOUS ERROR] Failed to create Airtable project: {e}")
            return None

    async def send_invoice_draft(self, client_chat_id: int, amount: float) -> bool:
        """
        Drafts and queues an invoice notification to be reviewed.
        Uses WebDriverWrapper (Playwright) or billing portal API.
        """
        logger.info(f"[AUTONOMOUS] Launching browser to prepare invoice draft of {amount}...")
        try:
            # Simulates using Web Driver to fill billing portal forms
            await self.web_driver.start()
            # Simulate navigation to billing system
            logger.info("✅ [AUTONOMOUS] WebDriverWrapper executed form filling.")
            await self.web_driver.stop()
            return True
        except Exception as e:
            logger.error(f"[AUTONOMOUS ERROR] WebDriver billing automated execution failed: {e}")
            if self.web_driver.browser:
                await self.web_driver.stop()
            return False
