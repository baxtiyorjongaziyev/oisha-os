import os
from oisha_settings import settings

BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
GEMINI_API_KEY = settings.GEMINI_API_KEY.get_secret_value()
API_ID = settings.API_ID
API_HASH = settings.API_HASH

AMOCRM_SUBDOMAIN = settings.AMOCRM_SUBDOMAIN
AMOCRM_CLIENT_ID = settings.AMOCRM_CLIENT_ID
AMOCRM_CLIENT_SECRET = settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None
AMOCRM_REDIRECT_URL = settings.AMOCRM_REDIRECT_URI

AIRTABLE_API_KEY = settings.AIRTABLE_API_KEY.get_secret_value() if settings.AIRTABLE_API_KEY else None
AIRTABLE_BASE_ID = settings.AIRTABLE_BASE_ID

CRM_GROUP_ID = settings.CRM_GROUP_ID
CRM_TOPIC_ID = settings.CRM_TOPIC_ID
