import os
import uuid
import shutil
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.guest import Guest, GuestCreate, GuestUpdate
from app.services import guest_service

router = APIRouter()

UPLOAD_DIR = "uploads/guests/ids"

@router.get("/", response_model=List[Guest])
async def read_guests(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    source: Optional[str] = Query(None, description="Filter by guest source")
) -> Any:
    return await guest_service.get_guests(db, skip=skip, limit=limit, search=search, source=source)

@router.post("/", response_model=Guest, status_code=status.HTTP_201_CREATED)
async def create_guest(
    guest_in: GuestCreate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    return await guest_service.create_guest(db, guest_in=guest_in)

@router.get("/{id}", response_model=Guest)
async def read_guest(
    id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    guest = await guest_service.get_guest(db, id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest

@router.patch("/{id}", response_model=Guest)
async def update_guest(
    id: int,
    guest_in: GuestUpdate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    guest = await guest_service.update_guest(db, id, guest_in)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest

@router.delete("/{id}")
async def delete_guest(
    id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    success = await guest_service.delete_guest(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Guest not found")
    return {"message": "Guest profile deleted successfully"}

@router.post("/{id}/id-proof", response_model=Guest)
async def upload_guest_id_proof(
    id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    # 1. Check guest exists
    guest = await guest_service.get_guest(db, id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    # 2. Local save
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"id_{id}_{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. Update DB
    return await guest_service.update_guest(db, id, GuestUpdate(id_proof_image_url=file_path))
