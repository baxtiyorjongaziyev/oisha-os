"""Post waiver comments to Google Cloud billing support cases."""
import json
import sys
import os
import time

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Installing google-api-python-client...")
    os.system("/home/ubuntu/oisha-os/venv/bin/pip install -q google-api-python-client google-auth")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

SA_FILE = os.environ.get("SA_FILE", None)
ADC_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)

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
        )
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
        )
    }
]

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/cloudsupport",
]

sa_project = ""
creds = None

if SA_FILE and os.path.exists(SA_FILE):
    try:
        creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
        with open(SA_FILE) as f:
            sa_info = json.load(f)
        sa_project = sa_info.get("project_id", "")
        print(f"Service account: {creds.service_account_email}")
    except Exception as e:
        print(f"FAIL: Cannot load service account: {e}")
        sys.exit(1)
elif ADC_FILE and os.path.exists(ADC_FILE):
    try:
        import google.auth
        import google.auth.transport.requests
        creds, project = google.auth.default(scopes=SCOPES)
        sa_project = project or ""
        print(f"Using ADC credentials, project={sa_project}")
        # Try to enable Cloud Support API with user credentials
        try:
            if sa_project:
                su = build("serviceusage", "v1", credentials=creds)
                result = su.services().enable(
                    name=f"projects/{sa_project}/services/cloudsupport.googleapis.com"
                ).execute()
                print(f"Cloud Support API enable: {result.get('name', result.get('done', 'ok'))}")
                time.sleep(10)
        except Exception as e2:
            print(f"Note: ADC enable attempt: {e2}")
    except Exception as e:
        print(f"FAIL: Cannot load ADC credentials: {e}")
        sys.exit(1)
else:
    print("FAIL: No credentials available (SA_FILE and GOOGLE_APPLICATION_CREDENTIALS both missing)")
    sys.exit(1)

# Discover projects linked to the billing accounts that may have Cloud Support API enabled.
candidate_quota_projects = [sa_project] if sa_project else []
try:
    billing_svc = build("cloudbilling", "v1", credentials=creds)
    for case in CASES:
        ba = f"billingAccounts/{case['billing_account']}"
        resp = billing_svc.billingAccounts().projects().list(name=ba).execute()
        for p in resp.get("projectBillingInfo", []):
            proj_id = p.get("projectId", "")
            if proj_id and proj_id not in candidate_quota_projects:
                candidate_quota_projects.append(proj_id)
    print(f"Candidate quota projects: {candidate_quota_projects}")
except Exception as e:
    print(f"Note: billing projects lookup: {e}")

def try_post_comment(case, quota_project):
    c = creds.with_quota_project(quota_project) if quota_project else creds
    svc = build("cloudsupport", "v2", credentials=c)
    name = f"billingAccounts/{case['billing_account']}/cases/{case['case_id']}"
    result = svc.cases().comments().create(
        parent=name, body={"body": case["body"]}
    ).execute()
    return result

success_count = 0
for case in CASES:
    print(f"\nPosting to case {case['case_id']} ({case['amount']})...")
    posted = False
    for qp in candidate_quota_projects:
        try:
            result = try_post_comment(case, qp)
            print(f"SUCCESS via quota_project={qp}: {result.get('name', 'comment posted')}")
            posted = True
            success_count += 1
            break
        except HttpError as e:
            if e.resp.status == 403 and "SERVICE_DISABLED" in str(e):
                print(f"  quota_project={qp}: API disabled, trying next...")
            else:
                print(f"  quota_project={qp}: {e}")
                break
        except Exception as e:
            print(f"  quota_project={qp}: {e}")
            break
    if not posted:
        print(f"FAIL: Could not post to case {case['case_id']} with any quota project")

print(f"\nResult: {success_count}/{len(CASES)} comments posted.")
if success_count < len(CASES):
    sys.exit(1)
