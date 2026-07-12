from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from pathlib import Path
import re

from auth import get_current_user
from roots import load_roots, save_roots, user_roots

router = APIRouter()


def _require_superadmin(user=Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")
    return user


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


class RootCreate(BaseModel):
    label: str
    path: str
    icon: str = "📁"


@router.get("/")
def list_roots(user=Depends(get_current_user)):
    """List roots available to the current user."""
    return user_roots(user)


@router.post("/", dependencies=[Depends(_require_superadmin)])
def create_root(body: RootCreate):
    p = Path(body.path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Path does not exist or is not a directory: {body.path}")
    roots = load_roots()
    root_id = _slug(body.label)
    # ensure unique id
    existing_ids = {r["id"] for r in roots}
    if root_id in existing_ids:
        i = 2
        while f"{root_id}-{i}" in existing_ids:
            i += 1
        root_id = f"{root_id}-{i}"
    roots.append({"id": root_id, "label": body.label, "path": str(p.resolve()), "icon": body.icon})
    save_roots(roots)
    return {"id": root_id, "label": body.label, "path": str(p.resolve()), "icon": body.icon}


@router.delete("/{root_id}", dependencies=[Depends(_require_superadmin)])
def delete_root(root_id: str):
    roots = load_roots()
    new_roots = [r for r in roots if r["id"] != root_id]
    if len(new_roots) == len(roots):
        raise HTTPException(status_code=404, detail="Root not found")
    if not new_roots:
        raise HTTPException(status_code=400, detail="Cannot delete the last root")
    save_roots(new_roots)
    return {"deleted": root_id}
