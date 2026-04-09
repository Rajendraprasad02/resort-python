from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.lead import Lead, LeadUpdate
from app.schemas.guest import Guest
from app.services import lead_service

router = APIRouter()

@router.get("/", response_model=List[Lead])
async def read_leads(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    search: str = Query(None, description="Search by name, email, or phone")
) -> Any:
    """
    Retrieve all unconverted leads.
    """
    return await lead_service.get_leads(db, skip=skip, limit=limit, search=search)

@router.get("/{lead_id}", response_model=Lead)
async def read_lead(
    lead_id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Get lead details by ID.
    """
    lead = await lead_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.post("/{lead_id}/convert", response_model=Guest)
async def convert_lead(
    lead_id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Manually convert a lead to a formal guest record.
    """
    guest = await lead_service.convert_lead_to_guest(db, lead_id)
    if not guest:
        raise HTTPException(status_code=400, detail="Could not convert lead. It may already be converted or doesn't exist.")
    return guest
