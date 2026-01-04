from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.models import Message, Principle

router = APIRouter(prefix="/principles", tags=["/principles"])


class PrincipleSchema(BaseModel):
    id: str  # <--- FIXED: changed from int to str to match your DB model
    label_name: str
    definition: str
    inclusion_criteria: str
    exclusion_criteria: str


class PrinciplesSchemaResponse(BaseModel):
    principles: list[PrincipleSchema]


class UpdatePrincipleRequest(BaseModel):
    label_name: str | None = None
    definition: str | None = None
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None


@router.get(
    "",
    response_model=PrinciplesSchemaResponse,
)
async def get_principles(*, session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Fetch all principles and map them to the response schema.
    """
    statement = select(Principle)
    results = session.exec(statement).all()

    principles_list = [
        PrincipleSchema(
            id=principle.id,
            label_name=principle.name,
            definition=principle.definition,
            inclusion_criteria=principle.inclusion_criteria or "",
            exclusion_criteria=principle.exclusion_criteria or "",
        )
        for principle in results
    ]
    return PrinciplesSchemaResponse(principles=principles_list)


@router.patch(
    "/{principle_id}", response_model=PrincipleSchema
)  # <--- Renamed path param
async def update_principle(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    principle_id: str,
    principle_in: UpdatePrincipleRequest,
) -> Any:
    """
    Update a principle.
    """
    # Use the specific ID passed in the URL
    principle = session.get(Principle, principle_id)

    if not principle:
        raise HTTPException(
            status_code=404, detail=f"Principle with id {principle_id} not found"
        )

    if principle_in.label_name is not None:
        principle.name = principle_in.label_name
    if principle_in.definition is not None:
        principle.definition = principle_in.definition
    if principle_in.inclusion_criteria is not None:
        principle.inclusion_criteria = principle_in.inclusion_criteria
    if principle_in.exclusion_criteria is not None:
        principle.exclusion_criteria = principle_in.exclusion_criteria

    session.add(principle)
    session.commit()
    session.refresh(principle)

    return PrincipleSchema(
        id=principle.id,
        label_name=principle.name,
        definition=principle.definition,
        inclusion_criteria=principle.inclusion_criteria or "",
        exclusion_criteria=principle.exclusion_criteria or "",
    )


from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlmodel import distinct, func, select

from app.models import Comment, Principle, User, UserCommentRevision  #

# ... existing imports ...

# --- Response Schemas for Samples ---


class DataRow(BaseModel):
    id: str
    preceding: str | None
    target: str
    following: str | None
    A1_Score: int
    A2_Score: int
    A3_Score: int
    principle_id: str
    llm_justification: str | None
    llm_evidence_quote: str | None
    expert_opinion: str | None

    # FIXED: Use 'alias' instead of 'serialization_alias' to handle INPUT and OUTPUT
    is_revised: bool = Field(alias="isRevised")
    reviser_name: str | None = Field(default=None, alias="reviserName")
    revision_timestamp: datetime | None = Field(default=None, alias="revisionTimestamp")

    class Config:
        populate_by_name = True


class SampleStats(BaseModel):
    total: int
    revised: int
    percentage: float


class SamplesResponse(BaseModel):
    samples: list[DataRow]
    stats: SampleStats


def get_principle_comments_with_revision_status(
    session: Session, principle_id: str, current_user_id: UUID
) -> list[dict]:
    statement = (
        select(
            Comment,
            UserCommentRevision.expert_opinion,
            UserCommentRevision.created_at.label("revision_timestamp"),
            UserCommentRevision.updated_at,
            User.full_name.label("reviser_name"),
        )
        .where(Comment.principle_id == principle_id)
        .outerjoin(
            UserCommentRevision,
            (UserCommentRevision.comment_id == Comment.id)
            & (UserCommentRevision.user_id == current_user_id),
        )
        .outerjoin(User, User.id == UserCommentRevision.user_id)
    )

    results = session.exec(statement).all()

    samples = []
    for (
        comment,
        expert_opinion,
        revision_timestamp,
        updated_at,
        reviser_name,
    ) in results:
        samples.append(
            {
                "id": comment.id,
                "preceding": comment.preceding,
                "target": comment.target,
                "following": comment.following,
                "A1_Score": comment.A1_Score,
                "A2_Score": comment.A2_Score,
                "A3_Score": comment.A3_Score,
                "principle_id": comment.principle_id,
                "llm_justification": comment.llm_justification,
                "llm_evidence_quote": comment.llm_evidence_quote,
                "expert_opinion": expert_opinion,
                "isRevised": expert_opinion is not None,
                "reviserName": reviser_name,
                "revisionTimestamp": revision_timestamp.isoformat()
                if revision_timestamp
                else None,
            }
        )

    return samples


@router.get("/{principle_id}/samples", response_model=SamplesResponse)
async def get_samples_by_principle(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    principle_id: str,
    show_revised: bool = True,
) -> Any:
    raw_samples = get_principle_comments_with_revision_status(
        session, principle_id, current_user.id
    )
    total_count = len(raw_samples)
    revised_count = sum(1 for s in raw_samples if s["isRevised"])
    percentage = (revised_count / total_count * 100) if total_count > 0 else 0.0
    stats = SampleStats(
        total=total_count, revised=revised_count, percentage=round(percentage, 2)
    )
    if not show_revised:
        filtered_samples = [s for s in raw_samples if not s["isRevised"]]
    else:
        filtered_samples = raw_samples
    data_rows = [DataRow(**sample) for sample in filtered_samples]
    return SamplesResponse(samples=data_rows, stats=stats)
