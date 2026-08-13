from __future__ import annotations

from fastapi import APIRouter

from backend.conversion.registry import registry


router = APIRouter()


@router.get("/formats")
async def formats() -> dict:
    return {"categories": registry.categories()}
