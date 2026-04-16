import json
import os

import requests
from google.api_core.exceptions import AlreadyExists
from google.cloud import secretmanager


def _project_id() -> str:
    project_id = (
        os.environ.get("PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or ""
    )
    if project_id:
        return project_id

    try:
        response = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        if response.status_code == 200:
            return response.text.strip()
    except requests.RequestException:
        pass

    return ""


def _store_token_secret(token_data: dict) -> None:
    project_id = _project_id()
    secret_id = os.environ.get("AMOCRM_TOKEN_SECRET_ID", "amocrm-token")
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not available")

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    secret_name = f"{parent}/secrets/{secret_id}"

    try:
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
    except AlreadyExists:
        pass

    payload = json.dumps(token_data).encode("utf-8")
    client.add_secret_version(
        request={
            "parent": secret_name,
            "payload": {"data": payload},
        }
    )


def amocrmOAuthCallback(request):
    code = request.args.get("code")
    if not code:
        return (
            "AmoCRM OAuth callback tayyor. Endi authorize link orqali qaytgan code shu yerga tushadi.",
            200,
        )

    subdomain = os.environ["AMOCRM_SUBDOMAIN"]
    client_id = os.environ["AMOCRM_CLIENT_ID"]
    client_secret = os.environ["AMOCRM_CLIENT_SECRET"]
    redirect_url = os.environ["AMOCRM_REDIRECT_URL"]

    response = requests.post(
        f"https://{subdomain}.amocrm.ru/oauth2/access_token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_url,
        },
        timeout=30,
    )

    if response.status_code != 200:
        return (
            f"AmoCRM token exchange failed: {response.status_code} {response.text[:300]}",
            500,
        )

    token_data = response.json()
    _store_token_secret(token_data)
    return (
        "AmoCRM qayta avtorizatsiya muvaffaqiyatli saqlandi. Endi tokenni serverga ulash mumkin.",
        200,
    )
