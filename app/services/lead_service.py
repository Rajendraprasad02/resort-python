from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func
from app.models.lead import Lead
from app.models.guest import Guest
from app.schemas.guest import GuestCreate

async def get_leads(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None
) -> List[Lead]:
    query = select(Lead)
    if search:
        query = query.filter(
            or_(
                Lead.name.ilike(f"%{search}%"),
                Lead.email.ilike(f"%{search}%"),
                Lead.phone.ilike(f"%{search}%")
            )
        )
    result = await db.execute(query.order_by(Lead.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()

async def get_lead(db: AsyncSession, lead_id: int) -> Optional[Lead]:
    result = await db.execute(select(Lead).filter(Lead.id == lead_id))
    return result.scalars().first()

async def convert_lead_to_guest(db: AsyncSession, lead_id: int) -> Optional[Guest]:
    """
    Converts a Lead into a formal Guest record.
    """
    lead = await get_lead(db, lead_id)
    if not lead or lead.is_converted:
        return None
    
    # Check if guest already exists with this phone
    stmt = select(Guest).where(Guest.phone == lead.phone)
    res = await db.execute(stmt)
    existing_guest = res.scalar_one_or_none()
    
    if existing_guest:
        lead.is_converted = True
        lead.guest_id = existing_guest.id
        await db.commit()
        return existing_guest

    # Create new Guest
    new_guest = Guest(
        name=lead.name,
        email=lead.email or f"{lead.phone}@whatsapp.invalid",
        phone=lead.phone,
        source=lead.source,
        id_number="PENDING" # Requirement from Guest model
    )
    db.add(new_guest)
    await db.flush() # Get ID
    
    lead.is_converted = True
    lead.guest_id = new_guest.id
    
    await db.commit()
    await db.refresh(new_guest)
    return new_guest
