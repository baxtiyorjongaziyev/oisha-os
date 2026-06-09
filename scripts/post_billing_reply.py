"""Post waiver comments to Google Cloud billing support cases."""
import json
import sys
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA_FILE = os.environ.get("SA_FILE")
if not SA_FILE or not os.path.exists(SA_FILE):
    print("FAIL: SA_FILE not set or file not found")
    sys.exit(1)

CASES = [
    {
        "billing_account": "01ED9C-CD8E9F-7C1964",
        "case_id": "71989960",
        "amount": "$79.16",
        "body": (
            "Hello,\n\n"
            "Thank you for the $294.00 credit already applied — I truly appreciate it.\n\n"
            "I am writing to respectfully request that the remaining $79.16 balance also be waived. "
            "Here is the key technical context:\n\n"
            "1. The Cloud Run service (oisha-master-bot, europe-west3) was deployed with "
            "CLOUD_RUN_CONTROL_PLANE_ONLY=True, an application-level flag that caused all "
            "initialization code to be skipped. No Telegram client started, no database "
            "connections opened, no requests processed. The container was allocated but "
            "completely idle at the application level.\n\n"
            "2. ENABLE_CLOUD_USERBOT=False was simultaneously set, explicitly disabling the "
            "only feature Cloud Run was intended to run.\n\n"
            "3. All actual production work ran on Oracle Cloud Free Tier. Cloud Run was a "
            "legacy deployment that was never decommissioned — a configuration oversight.\n\n"
            "4. The service has been permanently deleted. The deployment workflow and all "
            "GCP dependencies have been removed from the codebase. This cannot recur.\n\n"
            "5. Both payment attempts were declined — no funds were collected.\n\n"
            "Given that the service produced zero output (dual kill-switches were active), "
            "no funds were collected, and the service is permanently deleted, I respectfully "
            "request a full waiver of the remaining $79.16 as a one-time good faith adjustment.\n\n"
            "Thank you for your time and understanding.\n"
            "Baxtiyorjon Gaziyev\n"
            "baxtiyorjongaziyev@gmail.com"
        ),
    },
    {
        "billing_account": "010703-F34248-01FE50",
        "case_id": "71874253",
        "amount": "$58.61",
        "body": (
            "Hello,\n\n"
            "Following up on this billing adjustment request for $58.61.\n\n"
            "Additional technical evidence:\n\n"
            "1. The Cloud Run service was configured with CLOUD_RUN_CONTROL_PLANE_ONLY=True. "
            "This application flag caused all initialization to be skipped — the container "
            "ran but executed zero business logic. No requests were processed.\n\n"
            "2. ENABLE_CLOUD_USERBOT=False was also set, disabling the only intended feature.\n\n"
            "3. All production workload ran on Oracle Cloud Free Tier. Cloud Run was a "
            "legacy deployment never decommissioned — a configuration oversight, not intentional usage.\n\n"
            "4. The Cloud Run service has been permanently deleted. The deployment pipeline "
            "has been removed from our CI/CD. This cannot recur.\n\n"
            "5. No funds were collected — all charge attempts were declined.\n\n"
            "I respectfully request a full waiver of the $58.61 balance as a one-time adjustment.\n\n"
            "Thank you.\n"
            "Baxtiyorjon Gaziyev\n"
            "baxtiyorjongaziyev@gmail.com"
        ),
    },
]

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/cloudsupport",
]

creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
with open(SA_FILE) as f:
    sa_info = json.load(f)
sa_project = sa_info.get("project_id", "")
print(f"Service account: {creds.service_account_email}")
print(f"Project: {sa_project}")

svc = build("cloudsupport", "v2", credentials=creds)

# Discover accessible cases under the SA's project
print("\n--- Listing project-level cases ---")
project_cases = {}
try:
    resp = svc.cases().list(parent=f"projects/{sa_project}").execute()
    for c in resp.get("cases", []):
        name = c.get("name", "")
        print(f"  {name}  state={c.get('state')}  title={c.get('displayName', c.get('title', ''))[:60]}")
        case_id = name.split("/")[-1]
        project_cases[case_id] = name
except HttpError as e:
    print(f"  List project cases failed ({e.resp.status}): {e}")

print()

success_count = 0
for case in CASES:
    print(f"Case {case['case_id']} ({case['amount']}):")

    # Build candidate resource names
    candidates = [
        f"billingAccounts/{case['billing_account']}/cases/{case['case_id']}",
    ]
    # If found in project listing, prepend project path
    if case["case_id"] in project_cases:
        candidates.insert(0, project_cases[case["case_id"]])
    else:
        candidates.append(f"projects/{sa_project}/cases/{case['case_id']}")

    posted = False
    for resource in candidates:
        try:
            result = svc.cases().comments().create(
                parent=resource, body={"body": case["body"]}
            ).execute()
            print(f"  SUCCESS via {resource}: {result.get('name', 'comment posted')}")
            posted = True
            success_count += 1
            break
        except HttpError as e:
            print(f"  {resource} → {e.resp.status}: {e.reason}")

    if not posted:
        print(f"  FAIL: No resource path worked for case {case['case_id']}")

print(f"\nResult: {success_count}/{len(CASES)} comments posted.")
if success_count < len(CASES):
    sys.exit(1)
