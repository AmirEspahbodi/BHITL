from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.models import Principle

router = APIRouter(prefix="/principles", tags=["/principles"])
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)


class PrincipleSchema(BaseModel):
    id: int
    label_name: str
    definition: str
    inclusion_criteria: str
    exclusion_criteria: str


class PrinciplesSchemaResponse(BaseModel):
    principles: list[PrincipleSchema]


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
