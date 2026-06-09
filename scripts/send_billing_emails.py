"""Send waiver reply emails to Google Cloud Support cases via Gmail SMTP."""
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER = "baxtiyorjongaziyev@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

if not GMAIL_APP_PASSWORD:
    print("FAIL: GMAIL_APP_PASSWORD not set")
    sys.exit(1)

EMAILS = [
    {
        "to": "cloudsupport@google.com",
        "subject": "Re: Google Cloud Support 71874253 — answers to your questions",
        "body": (
            "Hello Jeaden,\n\n"
            "Thank you for your response. Please find the requested details below:\n\n"
            "1. Detailed explanation of how the error occurred:\n\n"
            "The Cloud Run service (billing account 010703-F34248-01FE50) was a legacy "
            "deployment left running after our production workload was migrated entirely "
            "to Oracle Cloud Free Tier. The service had two application-level flags set:\n"
            "- CLOUD_RUN_CONTROL_PLANE_ONLY=True — caused the service to skip all "
            "initialization on startup. No Telegram client, database connections, or "
            "request handlers were ever started.\n"
            "- ENABLE_CLOUD_USERBOT=False — explicitly disabled the only intended feature "
            "of the service.\n\n"
            "The container was allocated and running at the infrastructure level, but "
            "executed zero business logic. The error was a configuration oversight: the "
            "service was not decommissioned when production moved to Oracle Cloud, and "
            "these kill-switches masked the fact that it was still accruing charges.\n\n"
            "2. Steps taken to address the issue:\n\n"
            "- Permanently deleted the Cloud Run service from GCP Console\n"
            "- Removed all associated container images from Google Container Registry\n"
            "- Deleted the GitHub Actions deployment pipeline that previously deployed "
            "to Cloud Run\n"
            "- Removed all Cloud Run environment variables and service configuration "
            "from the codebase\n"
            "- Verified no remaining Cloud Run services exist on this billing account\n\n"
            "3. How the issue was initially identified:\n\n"
            "While reviewing infrastructure costs, I noticed the Cloud Run service was "
            "still active despite not being used in production for an extended period. "
            "Cross-referencing the service configuration confirmed both kill-switches "
            "were active, meaning the service had been idle at the application level "
            "throughout the entire billing period.\n\n"
            "4. Time frame during which the issue occurred and when it was resolved:\n\n"
            "The charges accrued prior to early June 2026. The issue was identified and "
            "fully resolved in the first week of June 2026 when the Cloud Run service was "
            "permanently deleted and all deployment pipelines were removed. The service "
            "no longer exists and cannot generate future charges.\n\n"
            "5. Preventive measures implemented:\n\n"
            "- Enabled billing budget alerts in Google Cloud Console\n"
            "- Performed a full audit of all remaining GCP resources\n"
            "- Updated infrastructure policy to require explicit decommissioning of "
            "cloud services as part of any future migration\n"
            "- The CI/CD pipeline no longer contains any Cloud Run deployment steps\n\n"
            "The charges resulted from an idle service with zero output — no requests "
            "were processed, no business value was generated, and Google has not collected "
            "any funds (both payment attempts were declined).\n\n"
            "I respectfully request that the $58.61 adjustment be approved.\n\n"
            "Thank you for your time and consideration.\n\n"
            "Best regards,\n"
            "Baxtiyorjon Gaziyev\n"
            "baxtiyorjongaziyev@gmail.com\n"
            "Case #71874253 | Billing account: 010703-F34248-01FE50\n\n"
            "ref:_00Df423Flu._500Kfu5xQt:ref"
        ),
    },
    {
        "to": "cloudsupport@google.com",
        "subject": "Re: Google Cloud Support 71989960 — urgent follow-up, charge declined today ($79.16)",
        "body": (
            "Hello Madhu / Google Cloud Billing Support,\n\n"
            "I am following up on my previous reply (sent June 8, 2026) requesting a "
            "waiver of the remaining $79.16 balance on billing account "
            "01ED9C-CD8E9F-7C1964.\n\n"
            "I am writing with urgency: today, June 9, 2026 at 21:44 (Tashkent time), "
            "I received a bank notification that Google attempted to charge $79.16 to "
            "my card (*2235), which was declined due to insufficient funds. This confirms "
            "the invoice is still active and Google is attempting to collect the balance.\n\n"
            "As outlined in my previous message, the full technical context supports a waiver:\n\n"
            "- The Cloud Run service had dual application-level kill-switches active "
            "(CLOUD_RUN_CONTROL_PLANE_ONLY=True and ENABLE_CLOUD_USERBOT=False) — "
            "zero business logic executed during the entire billing period\n"
            "- The service has been permanently deleted — no future charges are possible\n"
            "- No funds have been collected — both previous payment attempts and "
            "today's attempt were all declined\n"
            "- The $294.00 credit already acknowledged these charges were unintended\n\n"
            "I understand a waiver is a courtesy, and I am deeply grateful for the "
            "$294.00 credit already applied. The same circumstances that justified the "
            "initial credit apply equally to the remaining $79.16. I respectfully request "
            "a full waiver of this balance, bringing the account to $0.\n\n"
            "Given that Google is actively attempting to collect this amount, I would "
            "greatly appreciate an expedited review.\n\n"
            "Case reference: #71989960\n"
            "Billing account: 01ED9C-CD8E9F-7C1964\n\n"
            "Thank you for your prompt attention.\n\n"
            "Best regards,\n"
            "Baxtiyorjon Gaziyev\n"
            "baxtiyorjongaziyev@gmail.com\n\n"
            "ref:_00Df423Flu._500KfuFfyR:ref"
        ),
    },
]


def send_email(to: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())


success_count = 0
for email in EMAILS:
    try:
        send_email(email["to"], email["subject"], email["body"])
        print(f"SENT: {email['subject'][:60]}")
        success_count += 1
    except Exception as e:
        print(f"FAIL: {email['subject'][:50]} → {e}")

print(f"\nResult: {success_count}/{len(EMAILS)} emails sent.")
if success_count < len(EMAILS):
    sys.exit(1)
