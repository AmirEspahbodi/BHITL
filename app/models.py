import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserCommentRevision(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    comment_id: str = Field(foreign_key="comment.id")
    principle_id: str = Field(foreign_key="principle.id")
    expert_opinion: str | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    revised_comments: list["Comment"] = Relationship(
        back_populates="revisers", link_model=UserCommentRevision
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class Principle(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    definition: str
    context_rule: str | None = None
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None
    comments: list["Comment"] = Relationship(back_populates="principle")


class Comment(SQLModel, table=True):
    id: str = Field(primary_key=True)
    preceding: str | None = None
    target: str
    following: str | None = None
    A1_Score: int
    A2_Score: int
    A3_Score: int
    llm_justification: str | None = Field(
        default=None, sa_column_kwargs={"nullable": True}
    )
    llm_evidence_quote: str | None = None
    principle_id: str | None = Field(foreign_key="principle.id")
    principle: Principle | None = Relationship(back_populates="comments")
    revisers: list["User"] = Relationship(
        back_populates="revised_comments", link_model=UserCommentRevision
    )


class PrincipleUpdate(UserBase):
    label_name: str | str
    definition: str | str
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None


class CommentUpdate(UserBase):
    expert_opinion: str | None = None
    is_revised: bool | None
    reviser_id: int | None
    principle_id: int | None
    revision_timestamp: datetime | None = None


class PasswordResetToken(SQLModel, table=True):
    token_hash: str = Field(primary_key=True)
    email: str
    used: bool = False
    created_at: datetime
