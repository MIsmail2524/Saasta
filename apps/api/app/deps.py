from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import API_KEY_PREFIX, decode_access_token, hash_api_key
from app.db import get_db
from app.models import ApiKey, Merchant, User

COOKIE = "saasta_session"


async def optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and not auth[7:].startswith(API_KEY_PREFIX):
        token = auth[7:]
    if not token:
        return None
    claims = decode_access_token(token)
    if not claims:
        return None
    user = await db.get(User, claims["sub"])
    if not user or user.token_version != claims.get("tv"):
        return None  # logged out everywhere / password changed
    return user


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(401, "Please log in")
    return user


async def merchant_owner(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Merchant:
    m = (await db.execute(select(Merchant).where(Merchant.owner_id == user.id))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "No store registered for this account")
    return m


async def merchant_from_key(
    x_api_key: str | None = Header(default=None), db: AsyncSession = Depends(get_db)
) -> Merchant:
    if not x_api_key or not x_api_key.startswith(API_KEY_PREFIX) or len(x_api_key) > 100:
        raise HTTPException(401, "Missing or invalid API key")
    key = (await db.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(x_api_key), ApiKey.revoked.is_(False))
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(401, "Missing or invalid API key")
    key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return await db.get(Merchant, key.merchant_id)
