#!/usr/bin/env python3
"""Locally authorize the 5 TB Google Drive owner account (run on your PC).

Never commit the generated OAuth JSON; securely copy it to the Oisha server.
Requires a Google Cloud OAuth Desktop client JSON with Drive API enabled.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-secrets", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        parser.error("Refusing to overwrite existing OAuth token file")
    flow = InstalledAppFlow.from_client_secrets_file(
        args.client_secrets, scopes=SCOPES
    )
    creds = flow.run_local_server(port=0, open_browser=True)
    if not creds.refresh_token:
        raise RuntimeError("Google did not issue offline refresh token")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(creds.to_json())
    print(f"OAuth token written to {output} with private file permissions")


if __name__ == "__main__":
    main()
