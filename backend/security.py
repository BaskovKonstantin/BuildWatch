from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, time
from fastapi import HTTPException, Request
import db

SECRET = os.getenv("BUILDWATCH_AUTH_SECRET", "dev-only-change-me")
AUTH_REQUIRED = os.getenv("BUILDWATCH_AUTH_REQUIRED", "0") == "1"

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2$240000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds))
        return hmac.compare_digest(base64.urlsafe_b64encode(actual).decode(), expected)
    except (ValueError, TypeError):
        return False

def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def _decode(token: str) -> dict:
    try:
        raw, sig = token.split(".", 1)
        if not hmac.compare_digest(hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest(), sig): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload["exp"] < time.time(): raise ValueError
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(401, "invalid or expired token")

def login(email: str, password: str) -> str:
    rows = db.query("SELECT id,email,password_hash,role FROM users WHERE email=?", (email.lower().strip(),))
    if not rows or not verify_password(password, rows[0]["password_hash"]): raise HTTPException(401, "invalid credentials")
    r = rows[0]
    return _sign({"sub": r["id"], "email": r["email"], "role": r["role"], "exp": time.time()+8*3600})

def current_user(request: Request) -> dict | None:
    if not AUTH_REQUIRED: return None
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "): raise HTTPException(401, "bearer token required")
    return _decode(header[7:])

def require_role(request: Request, *roles: str) -> dict | None:
    user = current_user(request)
    if user and roles and user["role"] not in roles: raise HTTPException(403, "insufficient role")
    return user
