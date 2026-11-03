"""Owner-scoped task planning. No unattended execution or external actions."""
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from auth import authenticated

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
TASKS: dict[str, dict[str, dict]] = defaultdict(dict)
MAX_TASKS = 50

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(default="", max_length=2000)
    due_at: datetime | None = None

class TaskAction(BaseModel):
    action: str = Field(pattern="^(approve|complete|cancel)$")

def owner_token(request: Request) -> str:
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Owner authentication required.")
    return request.cookies["jarvis_session"]

@router.get("")
async def list_tasks(request: Request):
    token = owner_token(request)
    return {"tasks": list(TASKS[token].values()), "execution_enabled": False, "storage": "temporary"}

@router.post("", status_code=201)
async def create_task(body: TaskCreate, request: Request):
    token = owner_token(request)
    if len(TASKS[token]) >= MAX_TASKS:
        raise HTTPException(status_code=429, detail="Task limit reached.")
    if body.due_at and (body.due_at.tzinfo is None or body.due_at.utcoffset() is None):
        raise HTTPException(status_code=422, detail="Due time must include a timezone.")
    now = datetime.now(timezone.utc).isoformat()
    item = {"id": str(uuid4()), "title": body.title.strip(), "notes": body.notes,
            "due_at": body.due_at.isoformat() if body.due_at else None,
            "status": "pending", "created_at": now, "updated_at": now}
    if not item["title"]:
        raise HTTPException(status_code=422, detail="Title cannot be blank.")
    TASKS[token][item["id"]] = item
    return item

@router.post("/{task_id}/action")
async def task_action(task_id: str, body: TaskAction, request: Request):
    token = owner_token(request)
    item = TASKS[token].get(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    transitions = {"pending": {"approve": "approved", "cancel": "cancelled"},
                   "approved": {"complete": "completed", "cancel": "cancelled"}}
    status = transitions.get(item["status"], {}).get(body.action)
    if not status:
        raise HTTPException(status_code=409, detail="Invalid task transition.")
    item["status"] = status
    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    return item

@router.delete("")
async def clear_tasks(request: Request):
    token = owner_token(request)
    count = len(TASKS.pop(token, {}))
    return {"cleared": count}

def install_tasks(app):
    app.include_router(router)
