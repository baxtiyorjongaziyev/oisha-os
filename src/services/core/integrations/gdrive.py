import os
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from typing import Optional

logger = logging.getLogger(__name__)


class GoogleDriveSync:
    """
    Manages Google Drive uploads for Oisha-OS media synchronization.
    """

    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    def __init__(self, creds_file: str):
        self.creds_file = creds_file
        self.creds = service_account.Credentials.from_service_account_file(
            creds_file, scopes=self.SCOPES
        )
        self.service = build("drive", "v3", credentials=self.creds)

    def upload_file(
        self, file_path: str, folder_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Uploads a local file to Google Drive and returns the shareable link.
        """
        try:
            file_name = os.path.basename(file_path)
            file_metadata = {"name": file_name}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaFileUpload(file_path, resumable=True)
            uploaded_file = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )

            # Make readable for the user (anyone with the link - optional, depends on security)
            # self.service.permissions().create(
            #     fileId=uploaded_file.get('id'),
            #     body={'type': 'anyone', 'role': 'viewer'}
            # ).execute()

            logger.info(
                f"[GDRIVE] Uploaded {file_name} successfully: {uploaded_file.get('id')}"
            )
            return uploaded_file.get("webViewLink")

        except Exception as e:
            logger.error(f"[GDRIVE] Upload error: {e}")
            return None

    def create_folder(
        self, folder_name: str, parent_id: Optional[str] = None
    ) -> Optional[str]:
        """Creates a directory in Google Drive."""
        try:
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if parent_id:
                file_metadata["parents"] = [parent_id]

            folder = (
                self.service.files().create(body=file_metadata, fields="id").execute()
            )
            return folder.get("id")
        except Exception as e:
            logger.error(f"[GDRIVE] Error creating folder: {e}")
            return None
    
    def search_files(self, query: str) -> list:
        """
        Searches for files in Google Drive by name.
        """
        try:
            results = (
                self.service.files()
                .list(
                    q=f"name contains '{query}'",
                    fields="files(id, name, webViewLink, mimeType)",
                )
                .execute()
            )
            return results.get("files", [])
        except Exception as e:
            logger.error(f"[GDRIVE] Search error: {e}")
            return []
