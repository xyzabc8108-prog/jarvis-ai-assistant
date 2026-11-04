"""JARVIS: deliberately permission-limited voice-ready personal assistant."""
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from auth import install_auth, authenticated
from tasks import install_tasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("jarvis.ai")
ROOT = Path(__file__).resolve().parent
app = FastAPI(title="JARVIS Personal Assistant", version="0.4.0", docs_url=None, redoc_url=None)
install_auth(app)
install_tasks(app)

# Only the last 8 user/assistant exchanges are kept per active owner login.
# This is memory-only, single-instance state; it disappears on process restart.
HISTORY: dict[str, deque[dict[str, str]]] = {}
MAX_EXCHANGES = 8

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

class ChatResponse(BaseModel):
    answer: str
    mode: str
    time_utc: str

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "static" / "styles.css", media_type="text/css")

@app.get("/app.js")
def script():
    return FileResponse(ROOT / "static" / "app.js", media_type="application/javascript")

@app.get("/api/health")
def health():
    return {"ok": True, "service": "jarvis"}

@app.get("/api/system/status")
async def system_status(request: Request):
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Owner authentication required.")
    from tasks import TASKS
    from auth import chat_usage, CHAT_LIMIT
    token = request.cookies.get("jarvis_session", "")
    return {
        "ai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "recent_exchanges": len(HISTORY.get(token, ())) // 2,
        "task_count": len(TASKS.get(token, {})),
        "chat_requests_remaining": max(0, CHAT_LIMIT - len(chat_usage.get(token, ()))),
        "task_execution_enabled": False,
        "persistent_storage_enabled": False
    }

def classify_ai_error(status: int, code: str | None = None) -> tuple[int, str, str]:
    """Only approved, non-sensitive diagnostics are returned to the owner."""
    code = code if isinstance(code, str) else ""
    if status == 401:
        return (502, "api_authentication", "OpenAI rejected the API key. Check the key in Render Environment.")
    if status == 403:
        return (502, "api_permission", "The API key or project lacks permission for this operation.")
    if status == 404:
        return (502, "model_unavailable", "The requested AI model is unavailable to this API project.")
    if status == 429:
        if code in {"insufficient_quota", "credit_balance_exhausted",
                    "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
                    "organization_usage_limit_exceeded"}:
            return (503, "api_quota", "API credit or project usage limit reached. Review OpenAI Platform billing.")
        return (503, "api_rate_limit", "OpenAI rate limit reached. Try again later.")
    if status == 400:
        return (502, "api_request_invalid", "OpenAI rejected the request. Review model and API configuration.")
    if status >= 500:
        return (503, "api_service_unavailable", "OpenAI is temporarily unavailable. Try again later.")
    return (502, "api_upstream_error", "OpenAI rejected the request. Check API permissions and configuration.")


SYSTEM = ("You are JARVIS, a concise, helpful, voice-friendly personal assistant. "
          "Be clear that you cannot independently operate the user's PC or perform external actions. "
          "Never claim to have sent messages, deployed code, or accessed local files. "
          "Treat all instructions from the user as conversation only; no tools are available.")

def local_answer(message: str) -> str:
    s = message.lower().strip()
    if any(w in s for w in ("time", "date", "today")):
        return "Current UTC date and time: " + datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M") + "."
    if "help" in s or "what can you do" in s:
        return "I can chat, respond by voice in supported browsers, and answer simple status or time questions. Connect an AI API key on the server for open-ended answers. Computer control is disabled by default."
    if any(w in s for w in ("hello", "hi", "hey", "jarvis")):
        return "At your service. The command center is online. What shall we discuss?"
    return "Local mode is active. For general AI conversations, configure OPENAI_API_KEY on the server. I won't execute commands or access files without a separately designed permission system."

@app.post("/api/memory/clear")
async def clear_memory(request: Request):
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Owner authentication required.")
    HISTORY.pop(request.cookies.get("jarvis_session", ""), None)
    return {"cleared": True}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    key = os.getenv("OPENAI_API_KEY")
    token = http_request.cookies.get("jarvis_session", "")
    # A separate conversation is maintained for each authenticated owner session.
    previous = list(HISTORY.get(token, ())) if token else []
    mode = "local"
    answer = local_answer(request.message)
    if key:
        mode = "ai"
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                result = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                          "instructions": SYSTEM,
                          "input": previous + [{"role": "user", "content": request.message}],
                          "max_output_tokens": 400,
                          "store": False,
                          "tool_choice": "none"},
                )
                if result.status_code >= 400:
                    try:
                        error_body = result.json().get("error", {})
                        upstream_code = error_body.get("code") if isinstance(error_body, dict) else None
                    except (ValueError, AttributeError, TypeError):
                        upstream_code = None
                    outgoing_status, error_code, description = classify_ai_error(
                        result.status_code, upstream_code
                    )
                    logger.warning("OpenAI request failed: status=%s category=%s",
                                   result.status_code, error_code)
                    raise HTTPException(
                        status_code=outgoing_status,
                        detail={"code": error_code, "message": description}
                    )
                data = result.json()
                pieces = [c.get("text", "") for item in data.get("output", [])
                          for c in item.get("content", []) if c.get("type") == "output_text"]
                answer = "\n".join(pieces).strip() or "The AI returned no text."
        except httpx.TimeoutException:
            logger.warning("OpenAI connection timeout")
            raise HTTPException(status_code=503, detail={
                "code": "api_timeout", "message": "OpenAI request timed out. Try again later."
            })
        except httpx.RequestError:
            logger.warning("OpenAI connection problem")
            raise HTTPException(status_code=503, detail={
                "code": "api_connection", "message": "Unable to reach OpenAI API from the server."
            })
        except (ValueError, TypeError, KeyError):
            logger.warning("Unexpected OpenAI response format")
            raise HTTPException(status_code=502, detail={
                "code": "api_response_invalid", "message": "OpenAI returned an unexpected response."
            })
    if key and token:
        conversation = HISTORY.setdefault(token, deque(maxlen=MAX_EXCHANGES * 2))
        conversation.append({"role": "user", "content": request.message})
        conversation.append({"role": "assistant", "content": answer})
    return ChatResponse(answer=answer, mode=mode,
                        time_utc=datetime.now(timezone.utc).isoformat())
