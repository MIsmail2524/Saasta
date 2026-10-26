import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()  # argon2id, library defaults follow OWASP guidance
_ALG = "HS256"
API_KEY_PREFIX = "sk_saasta_"

# A precomputed hash so unknown-email logins still pay the argon2 cost (no timing oracle).
_DUMMY_HASH = _ph.hash("not-a-real-password-" + secrets.token_hex(8))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY_HASH, password) and hashed is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


def create_access_token(user_id: str, role: str, token_version: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "iss": "saasta",
        "aud": "saasta-web",
    }
    return jwt.encode(payload, s.secret_key, algorithm=_ALG)


def decode_access_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(
            token, s.secret_key, algorithms=[_ALG], audience="saasta-web", issuer="saasta",
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError:
        return None


def new_api_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix, hash). Plaintext is shown once and never stored."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[: len(API_KEY_PREFIX) + 6], hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    # Keys are 256-bit random, so a keyed fast hash is sufficient (no need for argon2).
    return hmac.new(get_settings().secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    s = get_settings()
    return hmac.new(s.ip_hash_salt.encode(), ip.encode(), hashlib.sha256).hexdigest()


def password_problems(pw: str) -> list[str]:
    problems = []
    if len(pw) < 10:
        problems.append("at least 10 characters")
    if len(pw) > 128:
        problems.append("at most 128 characters")
    if pw.lower() in _COMMON:
        problems.append("too common")
    if len(set(pw)) < 5:
        problems.append("too repetitive")
    return problems


_COMMON = {
    "password12", "password123", "1234567890", "qwertyuiop", "pakistan123", "iloveyou12",
    "admin12345", "letmein123", "welcome123", "abcdef1234", "qwerty1234", "1q2w3e4r5t",
}
