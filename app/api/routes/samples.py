from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.api.routes.common import DataRow
from app.models import Comment as Sample
from app.models import User, UserCommentRevision

router = APIRouter(prefix="/samples", tags=["/samples"])
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)


class SampleResponse(BaseModel):
    sample: DataRow


@router.get("/{sample_id}", response_model=SampleResponse)
async def get_sample(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    sample_id: str,
) -> Any:
    """
    Fetch a single sample by ID with revision status for the current user.
    """
    statement = (
        select(
            Sample,
            UserCommentRevision.expert_opinion,
            UserCommentRevision.created_at.label("revision_timestamp"),
            User.full_name.label("reviser_name"),
            UserCommentRevision.is_revise_completed,
        )
        .where(Sample.id == sample_id)
        .outerjoin(
            UserCommentRevision,
            (UserCommentRevision.sample_id == Sample.id)
            & (UserCommentRevision.user_id == current_user.id),
        )
        .outerjoin(User, User.id == UserCommentRevision.user_id)
    )

    result = session.exec(statement).first()

    if not result:
        raise HTTPException(status_code=404, detail="Sample not found")

    sample, expert_opinion, revision_timestamp, reviser_name, is_revise_completed = (
        result
    )

    data_row = DataRow(
        id=sample.id,
        preceding=sample.preceding,
        target=sample.target,
        following=sample.following,
        A1_Score=sample.A1_Score,
        A2_Score=sample.A2_Score,
        A3_Score=sample.A3_Score,
        principle_id=sample.principle_id,
        llm_justification=sample.llm_justification,
        llm_evidence_quote=sample.llm_evidence_quote,
        expert_opinion=expert_opinion,
        is_revised=is_revise_completed if is_revise_completed else False,
        reviser_name=reviser_name,
        revision_timestamp=revision_timestamp,
    )

    return SampleResponse(sample=data_row)


class UpdateSampleOpinionRequest(BaseModel):
    expert_opinion: str


@router.patch("/{sample_id}/opinion", response_model=SampleResponse)
async def update_add_opinion(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    sample_id: str,
    expert_opinion_in: UpdateSampleOpinionRequest,
) -> Any:
    """
    Update/add expert_opinion of/to related revision row of this sample efficiently.
    """
    statement = (
        select(Sample, UserCommentRevision)
        .where(Sample.id == sample_id)
        .outerjoin(
            UserCommentRevision,
            (UserCommentRevision.comment_id == Sample.id)
            & (UserCommentRevision.user_id == current_user.id),
        )
    )

    result = session.exec(statement).first()

    if not result:
        raise HTTPException(status_code=404, detail="Sample not found")

    sample, revision = result

    now = datetime.now(timezone.utc)

    if revision:
        revision.expert_opinion = expert_opinion_in.expert_opinion
        revision.updated_at = now
        session.add(revision)
    else:
        revision = UserCommentRevision(
            user_id=current_user.id,
            comment_id=sample.id,
            principle_id=sample.principle_id,
            expert_opinion=expert_opinion_in.expert_opinion,
            is_revise_completed=False,
            created_at=now,
            updated_at=now,
        )
        session.add(revision)

    session.commit()
    session.refresh(revision)

    data_row = DataRow(
        id=sample.id,
        preceding=sample.preceding,
        target=sample.target,
        following=sample.following,
        A1_Score=sample.A1_Score,
        A2_Score=sample.A2_Score,
        A3_Score=sample.A3_Score,
        principle_id=sample.principle_id,
        llm_justification=sample.llm_justification,
        llm_evidence_quote=sample.llm_evidence_quote,
        expert_opinion=revision.expert_opinion,
        is_revised=revision.is_revise_completed,
        reviser_name=current_user.full_name,
        revision_timestamp=revision.updated_at or revision.created_at,
    )

    return SampleResponse(sample=data_row)
