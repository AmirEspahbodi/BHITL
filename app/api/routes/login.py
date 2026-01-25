from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request  # ✅ Import Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from limits import parse  # ✅ Import parse to create the limit rule
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Message, NewPassword, Token, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
# ❌ Remove the decorator @limiter.limit("5/minute")
# We handle it manually inside to access form_data
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """

    # ✅ 1. Rate Limit Logic: Limit by Username
    # We create a unique key for this user: "login:username"
    # We use the existing limiter storage to track hits.
    limit_key = f"login:{form_data.username}"
    limit_rule = parse("5/minute")

    # limiter.limiter is the internal strategy (e.g., FixedWindow).
    # .hit() returns True if allowed, False if limit exceeded.
    if not limiter.limiter.hit(limit_rule, limit_key):
        # Optional: Log the attempt here
        raise HTTPException(
            status_code=429, detail="Too many login attempts. Please try again later."
        )

    # ✅ 2. Authentication Logic (Only runs if rate limit passes)
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Determine user type
    user_type = "superuser" if user.is_superuser else "normal"

    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        user_type=user_type,
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


# In login.py
@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    user = crud.get_user_by_email(session=session, email=email)

    if user:  # Only send email if user exists
        # Pass session to generate function to persist token
        password_reset_token = generate_password_reset_token(
            session=session, email=email
        )
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )

    # ✅ Always return same message
    return Message(message="If that email exists, a recovery link has been sent")


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token, session=session)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )

    # Pass session to generate function to persist token
    password_reset_token = generate_password_reset_token(session=session, email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
