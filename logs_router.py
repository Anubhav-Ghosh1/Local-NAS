from fastapi import APIRouter, Depends, HTTPException, Query
from pathlib import Path
import json

from auth import get_current_user

router = APIRouter()
LOG_FILE = Path("activity.log")


@router.get("/")
def get_logs(
    limit: int = Query(default=200, le=1000),
    user: str | None = Query(default=None),
    action: str | None = Query(default=None),
    current=Depends(get_current_user),
):
    if current["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin only")
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().strip().splitlines()
    out = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if user and e.get("user") != user:
                continue
            if action and e.get("action") != action:
                continue
            out.append(e)
            if len(out) >= limit:
                break
        except Exception:
            pass
    return out
