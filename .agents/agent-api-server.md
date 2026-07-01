# Agent: API Server Engineer

## Mission
REST API improvements, endpoints, auth, rate limiting.

## Files you own
- `src/api_server.py` — FastAPI/Flask server
- `src/api/` — API routes

## Current State
- Health check endpoint
- User lookup endpoint
- Chat history endpoint
- Send message endpoint

## What to Build
1. **Rate limiting** — per-user, per-endpoint
2. **Auth middleware** — JWT validation
3. **Input validation** — Pydantic models
4. **Error handling** — structured responses
5. **API docs** — OpenAPI/Swagger

## Rules
1. **Pydantic models** — request/response validation
2. **Status codes** — proper HTTP semantics
3. **CORS** — configured for production
4. **Logging** — request/response logging

## Verify
```powershell
python -m pytest tests/test_api_server_security.py -v
```
