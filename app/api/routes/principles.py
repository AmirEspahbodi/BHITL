from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

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
