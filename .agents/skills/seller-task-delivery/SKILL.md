---
name: seller-task-delivery
description: Route shared-login CRM task reminders to the verified seller through Oisha and verify delivery safely.
---

# Seller task delivery

## Scope and sources

Use for private Oisha task delivery. Never infer the seller from the shared
responsible_user_id. Use field 1559389, falling back to exact seller tags.
Field/tag conflicts block private delivery. Numeric Telegram destinations and
aliases live in task_notifier/routing.py. Usernames can change; IDs are stable.

## Operation

1. Read AGENTS.md, production status and git status. Isolate dirty work.
2. Verify the service host. Historical Contabo deployment notes can be stale.
3. Use application settings without printing credentials. Never start a userbot.
4. On the production host, preview from the application directory:
   `PYTHONPATH=. venv/bin/python scripts/prod/verify_seller_task_delivery.py`
5. With owner authorization to send tasks, add `--send`. This sends at most one
   real open due task per seller, without creating synthetic CRM records.
6. Record task ID, seller ID, Telegram message ID and persistent receipt.

## Edge cases

- A recipient may need to press Start or unblock Oisha.
- Page through every task page; a failed read must not become a fake zero.
- Delivery claims contain task ID, deadline, recipient and alert kind.
- Persistent atomic claims stop races between schedulers. Keep the claim after
  an ambiguous transport timeout; never blindly resend.
- Closed deals, completed tasks and unresolved sellers are not privately sent.
- Polling runs 10:00–18:00 Monday–Saturday. Due alerts start 15 minutes before
  deadline; overdue alerts cover the following four hours.
- New tasks are detected for 15 minutes; add webhooks route as new tasks.
  Webhook subscription setup must be verified separately.
- Historical overdue backlog is not automatically mass-sent by this flow.

## Verification

Run notifier, seller delivery and formatter tests, Bandit and Uzbek text guard.
Full preflight is separate. A failing preflight blocks PR creation/merge.
Distinguish scoped deployment, git push, merge and CI. Verify readiness and
Telegram receipts after changes. Receipt does not prove the seller read a task.
