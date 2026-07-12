import json
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("activity.log")


def log_event(user: str, action: str, path: str = "", detail: str = ""):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "action": action,
        "path": path,
        "detail": detail,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
