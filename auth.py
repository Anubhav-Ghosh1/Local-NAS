from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from config import settings

router = APIRouter()
security = HTTPBearer()
USERS_FILE = Path("users.json")

ROLES = ("user", "admin", "superadmin")


# ── Password helpers ──────────────────────────────────────────────────
def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── User store ────────────────────────────────────────────────────────
def init_users():
    if not USERS_FILE.exists():
        users = {
            "admin": {
                "username": "admin",
                "hashed_password": _hash("admin123"),
                "role": "superadmin",
                "allowed_roots": ["*"],
            }
        }
        USERS_FILE.write_text(json.dumps(users, indent=2))
        print("\n⚠️  Default user created: admin / admin123 — CHANGE THIS PASSWORD!\n")


def _load() -> dict:
    return json.loads(USERS_FILE.read_text())


def _save(users: dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))


# ── JWT ───────────────────────────────────────────────────────────────
def _make_token(username: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "role": role, "exp": exp}, settings.SECRET_KEY, algorithm="HS256")


def _decode(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Dependencies ──────────────────────────────────────────────────────
def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = _decode(creds.credentials)
    users = _load()
    u = users.get(payload["sub"], {})
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "allowed_roots": u.get("allowed_roots", []),
    }


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin or superadmin required")
    return user


def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")
    return user


# ── Models ────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    allowed_roots: list[str] = []


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


# ── Routes ────────────────────────────────────────────────────────────
@router.post("/login")
def login(req: LoginRequest):
    from logger import log_event
    users = _load()
    user = users.get(req.username)
    if not user or not _verify(req.password, user["hashed_password"]):
        log_event(req.username, "login_failed", detail="bad credentials")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token(req.username, user["role"])
    log_event(req.username, "login")
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "username": req.username,
        "allowed_roots": user.get("allowed_roots", []),
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(req: PasswordChange, user: dict = Depends(get_current_user)):
    from logger import log_event
    users = _load()
    u = users[user["username"]]
    if not _verify(req.old_password, u["hashed_password"]):
        raise HTTPException(status_code=401, detail="Wrong current password")
    u["hashed_password"] = _hash(req.new_password)
    _save(users)
    log_event(user["username"], "change_password")
    return {"message": "Password changed"}


@router.get("/users")
def list_users(user: dict = Depends(require_admin)):
    users = _load()
    return [
        {"username": u, "role": d["role"], "allowed_roots": d.get("allowed_roots", [])}
        for u, d in users.items()
    ]


@router.post("/users")
def create_user(req: UserCreate, actor: dict = Depends(require_admin)):
    from logger import log_event
    # only superadmin can create admins/superadmins
    if req.role in ("admin", "superadmin") and actor["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can create admin accounts")
    users = _load()
    if req.username in users:
        raise HTTPException(status_code=400, detail="User already exists")
    users[req.username] = {
        "username": req.username,
        "hashed_password": _hash(req.password),
        "role": req.role,
        "allowed_roots": req.allowed_roots,
    }
    _save(users)
    log_event(actor["username"], "create_user", detail=f"user={req.username} role={req.role}")
    return {"message": f"User {req.username} created"}


@router.patch("/users/{username}/access")
def set_access(
    username: str,
    allowed_roots: list[str] = Body(...),
    actor: dict = Depends(require_superadmin),
):
    from logger import log_event
    users = _load()
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    users[username]["allowed_roots"] = allowed_roots
    _save(users)
    log_event(actor["username"], "set_access", detail=f"user={username} roots={allowed_roots}")
    return {"username": username, "allowed_roots": allowed_roots}


@router.patch("/users/{username}/role")
def set_role(
    username: str,
    role: str = Body(...),
    actor: dict = Depends(require_superadmin),
):
    if role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ROLES}")
    users = _load()
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    users[username]["role"] = role
    _save(users)
    return {"username": username, "role": role}


@router.delete("/users/{username}")
def delete_user(username: str, actor: dict = Depends(require_admin)):
    from logger import log_event
    users = _load()
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete the primary admin account")
    target_role = users[username]["role"]
    if target_role in ("admin", "superadmin") and actor["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can delete admin accounts")
    del users[username]
    _save(users)
    log_event(actor["username"], "delete_user", detail=f"user={username}")
    return {"message": f"Deleted {username}"}
