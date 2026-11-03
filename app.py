"""JARVIS: deliberately permission-limited voice-ready personal assistant."""
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from auth import install_auth
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="JARVIS Personal Assistant", version="0.2.0", docs_url=None, redoc_url=None)
install_auth(app)

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
    return {"ok": True, "service": "jarvis", "ai_configured": bool(os.getenv("OPENAI_API_KEY"))}

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

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    key = os.getenv("OPENAI_API_KEY")
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
                          "input": request.message,
                          "max_output_tokens": 400},
                )
                result.raise_for_status()
                data = result.json()
                pieces = [c.get("text", "") for item in data.get("output", [])
                          for c in item.get("content", []) if c.get("type") == "output_text"]
                answer = "\n".join(pieces).strip() or "The AI returned no text."
        except (httpx.HTTPError, ValueError):
            raise HTTPException(status_code=503, detail="AI service unavailable. Please try again.")
    return ChatResponse(answer=answer, mode=mode,
                        time_utc=datetime.now(timezone.utc).isoformat())
