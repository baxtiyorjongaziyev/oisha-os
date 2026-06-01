# AmoCRM Call Audit

Oisha now owns the AmoCRM call-audit workflow. It transcribes AmoCRM call
recordings, writes an Uzbek summary to the deal note, and tags the deal as one
of:

- `Mijoz`
- `Jamoa`
- `Shaxsiy`
- `Oila`
- `Boshqa`

## Recommended Production Run

PowerShell:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
python src/run_call_analysis_pipeline.py `
  --limit 500 `
  --write `
  --include-transcript `
  --one-analysis-per-lead `
  --max-calls-per-lead 1 `
  --min-call-duration-seconds 8 `
  --report-path "data/reports/amocrm-call-audit-$stamp.jsonl"
```

This mode is intentionally conservative:

- It skips deals that already have an `AI_CALL_ANALYSIS` note.
- It analyzes only the newest usable call per deal when `--max-calls-per-lead 1` is set.
- It skips very short calls when `--min-call-duration-seconds` is set and AmoCRM provides call duration.
- It writes a JSONL report so the run can be audited after completion.

## Safe Dry Run

Use this before a large write run:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
python src/run_call_analysis_pipeline.py `
  --limit 20 `
  --dry-run `
  --one-analysis-per-lead `
  --max-calls-per-lead 1 `
  --min-call-duration-seconds 8 `
  --report-path "data/reports/amocrm-call-audit-dry-$stamp.jsonl"
```

## Notes

- Oisha writes `[AI_CALL_ANALYSIS]` into AmoCRM notes so repeat runs can safely resume.
- The pipeline stores processed call IDs in the local `call_analyses` table.
- STT uses Gemini first and can fall back to OpenAI when `OPENAI_API_KEY` is configured.
- The old `jonbranding-web/scripts/amocrm-call-audit.mjs` script has been removed from the web repo because this is CRM automation, not website code.
