from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func
from app.models.guest import Guest
from app.models.reservation import Reservation
from app.schemas.guest import GuestCreate, GuestUpdate

async def create_guest(db: AsyncSession, guest_in: GuestCreate) -> Guest:
    db_obj = Guest(**guest_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_guests(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    source: Optional[str] = None
) -> List[Guest]:
    query = select(Guest)
    if search:
        query = query.filter(
            or_(
                Guest.name.ilike(f"%{search}%"),
                Guest.email.ilike(f"%{search}%"),
                Guest.phone.ilike(f"%{search}%")
            )
        )
    if source:
        query = query.filter(Guest.source == source)
        
    result = await db.execute(query.offset(skip).limit(limit))
    guests = result.scalars().all()
    
    # Compute total stays for each guest
    for guest in guests:
        qty = (await db.execute(select(func.count(Reservation.id)).filter(
            Reservation.guest_id == guest.id,
            Reservation.status == "Checked-In" # Or however we define a 'completed' stay
        ))).scalar() or 0
        guest.total_stays = qty
        
        # loyalty logic
        if qty > 10: guest.loyalty_tier = "Platinum"
        elif qty > 5: guest.loyalty_tier = "Gold"
        elif qty > 2: guest.loyalty_tier = "Silver"
        else: guest.loyalty_tier = "Blue"
        
    return guests

async def get_guest(db: AsyncSession, guest_id: int) -> Optional[Guest]:
    result = await db.execute(select(Guest).filter(Guest.id == guest_id))
    guest = result.scalars().first()
    if guest:
        qty = (await db.execute(select(func.count(Reservation.id)).filter(
            Reservation.guest_id == guest.id
        ))).scalar() or 0
        guest.total_stays = qty
    return guest

async def update_guest(db: AsyncSession, guest_id: int, guest_in: GuestUpdate) -> Optional[Guest]:
    guest = await get_guest(db, guest_id)
    if not guest:
        return None
        
    update_data = guest_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(guest, field, value)
    
    db.add(guest)
    await db.commit()
    await db.refresh(guest)
    return guest

async def delete_guest(db: AsyncSession, guest_id: int) -> bool:
    guest = await get_guest(db, guest_id)
    if not guest:
        return False
    await db.delete(guest)
    await db.commit()
    return True
