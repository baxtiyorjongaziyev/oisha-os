# Oisha Sales OS Suite

Oisha ichida uchta mahsulot bitta operatsion tizimga birlashadi:

- DeepSales yo'nalishi: lead intelligence, prospecting, buyer context, lead scoring.
- Metasell yo'nalishi: call analysis, transcription, Uzbek summary, coaching, task automation.
- Reportagram yo'nalishi: scheduled reports, funnel metrics, Telegram-ready executive summaries.

Manbalar:

- https://deepsales.uz/?lang=en
- https://metasell.ai/
- https://www.reportagram.com/

## Product Mapping

| Source product | Oisha layer | Oisha modules | amoCRM output |
| --- | --- | --- | --- |
| DeepSales | Lead Intelligence | `AmoCRMLeadEnricher`, `LeadScraper`, `LeadClassifier`, `DealHygiene` | lead score, enrichment note, source tag, qualification task |
| Metasell | Conversation Intelligence | `CallAnalyzer`, `PipelineAuditor`, `SalesCoach`, `AutonomousSalesAgent` | transcript, Uzbek summary, objection tags, follow-up task |
| Reportagram | Revenue Reporting | `EnterpriseReporter`, `SalesAnalytics`, `MissionControl`, `SlaMonitor` | daily/weekly/monthly reports, SLA alerts, pipeline audit notes |

## Unified Workflow

1. New deal or phone number arrives in amoCRM.
2. Oisha normalizes the phone number, deduplicates the lead, enriches buyer context, and writes a structured note.
3. When a call recording or Telegram conversation exists, Oisha transcribes it, summarizes it in Uzbek, extracts objections and promised next steps.
4. Oisha tags the deal as `mijoz`, `jamoa`, `shaxsiy`, `oila`, or `noma'lum`.
5. For real customer conversations, Oisha creates the next task in amoCRM with owner, due date, and reasoning.
6. Scheduled reporting rolls this into daily, weekly, and monthly Telegram reports for management.

## Call Tag Policy

| Tag | Meaning | CRM action |
| --- | --- | --- |
| `mijoz` | Real customer conversation | Keep in funnel, write summary, create next sales task |
| `jamoa` | Internal team coordination | Write internal note, exclude from sales conversion metrics |
| `shaxsiy` | Personal call | Tag as noise, no sales task |
| `oila` | Family/private call | Tag as private noise, no sales task |
| `noma'lum` | Unclear or mixed conversation | Create review task only when lead is active |

## API Contract

The suite contract is available at:

```text
GET /api/oisha/product-suite
```

This endpoint is the source of truth for the combined product promise, pillars, workflows, tag policy, task rules, and runtime integrations.
