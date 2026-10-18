# Oisha OS • Enterprise AI & Automation Platform

Modern React & TypeScript application rewritten from the original Oisha OS enterprise architecture.

## Overview

Oisha OS unites financial automation, conversational intelligence, digital advertising infrastructure, and autonomous agent orchestration into a single high-performance console.

### Key Capabilities

1. **Hisobchi AI (Financial Accounting & Card Parser Engine)**:
   - Automated parsing for Uzcard, Humo, Visa, Payme, and Click bank SMS/receipts.
   - Intelligent extraction of amounts, vendors, card identifiers, and PnL categories.
   - Real-time PnL ledger with UZS and USD currency support.
   - Telegram Finance Group (`HISOBCHI_FINANCE_GROUP_ID`) topic dispatcher.

2. **SalesCoach AI (Speech & Call Analytics)**:
   - Accessible Call Recording Player with custom waveform visualization, scrubber, and playback speed controls.
   - Speaker diarization with timestamp synchronization.
   - Automated scoring for script adherence, empathy, and objection handling.
   - Actionable takeaways with visual compliance anchors.

3. **Marketing OS (Meta Leadgen Conversions API Console)**:
   - Privacy-first Meta CAPI dispatch with client-side SHA-256 PII hashing.
   - Durable outbox ledger with idempotency keys and exponential backoff retry.
   - JonBranding producer intake integration and status monitoring.

4. **CRM & Telegram Integration Hub**:
   - AmoCRM deal pipelines and lead synchronization.
   - Airtable two-way sync mapper.
   - Telegram userbot session lock protection (preventing Oracle VM session collisions) and quiet-hours automation.

5. **Autonomous Multi-Agent Swarm**:
   - Real-time coordination and file lock management for 9 specialized engineering subagents (Hisobchi AI, API Server, Database, God Object Parser, Integration, Security & Testing, Performance, Code Quality, and PR Steward).
   - In-app verification command execution.

6. **Pre-flight CI & Security Shield**:
   - Local validation mirroring GitHub Actions CI: Ruff F821, Bandit -ll security scanner, SKIP_LIVE Pytest suites, and secret leakage prevention.

## Tech Stack

- **Framework**: React 19 + TypeScript + Vite
- **Styling**: Tailwind CSS v4 with custom `amberline` theme tokens
- **Icons**: Lucide React
- **Accessibility**: ARIA role groups, switch roles, keyboard focus management, and screen reader-friendly transcripts conforming to the Impeccable Design Constitution.

## Development

```bash
npm install
npm run dev
```

The dev server runs on port 3000 (`http://localhost:3000`).
