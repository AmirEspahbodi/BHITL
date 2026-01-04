from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.models import Comment as Sample

router = APIRouter(prefix="/samples", tags=["/samples"])
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)


class SampleSchema(BaseModel):
    id: str
    label_name: str
    definition: str
    inclusion_criteria: str
    exclusion_criteria: str


class SampleSchemaResponse(BaseModel):
    samples: list[SampleSchema]


@router.get(
    "",
    response_model=SampleSchemaResponse,
)
async def get_principles(*, session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Fetch all principles and map them to the response schema.
    """
    statement = select(Sample)
    results = session.exec(statement).all()

    principles_list = [
        SampleSchema(
            id=principle.id,
            label_name=principle.name,
            definition=principle.definition,
            inclusion_criteria=principle.inclusion_criteria or "",
            exclusion_criteria=principle.exclusion_criteria or "",
        )
        for principle in results
    ]
    return SampleSchemaResponse(samples=principles_list)
