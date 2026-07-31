# Oisha-OS Architecture

## Overview

Oisha-OS is an autonomous "Surgical COO" (Chief Operating Officer) system designed for agency management. It orchestrates sales, support, and internal operations using high-precision AI agents.

## Core Components

### 🤖 Agents (src/agents/)

- **BaseAgent**: abstract foundation for all agents.
- **SalesAgent**: Handles lead negotiation, CRM updates, and scheduling.
- **SupportAgent**: Provides grounded responses using an internal knowledge base.
- **NegotiationEngine**: Analysis engine that assesses chat context to generate instructions.

### 💼 Integrations (src/services/)

- **AmoCRM**: Primary CRM for lead management.
- **Airtable/Google Sheets**: Secondary storage and reporting.
- **Telegram (Telethon/aiogram)**: Communication interface.

### 🧠 AI Layer

- **Google Gemini 2.5 Flash / 2.0 Flash**: Core reasoning (logic, missions).
- **Google Gemini 1.5 Pro**: Complex coding tasks.
- **Groq/DeepSeek**: Fallback or specialized tasks.
- **Hisobchi AI**: Handles financial tasks, approvals, and metrics.
- **Free-AI router**: Routes internal AI requests without cost overhead.
- **MCP gateway**: Standardized context protocol for AI agents and services.

## Data Flow

1. **Trigger**: Incoming Telegram message or CRM webhook.
2. **Analysis**: `NegotiationEngine` assesses lead intent and stage.
3. **Execution**: `SalesAgent` plans CRM actions (tasks, status changes).
4. **Action**: `Executor` performs changes in amoCRM/Airtable.
5. **Feedback**: System logs actions and notifies the team via Telegram.

## Security & Reliability

- **Secrets**: Managed via Cloud Secret Manager (Production) or .env (Development).
- **Testing**: Pytest unit tests for agent logic.
- **CI/CD**: Primary deployment to Oracle VM via systemd (`oisha-os` service). Google Cloud Run is kept as a legacy fallback.
