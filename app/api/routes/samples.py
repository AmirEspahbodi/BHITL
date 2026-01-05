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
            UserCommentRevision.updated_at,
            UserCommentRevision.created_at,
            User.full_name.label("reviser_name"),
            UserCommentRevision.is_revise_completed,
            UserCommentRevision.principle_id.label("user_principle_id"),
        )
        .where(Sample.id == sample_id)
        .outerjoin(
            UserCommentRevision,
            (UserCommentRevision.comment_id == Sample.id)
            & (UserCommentRevision.user_id == current_user.id),
        )
        .outerjoin(User, User.id == UserCommentRevision.user_id)
    )

    result = session.exec(statement).first()

    if not result:
        raise HTTPException(status_code=404, detail="Sample not found")

    (
        sample,
        expert_opinion,
        updated_at,
        created_at,
        reviser_name,
        is_revise_completed,
        user_principle_id,
    ) = result

    data_row = DataRow(
        id=sample.id,
        preceding=sample.preceding,
        target=sample.target,
        following=sample.following,
        A1_Score=sample.A1_Score,
        A2_Score=sample.A2_Score,
        A3_Score=sample.A3_Score,
        principle_id=user_principle_id if user_principle_id else sample.principle_id,
        llm_justification=sample.llm_justification,
        llm_evidence_quote=sample.llm_evidence_quote,
        expert_opinion=expert_opinion,
        is_revised=is_revise_completed if is_revise_completed else False,
        reviser_name=reviser_name,
        revision_timestamp=updated_at if updated_at else created_at,
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
        principle_id=revision.principle_id,
        llm_justification=sample.llm_justification,
        llm_evidence_quote=sample.llm_evidence_quote,
        expert_opinion=revision.expert_opinion,
        is_revised=revision.is_revise_completed,
        reviser_name=current_user.full_name,
        revision_timestamp=revision.updated_at or revision.created_at,
    )

    return SampleResponse(sample=data_row)


class ToggleSampleRevisionRequest(BaseModel):
    is_revised: bool
    reviser_name: str


@router.patch("/{sample_id}/revision", response_model=SampleResponse)
async def toggle_sample_revision(
    sample_id: str,
    session: SessionDep,
    request: ToggleSampleRevisionRequest,
    current_user: CurrentUser,
):
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
        revision.is_revise_completed = request.is_revised
        revision.updated_at = now
        session.add(revision)
    else:
        revision = UserCommentRevision(
            user_id=current_user.id,
            comment_id=sample.id,
            principle_id=sample.principle_id,
            expert_opinion="",
            is_revise_completed=request.is_revised,
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
        principle_id=revision.principle_id,
        llm_justification=sample.llm_justification,
        llm_evidence_quote=sample.llm_evidence_quote,
        expert_opinion=revision.expert_opinion,
        is_revised=revision.is_revise_completed,
        reviser_name=current_user.full_name,
        revision_timestamp=revision.updated_at or revision.created_at,
    )
    return SampleResponse(sample=data_row)


class ToggleSampleReassignRequest(BaseModel):
    target_principle_id: bool
    reviser_name: str


@router.patch("/{sample_id}/reassign", response_model=SampleResponse)
async def toggle_sample_reassign(
    sample_id: str,
    session: SessionDep,
    request: ToggleSampleReassignRequest,
    current_user: CurrentUser,
):
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
        revision.principle_id = request.target_principle_id
        revision.is_revise_completed = True
        revision.updated_at = now
        session.add(revision)
    else:
        revision = UserCommentRevision(
            user_id=current_user.id,
            comment_id=sample.id,
            principle_id=request.target_principle_id,
            expert_opinion="",
            is_revise_completed=True,
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
        principle_id=revision.principle_id,
        llm_justification=sample.llm_justification,
        llm_evidence_quote=sample.llm_evidence_quote,
        expert_opinion=revision.expert_opinion,
        is_revised=revision.is_revise_completed,
        reviser_name=current_user.full_name,
        revision_timestamp=revision.updated_at or revision.created_at,
    )
    return SampleResponse(sample=data_row)
