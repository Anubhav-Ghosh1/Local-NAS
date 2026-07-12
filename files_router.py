from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import mimetypes
import shutil

from auth import get_current_user
from roots import get_root, user_roots, resolve
from logger import log_event


class TextBody(BaseModel):
    content: str

router = APIRouter()

EDITABLE_EXTS = {
    ".txt", ".md", ".json", ".js", ".ts", ".jsx", ".tsx", ".css", ".html",
    ".htm", ".xml", ".yaml", ".yml", ".toml", ".py", ".rb", ".go", ".rs",
    ".java", ".c", ".cpp", ".h", ".sh", ".bash", ".zsh", ".env", ".sql",
    ".graphql", ".vue", ".svelte", ".csv", ".ini", ".cfg", ".conf",
}


def _check_access(root_id: str, user: dict) -> dict:
    root = get_root(root_id)
    if not root:
        raise HTTPException(status_code=404, detail="Root not found")
    allowed = user.get("allowed_roots", [])
    if "*" not in allowed and user["role"] not in ("admin", "superadmin") and root_id not in allowed:
        raise HTTPException(status_code=403, detail="You do not have access to this root")
    return root


def _info(p: Path, base: Path) -> dict:
    stat = p.stat()
    mime, _ = mimetypes.guess_type(str(p))
    ext = p.suffix.lower()
    return {
        "name": p.name,
        "path": str(p.relative_to(base)),
        "is_dir": p.is_dir(),
        "size": stat.st_size if p.is_file() else None,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "mime": mime,
        "ext": ext,
        "streamable": bool(mime and mime.startswith(("video/", "audio/", "image/"))),
        "editable": bool(ext in EDITABLE_EXTS or (mime and mime.startswith("text/"))),
    }


# ── Browse / download ─────────────────────────────────────────────────
@router.get("/{root_id}")
@router.get("/{root_id}/{path:path}")
def browse(root_id: str, path: str = "", user=Depends(get_current_user)):
    root = _check_access(root_id, user)
    base = Path(root["path"]).resolve()
    target = resolve(root, path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")

    if target.is_dir():
        items = []
        for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                items.append(_info(item, base))
            except (PermissionError, OSError):
                pass
        return {"root_id": root_id, "path": path, "items": items}

    return FileResponse(target, filename=target.name)


# ── Upload ────────────────────────────────────────────────────────────
@router.post("/{root_id}/upload")
async def upload(
    root_id: str,
    path: str = Query(default=""),
    files: list[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    root = _check_access(root_id, user)
    target_dir = resolve(root, path)
    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="Target must be a directory")
    uploaded = []
    for f in files:
        dest = target_dir / f.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        uploaded.append(f.filename)
        log_event(user["username"], "upload", f"{root_id}:{path}/{f.filename}".rstrip("/"))
    return {"uploaded": uploaded}


# ── Mkdir ─────────────────────────────────────────────────────────────
@router.post("/{root_id}/mkdir")
def mkdir(root_id: str, path: str = Query(...), user=Depends(get_current_user)):
    root = _check_access(root_id, user)
    target = resolve(root, path)
    target.mkdir(parents=True, exist_ok=True)
    log_event(user["username"], "mkdir", f"{root_id}:{path}")
    return {"created": path}


# ── Rename ────────────────────────────────────────────────────────────
@router.patch("/{root_id}/rename")
def rename(
    root_id: str,
    path: str = Query(...),
    new_name: str = Query(...),
    user=Depends(get_current_user),
):
    if "/" in new_name or "\\" in new_name:
        raise HTTPException(status_code=400, detail="Name cannot contain slashes")
    root = _check_access(root_id, user)
    base = Path(root["path"]).resolve()
    target = resolve(root, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")
    dest = target.parent / new_name
    if dest.exists():
        raise HTTPException(status_code=409, detail="Name already taken")
    target.rename(dest)
    new_path = str(dest.relative_to(base))
    log_event(user["username"], "rename", f"{root_id}:{path}", f"→ {new_name}")
    return {"old": path, "new": new_path}


# ── Text read / write ─────────────────────────────────────────────────
@router.get("/{root_id}/text")
def read_text(root_id: str, path: str = Query(...), user=Depends(get_current_user)):
    root = _check_access(root_id, user)
    target = resolve(root, path)
    if not target.is_file():
        raise HTTPException(status_code=404)
    if target.stat().st_size > 1024 * 1024:  # 1 MB cap
        raise HTTPException(status_code=413, detail="File too large to edit in browser (max 1 MB)")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"path": path, "content": content}


@router.put("/{root_id}/text")
def write_text(
    root_id: str,
    path: str = Query(...),
    body: TextBody = ...,
    user=Depends(get_current_user),
):
    root = _check_access(root_id, user)
    target = resolve(root, path)
    if not target.exists():
        raise HTTPException(status_code=404)
    target.write_text(body.content, encoding="utf-8")
    log_event(user["username"], "edit", f"{root_id}:{path}")
    return {"saved": path}


# ── Delete ────────────────────────────────────────────────────────────
@router.delete("/{root_id}/{path:path}")
def delete(root_id: str, path: str, user=Depends(get_current_user)):
    root = _check_access(root_id, user)
    target = resolve(root, path)
    if not target.exists():
        raise HTTPException(status_code=404)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    log_event(user["username"], "delete", f"{root_id}:{path}")
    return {"deleted": path}
