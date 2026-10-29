# Oisha: ChatGPT plan integration assessment

Checked: 2026-10-11, Asia/Tashkent. Status: **ruxsat kutilmoqda** for the current remotely hosted Oisha service. No application approval was submitted; no live inference was attempted.

## Verified scope

Read-only source review; no production credentials, browser sessions, cookies, passwords or tokens read/copied. No client messages, provider changes, paid activation, deployment or live userbot startup. Existing dirty checkout changes preserved. Runtime configuration and production billing were not inspected.

- `src/settings.py:79-112`: Gemini models, provider API-key settings; paid fallback defaults to false. Defaults do not prove deployed values.
- `src/services/utils/free_ai_router.py`: Gemini-first default text chain with Groq, Cerebras, SambaNova, Together, OpenRouter, NVIDIA, Mistral, Hugging Face, Cloudflare and Ollama; bearer API-key authentication for hosted providers. Token caps, timeouts and provider cooldowns are not monetary caps.
- `src/services/utils/gemini_failover/engine.py` and `providers.py`: Gemini quota cooldown and separate fallback chain. This chain does not enforce `ENABLE_PAID_AI_FALLBACK` for every provider. Names/comments saying free do not prove a configured account is free.
- `src/services/call_analytics/transcriber.py:299`: OpenAI transcription fallback checks the paid flag. This is a separate API billing route.
- `src/agents/router_pkg/models_cost.py:57-58`: default daily soft/hard limits USD 3/10. Catalog prices are zero; router paths also record zero cost. These values cannot establish a reliable monetary cap across the application. This file was read for assessment only, not edited.
- `gh repo view --json visibility,url`: public repository; local `LICENSE`: MIT. This makes the OSS documentation relevant, but does not prove eligibility for the current hosted service.
- No SIWC/client registration implementation found in searched `src`, `apps`, `deploy`, `tests` Python/TypeScript/JSON sources. Existing OpenAI approval outside these sources is unknown.

## Official availability

Identity login and authorization to consume a ChatGPT plan are distinct. Plan usage is optional, limited to eligible requests/accounts; a Plus subscription alone does not register Oisha.

- [Quickstart](https://developers.openai.com/siwc/quickstart)
- [Commercial client ID](https://developers.openai.com/siwc/request-client-id): selected commercial partners; interest form/waitlist.
- [OSS plan usage](https://developers.openai.com/siwc/token-sharing-open-source): OSS/local clients have dynamic registration; paid or remotely hosted applications are directed to the interest form. Public MIT code alone does not prove approval of hosted Oisha.
- [Self-hosted VM guide](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms): documents transfer of protected SIWC credentials for an OSS installation. No such transfer was performed; it cannot be used as evidence of approval for a hosted product, nor to bypass the owner's token restrictions.
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations): streaming Responses requests, `store:false`; several fields/tools unsupported; transcription is unsupported. Existing chat-completion/STT code cannot simply receive a ChatGPT token.

## Required approved implementation

After OpenAI confirms the correct registration route for remotely hosted Oisha: use only issued Oisha registration and supported OAuth Authorization Code + PKCE/OIDC. Validate state, nonce, issuer, audience and granted scopes. Never reuse Codex's client ID or any existing ChatGPT browser credential.

UI must show account sign-in separately from optional plan usage consent, current connection/authorization state, limits, and disconnect. Declined consent leaves plan calls disabled. Revocation/expired session/401 stops calls and requires supported reauthorization; 429/limit exhaustion stops without switching to paid API. No automatic purchase, top-up or paid fallback. Disconnect invalidates local access and uses the supported revocation mechanism; verify completion. Store only credentials expressly permitted by the owner and approved flow, in a protected credential store, never chat/vault/logs.

First acceptance run: isolated internal prompt with no customer data, no Telegram/CRM destination, one request; verify `response.completed` and usage attribution. Also verify consent refusal, revoked connection, exhausted limit and disconnect before production routing.

## Test status

The requested live one-request ChatGPT Plus test is **not performed**: no confirmed Oisha registration/authorization and no owner OAuth consent. No mock is presented as real inference. A request through this Codex chat would not test Oisha's connection. Production was not touched.

## API alternative — proposal, disabled

Use a dedicated OpenAI API project/service credential with separate billing only after explicit owner approval of daily/monthly USD caps and model. Enforce a durable atomic application budget: reserve worst-case request cost before dispatch, account for input/output/tool/reasoning charges and concurrent workers, reconcile usage after completion, retain reservations on ambiguous timeout, fail closed on unavailable ledger/pricing. Bound input/output and concurrency; prohibit automatic paid fallback and top-ups. Add the project's hard spend limit as another layer; alerts alone do not stop requests, and platform limit propagation can allow small overshoot. Apply a safety margin. Do not claim prepaid balance or alerts alone provide an exact cap.

Source: [OpenAI spend limits](https://developers.openai.com/api/docs/guides/spend-limits). No key created, billing enabled or numeric budget approved.

## One next owner step

Submit the [official interest form](https://openai.com/form/sign-in-with-chatgpt-interest/) for Oisha's remotely hosted agency operations service and obtain OpenAI confirmation/client registration for identity **and** ChatGPT plan usage. Submission is pending, not completed. Suggested description: public MIT Oisha OS; remotely hosted Telegram/AmoCRM agency operations; user-authorized text inference; separate identity/plan consent, per-user limits, revocation, and no browser-session credential reuse. Customer-facing/shared usage eligibility must be confirmed by OpenAI.
