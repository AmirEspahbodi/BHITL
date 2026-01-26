import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import SQLModel, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Message,
    UpdatePassword,
    User,
    UserCommentRevision,
    UserPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import send_email

router = APIRouter(prefix="/users", tags=["users"])


# New Pydantic models for the response
class UserReviseStats(UserPublic):
    revised_count: int


class NonSuperUsersResponse(SQLModel):
    total_comments: int
    users: list[UserReviseStats]


@router.get(
    "/non-superusers",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=NonSuperUsersResponse,
)
def read_non_super_users(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get list of non-super users with their completed revision count and the global total of completed revisions.
    """
    # 1. Calculate global total of completed revisions by non-superusers
    count_statement = (
        select(func.count(UserCommentRevision.id))
        .join(User, User.id == UserCommentRevision.user_id)
        .where(User.is_superuser == False)
        .where(UserCommentRevision.is_revise_completed == True)
    )
    total_comments = session.exec(count_statement).one()

    # 2. Get list of non-superusers with their individual revision counts
    statement = (
        select(User, func.count(UserCommentRevision.id))
        .outerjoin(
            UserCommentRevision,
            (User.id == UserCommentRevision.user_id)
            & (UserCommentRevision.is_revise_completed == True),
        )
        .where(User.is_superuser == False)
        .group_by(User.id)
        .offset(skip)
        .limit(limit)
    )

    results = session.exec(statement).all()

    # 3. Format the data
    users_data = []
    for user, count in results:
        user_dict = user.model_dump()
        user_dict["revised_count"] = count
        users_data.append(user_dict)

    return NonSuperUsersResponse(total_comments=total_comments, users=users_data)


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")


@router.get("/{user_id}/get-dataset")
def get_user_dataset(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Generate and download a JSON dataset of completed revisions for a specific user.
    """
    # 1. Authorization Check
    # Ensure the current user is requesting their own data, or is a superuser
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )

    # 2. Query the UserCommentRevision table
    # Filter by the specific user_id and only include completed revisions
    statement = (
        select(UserCommentRevision)
        .where(UserCommentRevision.user_id == user_id)
        .where(UserCommentRevision.is_revise_completed == True)
    )
    results = session.exec(statement).all()

    # 3. Create the dataset list
    # Extract only comment_id and principle_id as requested
    dataset = [
        {"comment_id": record.comment_id, "principle_id": record.principle_id}
        for record in results
    ]

    # 4. Serialize to JSON
    # using ensure_ascii=False is good practice if IDs might contain non-ascii chars,
    # though unlikely for IDs. indent=2 makes it human-readable.
    json_content = json.dumps(dataset, indent=2)

    # 5. Return the Response
    # Setting Content-Disposition attachment forces the browser to download the file
    # rather than displaying it.
    filename = f"dataset_{user_id}.json"
    return Response(
        content=json_content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
