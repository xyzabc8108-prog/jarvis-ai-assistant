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

## Phase 3: Optional AI activation

AI mode is off until the owner adds `OPENAI_API_KEY` to the Render service environment. Obtain a key directly from https://platform.openai.com/api-keys and **never paste it into chat, GitHub or the frontend**. In Render: JARVIS service → Environment → Add Environment Variable → `OPENAI_API_KEY` → Save and deploy. Optionally set `OPENAI_MODEL` to an API model enabled for the account. The model call sends no tools, requests `store=false`, and caps generated output at 400 tokens. It does not supply the assistant with web browsing, local shell, files, or scheduled execution.

Protect your OpenAI API project with spending/budget alerts, and monitor usage. JARVIS has a basic **30 messages per session per hour** limit, but this is not a guaranteed billing cap. If the owner password has appeared in chat, rotate `JARVIS_OWNER_PASSWORD` directly in Render's Environment settings and do not post the replacement.

Deployment updates are triggered automatically from `main`; confirm their successful completion in the Render dashboard before relying on new features.

## Phase 4: Short-term conversational memory

- The last eight user/assistant exchanges are passed back to the AI for follow-up context.
- This history exists only in the running process, separated by authenticated login session, and **is not persisted to a database**.
- Use **CLEAR MEMORY** in the interface to forget the current session's context. Logging out also discards it.
- Restarting the Render instance loses this context; the server can restart on the free plan.
- Only authenticated requests can clear or use conversational memory. Local fallback answers remain rule-based and do not use conversation history.
- This is a prototype, not a durable multi-device memory service. Do not submit sensitive personal information.

## Phase 5: Task planner (non-executing)

Once logged in, add a task in the **Task Planner** section. New tasks are `pending`; you may explicitly **approve**, **complete** or **cancel** them. Approval does not run commands or schedule anything. The API endpoints are `GET /api/tasks`, `POST /api/tasks`, `POST /api/tasks/{id}/action`, and `DELETE /api/tasks`.

This MVP keeps at most 50 tasks per authenticated session in server RAM, with a per-session status history only. They disappear on logout, instance restart, or replacement. Due dates are accepted by the API as timezone-aware timestamps but **do not trigger reminders**. This is deliberately not an autonomous job runner. Reliable background scheduling requires durable storage, independent workers, user-visible audit logs, and permissions for each external action. No external integrations are enabled through the task planner.
