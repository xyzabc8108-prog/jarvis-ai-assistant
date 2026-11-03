# J.A.R.V.I.S. — Personal AI Assistant

A voice-ready command center with **owner-only access**. AI conversation is optional, and OS control, shell commands, filesystem operations, email sending and other external actions are intentionally unavailable.

## Live deployment

https://jarvis-ai-assistant-b0jt.onrender.com

## Run locally

Requires Python 3.11+.

```bash
python -m pip install -r requirements.txt
export JARVIS_OWNER_PASSWORD='replace-with-a-long-random-secret'
export JARVIS_LOCAL_DEV=1
uvicorn app:app --reload
```

Open http://127.0.0.1:8000 and use the owner password. On Windows PowerShell use `$env:JARVIS_OWNER_PASSWORD = '...'` and `$env:JARVIS_LOCAL_DEV = '1'` instead of export.

## Security

- Configure `JARVIS_OWNER_PASSWORD` as a **Render secret environment variable**. Never put it in git.
- Secure HttpOnly SameSite cookies, 12-hour in-memory session expiration, and basic per-process login throttling.
- Unauthenticated visitors cannot use `POST /api/chat`.
- Public site serves the landing UI and health check; private conversation requires login.
- If you enable `OPENAI_API_KEY`, **usage can incur API charges**. Do not enable AI on a publicly accessible service until authentication is validated.
- The basic single-instance login limiter is not suitable for high-risk or multi-instance production use. Future hardening should add persistent rate limiting, account recovery and an identity provider.
- `JARVIS_LOCAL_DEV=1` disables the secure-cookie requirement and must **never** be set in hosted production.

## Tests

```bash
python -m pytest -q
```

## Current capabilities

- Typed chat and speech recognition/speech synthesis where supported in the browser
- Owner authentication
- Optional server-side OpenAI Responses API integration (API key required)
- No PC control, scheduled autonomous execution or third-party account actions

## Deployment

Render Python service, free plan, Singapore region, auto-deploy from `main`. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
