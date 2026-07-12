"""Shared utilities for multi-root management."""
import json
from pathlib import Path
from typing import Optional
from fastapi import HTTPException

ROOTS_FILE = Path("roots.json")


def _default() -> list[dict]:
    return [{"id": "home", "label": "Home", "path": str(Path.home()), "icon": "🏠"}]


def init_roots():
    if not ROOTS_FILE.exists():
        ROOTS_FILE.write_text(json.dumps(_default(), indent=2))


def load_roots() -> list[dict]:
    if not ROOTS_FILE.exists():
        return _default()
    return json.loads(ROOTS_FILE.read_text())


def save_roots(roots: list[dict]):
    ROOTS_FILE.write_text(json.dumps(roots, indent=2))


def get_root(root_id: str) -> Optional[dict]:
    for r in load_roots():
        if r["id"] == root_id:
            return r
    return None


def user_roots(user: dict) -> list[dict]:
    """Roots visible to a user based on their allowed_roots list."""
    allowed = user.get("allowed_roots", [])
    all_roots = load_roots()
    if "*" in allowed or user["role"] in ("admin", "superadmin"):
        return all_roots
    return [r for r in all_roots if r["id"] in allowed]


def resolve(root: dict, path: str) -> Path:
    """Resolve a path within a root, blocking traversal."""
    base = Path(root["path"]).resolve()
    target = (base / path.lstrip("/")).resolve() if path else base
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=403, detail="Access denied")
    return target
