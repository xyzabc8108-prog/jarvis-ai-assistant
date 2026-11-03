"""Owner-only authentication for JARVIS. Single process MVP; sessions reset on restart."""
import os
import secrets
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth")
sessions: dict[str, float] = {}
attempts: dict[str, deque[float]] = defaultdict(deque)
chat_usage: dict[str, deque[float]] = defaultdict(deque)
CHAT_WINDOW = 60 * 60
CHAT_LIMIT = 30
SESSION_SECONDS = 12 * 60 * 60
RATE_WINDOW = 10 * 60
RATE_LIMIT = 5

class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)

def authenticated(request: Request) -> bool:
    token = request.cookies.get("jarvis_session", "")
    expires = sessions.get(token, 0) if token else 0
    if not expires or expires <= time.time():
        if token:
            sessions.pop(token, None)
        return False
    return True

@router.get("/status")
async def status(request: Request):
    return {"authenticated": authenticated(request), "login_required": True}

@router.post("/login")
async def login(body: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    q = attempts[ip]
    while q and q[0] < now - RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Too many attempts. Try again later."})
    expected = os.getenv("JARVIS_OWNER_PASSWORD", "")
    if not expected:
        return JSONResponse(status_code=503, content={"detail": "Owner login is not configured."})
    if not secrets.compare_digest(body.password.encode(), expected.encode()):
        q.append(now)
        return JSONResponse(status_code=401, content={"detail": "Incorrect password."})
    q.clear()
    token = secrets.token_urlsafe(40)
    sessions[token] = now + SESSION_SECONDS
    secure = os.getenv("JARVIS_LOCAL_DEV") != "1"
    response = JSONResponse({"authenticated": True})
    response.set_cookie("jarvis_session", token, max_age=SESSION_SECONDS, httponly=True, secure=secure, samesite="strict", path="/")
    return response

@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get("jarvis_session", "")
    sessions.pop(token, None)
    chat_usage.pop(token, None)
    from app import HISTORY
    HISTORY.pop(token, None)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie("jarvis_session", path="/", secure=os.getenv("JARVIS_LOCAL_DEV") != "1", samesite="strict", httponly=True)
    return response

def install_auth(app):
    app.include_router(router)

    @app.middleware("http")
    async def protect(request: Request, call_next):
        if request.url.path == "/api/chat":
            if not authenticated(request):
                return JSONResponse(status_code=401, content={"detail": "Owner authentication required."})
            if request.method == "POST":
                token = request.cookies.get("jarvis_session", "")
                now = time.time()
                q = chat_usage[token]
                while q and q[0] < now - CHAT_WINDOW:
                    q.popleft()
                if len(q) >= CHAT_LIMIT:
                    return JSONResponse(status_code=429, content={"detail": "Hourly request limit reached."})
                q.append(now)
        # Deny cross-origin state-changing browser calls.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                from urllib.parse import urlsplit
                parsed = urlsplit(origin)
                host = request.headers.get("host", "")
                if parsed.netloc != host or parsed.scheme not in {"https", "http"}:
                    return JSONResponse(status_code=403, content={"detail": "Cross-origin request denied."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response
