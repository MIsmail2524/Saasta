from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ratelimit import enforce
from app.core.security import (
    create_access_token,
    hash_password,
    needs_rehash,
    password_problems,
    verify_password,
)
from app.db import get_db
from app.deps import COOKIE, current_user
from app.models import User
from app.schemas import LoginIn, PasswordChangeIn, SignupIn, UserOut

router = APIRouter(prefix="/v1/auth", tags=["auth"])
LOCK_AFTER = 8
LOCK_MINUTES = 15


def _set_cookie(resp: Response, user: User) -> None:
    s = get_settings()
    resp.set_cookie(
        COOKIE, create_access_token(user.id, user.role, user.token_version),
        httponly=True, secure=s.is_prod, samesite="lax", max_age=s.access_token_minutes * 60, path="/",
    )


def _out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, name=u.name, role=u.role)


@router.post("/signup", response_model=UserOut, status_code=201)
async def signup(body: SignupIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    await enforce(request, "signup", s.rl_auth_per_min, 60)
    if problems := password_problems(body.password):
        raise HTTPException(422, "Password needs: " + ", ".join(problems))
    email = body.email.lower()
    if (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none():
        # Same message shape as success-ish failure; don't confirm which emails exist beyond this.
        raise HTTPException(409, "Could not create account with that email")
    user = User(email=email, password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    await db.commit()
    _set_cookie(response, user)
    return _out(user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    await enforce(request, "login", s.rl_auth_per_min, 60)
    await enforce(request, "login-acct", 20, 3600, subject=body.email.lower())
    user = (await db.execute(select(User).where(func.lower(User.email) == body.email.lower()))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    locked = user and user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now
    ok = verify_password(body.password, user.password_hash if user else None)
    if not user or locked or not ok:
        if user and not locked:
            user.failed_logins += 1
            if user.failed_logins >= LOCK_AFTER:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            await db.commit()
        raise HTTPException(401, "Wrong email or password")
    user.failed_logins = 0
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    await db.commit()
    _set_cookie(response, user)
    return _out(user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")


@router.post("/logout-all", status_code=204)
async def logout_all(response: Response, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    user.token_version += 1
    await db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.post("/password", status_code=204)
async def change_password(body: PasswordChangeIn, request: Request, response: Response,
                          user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await enforce(request, "pwchange", 5, 3600, subject=user.id)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(401, "Current password is wrong")
    if problems := password_problems(body.new_password):
        raise HTTPException(422, "Password needs: " + ", ".join(problems))
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # kill other sessions
    await db.commit()
    _set_cookie(response, user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return _out(user)


@router.delete("/me", status_code=204)
async def delete_account(response: Response, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Right to erasure: removes the user and cascades their watches, boards and try-ons."""
    await db.delete(user)
    await db.commit()
    response.delete_cookie(COOKIE, path="/")
