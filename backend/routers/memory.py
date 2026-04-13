"""Memory router exposing Hindsight retain/recall/reflect APIs."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from routers.auth import get_current_user
from services.hindsight_service import (
    build_bank_id,
    is_enabled,
    recall,
    reflect,
    retain,
)

router = APIRouter()


class RetainRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    fact_type: str = "world_fact"
    bank_id: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


class RecallRequest(BaseModel):
    query: str = Field(default="", max_length=1000)
    bank_id: Optional[str] = None
    limit: int = 5


class ReflectRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    bank_id: Optional[str] = None
    mission: Optional[str] = None
    directives: List[str] = Field(default_factory=list)
    disposition: Dict[str, int] = Field(default_factory=dict)


@router.get("/status")
async def memory_status(current_user: dict = Depends(get_current_user)):
    return {
        "enabled": is_enabled(),
        "bank_id": build_bank_id(current_user),
    }


@router.post("/retain")
async def retain_memory(request: RetainRequest, current_user: dict = Depends(get_current_user)):
    bank_id = build_bank_id(current_user, request.bank_id)
    result = await retain(
        bank_id=bank_id,
        content=request.content,
        fact_type=request.fact_type,
        metadata=request.metadata,
    )
    return {
        "bank_id": bank_id,
        "result": result,
    }


@router.post("/recall")
async def recall_memory(request: RecallRequest, current_user: dict = Depends(get_current_user)):
    bank_id = build_bank_id(current_user, request.bank_id)
    result = await recall(bank_id=bank_id, query=request.query, limit=request.limit)
    return {
        "bank_id": bank_id,
        "result": result,
    }


@router.post("/reflect")
async def reflect_memory(request: ReflectRequest, current_user: dict = Depends(get_current_user)):
    bank_id = build_bank_id(current_user, request.bank_id)
    result = await reflect(
        bank_id=bank_id,
        query=request.query,
        mission=request.mission,
        directives=request.directives,
        disposition=request.disposition,
    )
    if not result.get("ok"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result.get("error") or "Reflect failed")
    return {
        "bank_id": bank_id,
        "result": result,
    }
