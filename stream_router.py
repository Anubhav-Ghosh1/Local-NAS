from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from pathlib import Path
import mimetypes
import os

from config import settings
from roots import get_root, resolve

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def _auth(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    token: str | None = Query(default=None),
) -> dict:
    """Accept JWT from Authorization header OR ?token= query param (needed for <video src>)."""
    raw = creds.credentials if creds else token
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(raw, settings.SECRET_KEY, algorithms=["HS256"])
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _check_access(root_id: str, user: dict) -> dict:
    root = get_root(root_id)
    if not root:
        raise HTTPException(status_code=404, detail="Root not found")
    allowed = user.get("allowed_roots", [])
    role = user.get("role", "user")
    if "*" not in allowed and role not in ("admin", "superadmin") and root_id not in allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    return root


@router.get("/{root_id}/{path:path}")
async def stream(root_id: str, path: str, request: Request, user=Depends(_auth)):
    root = _check_access(root_id, user)
    target = resolve(root, path)

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"
    file_size = os.path.getsize(target)
    range_header = request.headers.get("range")

    if range_header:
        parts = range_header.replace("bytes=", "").split("-")
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def gen_range():
            with open(target, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            gen_range(),
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": mime,
            },
        )

    def gen_full():
        with open(target, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        gen_full(),
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": mime,
        },
    )
