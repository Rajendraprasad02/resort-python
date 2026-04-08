from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.reservation import Reservation
from app.models.asset import PropertyAsset

async def get_dashboard_metrics(db: AsyncSession) -> dict:
    """
    Modernized Dashboard Metrics: Calculated from the Elite HMS schema.
    """
    result_total_revenue = await db.execute(select(func.sum(Reservation.total_price)).filter(Reservation.status != "Cancelled"))
    total_revenue = result_total_revenue.scalar() or 0.0
    
    result_total_bookings = await db.execute(select(func.count(Reservation.id)))
    total_bookings = result_total_bookings.scalar() or 0
    
    result_total_rooms = await db.execute(select(func.count(PropertyAsset.id)))
    total_rooms = result_total_rooms.scalar() or 0

    return {
        "revenue": total_revenue,
        "total_bookings": total_bookings,
        "total_rooms": total_rooms
    }
