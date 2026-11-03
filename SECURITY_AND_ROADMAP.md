# JARVIS — Security & Operations Notes

## Current trust boundary

JARVIS is a **single-owner, conversational web prototype**. The only external request initiated by the application is an optional OpenAI Responses API call when a server-side API key is configured. No terminal commands, email sends, browser automation, filesystem access, deployments, financial orders, or device operations are exposed as assistant tools.

## Live setup

- GitHub: https://github.com/xyzabc8108-prog/jarvis-ai-assistant
- Render: https://jarvis-ai-assistant-b0jt.onrender.com
- Backend: FastAPI, Uvicorn, single process
- Deployment: Render free plan, automatic deployments from main
- Owner login: JARVIS_OWNER_PASSWORD secret in Render environment
- Optional AI: OPENAI_API_KEY secret in Render environment
- Chat limit: 30 requests/hour **per login session**, not a monetary spending cap
- Max AI output: 400 tokens
- AI requests: store=false, tool_choice=none
- Browser voice input may depend on browser speech services and their privacy terms

## Test and monitoring

- GitHub Actions CI: Python compile + pytest on every push and pull request
- Render dashboard and logs: verify live status after pushes
- Unauthenticated health endpoint returns only a minimal OK state
- Authenticated /api/system/status reports AI configured flag and resource counters, not secrets

## Known limitations — do not overstate

- Owner sessions, chat memory, tasks and rate-limit counters live **in RAM** and disappear after process restart or replacement
- Login attempts are limited per process, not across instances and not a production-strength identity provider
- Tasks are planning-only; approval never invokes external operations
- Due timestamps are display metadata, not an unattended schedule
- Browser voice support varies; microphone audio may be processed by the user's browser provider
- There is no persistent audit trail, durable task queue, scheduled worker or background agent
- API model credentials are billed separately and may incur expenses

## Requirements before unattended actions

1. Create a dedicated JARVIS database/project (do not reuse Indian Market Lab production data). Get the owner's organization choice and confirm any nonzero cost before provisioning.
2. Implement migrations with owner isolation, row-level security and reproducible rollback.
3. Add a persistent, idempotent queue with action-type allowlist, retries, execution deadlines and audited state transitions.
4. Require explicit owner consent for any external side effect, plus an emergency off switch.
5. Use a separate scheduler/worker and test recovery from process restart and duplicate delivery.
6. Require per-action scopes for Gmail, Calendar, GitHub, local Windows or other connected apps. No unrestricted shell access.
7. Add observability, alerting, key rotation and identity-provider-based authentication.

## Owner actions

- **Rotate owner password** directly in Render if it has ever been displayed in chat.
- Configure API spend limits and budget notifications in OpenAI billing before enabling model usage.
- Review GitHub Actions results and Render deployment after every change.
- Export temporary tasks before logging out or whenever you need a manual backup.
- Do not commit API keys, access tokens, passwords or private data to this public repository.

## Supported project roadmap

Phase 6 (current): CI, safety headers, diagnostics, owner controls, task due timestamps, manual export.

Phase 7 (blocked on separately approved storage): persistent task history, migrations, auth hardening.

Phase 8 (blocked on scheduler and permissions): bounded automation, worker status, reminder delivery, audit log.

Phase 9 (blocked on local user setup): voice-controlled Windows desktop companion with explicit permissions and emergency stop.
