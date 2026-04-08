from typing import Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.reservation import Reservation, ReservationCreate, ReservationUpdate
from app.services import reservation_service

router = APIRouter()

@router.get("/", response_model=List[Reservation])
async def read_reservations(
    db: AsyncSession = Depends(deps.get_db),
    start_date: Optional[date] = Query(None, description="Start date for calendar view"),
    end_date: Optional[date] = Query(None, description="End date for calendar view")
) -> Any:
    """
    Retrieve all bookings. Filters: Support start_date and end_date.
    """
    return await reservation_service.get_reservations(db, start_date=start_date, end_date=end_date)

@router.post("/", response_model=Reservation, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    res_in: ReservationCreate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create a new reservation. Includes room availability validation.
    """
    try:
        return await reservation_service.create_reservation(db, res_in=res_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{id}", response_model=Reservation)
async def update_reservation(
    id: int,
    res_in: ReservationUpdate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Update booking dates or status.
    """
    try:
        res = await reservation_service.update_reservation(db, id, res_in)
        if not res:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{id}")
async def delete_reservation(
    id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Archive or remove a cancelled reservation.
    """
    success = await reservation_service.delete_reservation(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return {"message": "Reservation removed successfully"}
