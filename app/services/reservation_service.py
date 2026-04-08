from typing import List, Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreate, ReservationUpdate

async def check_availability(db: AsyncSession, asset_id: int, check_in: date, check_out: date, exclude_res_id: Optional[int] = None) -> bool:
    """
    Check if a Room/Villa is available for the given dates.
    Excludes any reservation ID (useful during an update).
    """
    query = select(Reservation).filter(
        Reservation.asset_id == asset_id,
        Reservation.status != "Cancelled",
        or_(
            and_(Reservation.check_in <= check_in, Reservation.check_out > check_in),
            and_(Reservation.check_in < check_out, Reservation.check_out >= check_out),
            and_(Reservation.check_in >= check_in, Reservation.check_out <= check_out)
        )
    )
    if exclude_res_id:
        query = query.filter(Reservation.id != exclude_res_id)
        
    result = await db.execute(query)
    existing_booking = result.scalars().first()
    return existing_booking is None

async def create_reservation(db: AsyncSession, res_in: ReservationCreate) -> Reservation:
    # 1. First check availability
    available = await check_availability(db, res_in.asset_id, res_in.check_in, res_in.check_out)
    if not available:
        raise ValueError("Room is already booked for these dates.")
        
    # 2. Save reservation
    db_obj = Reservation(**res_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_reservations(
    db: AsyncSession, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None
) -> List[Reservation]:
    query = select(Reservation)
    if start_date and end_date:
        query = query.filter(
            or_(
                and_(Reservation.check_in <= start_date, Reservation.check_out >= start_date),
                and_(Reservation.check_in >= start_date, Reservation.check_in <= end_date)
            )
        )
    result = await db.execute(query.order_by(Reservation.check_in))
    return result.scalars().all()

async def get_reservation(db: AsyncSession, res_id: int) -> Optional[Reservation]:
    result = await db.execute(select(Reservation).filter(Reservation.id == res_id))
    return result.scalars().first()

async def update_reservation(db: AsyncSession, res_id: int, res_in: ReservationUpdate) -> Optional[Reservation]:
    db_res = await get_reservation(db, res_id)
    if not db_res:
        return None
        
    update_data = res_in.model_dump(exclude_unset=True)
    
    # If dates or asset changed, check availability again
    new_in = update_data.get("check_in", db_res.check_in)
    new_out = update_data.get("check_out", db_res.check_out)
    new_asset = update_data.get("asset_id", db_res.asset_id)
    
    if "check_in" in update_data or "check_out" in update_data or "asset_id" in update_data:
        available = await check_availability(db, new_asset, new_in, new_out, exclude_res_id=res_id)
        if not available:
            raise ValueError("New dates/asset are unavailable for booking.")
            
    for field, value in update_data.items():
        setattr(db_res, field, value)
        
    db.add(db_res)
    await db.commit()
    await db.refresh(db_res)
    return db_res

async def delete_reservation(db: AsyncSession, res_id: int) -> bool:
    db_res = await get_reservation(db, res_id)
    if not db_res:
        return False
    # SOFT DELETE: Actually archive/cancel usually better, but for this request we will just delete
    await db.delete(db_res)
    await db.commit()
    return True
