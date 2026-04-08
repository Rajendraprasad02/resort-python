import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import AsyncSessionLocal
from app.models.asset import PropertyAsset, AssetImage

async def seed_data():
    async with AsyncSessionLocal() as db:
        # Initial Villa Assets with Multiple Images
        villa1 = PropertyAsset(
            name="Coral Beach Villa",
            type="villa",
            status="Available",
            base_price=1200.0,
            max_adults=4,
            bedrooms=3,
            view="Beachfront",
            pool_type="Private"
        )
        villa1.images = [
            AssetImage(url="https://images.resort.com/villas/coral-cover.jpg", description="Main entrance of the Villa", is_cover=True),
            AssetImage(url="https://images.resort.com/villas/coral-pool.jpg", description="Private infinity pool at sunset", is_cover=False),
            AssetImage(url="https://images.resort.com/villas/coral-bed.jpg", description="Master bedroom with ocean view", is_cover=False)
        ]

        villa2 = PropertyAsset(
            name="Azure Sky Villa",
            type="villa",
            status="Occupied",
            base_price=950.0,
            max_adults=2,
            bedrooms=1,
            view="Ocean View",
            pool_type="Private"
        )
        villa2.images = [
            AssetImage(url="https://images.resort.com/villas/azure-cover.jpg", description="Aerial view of the sky villa", is_cover=True),
            AssetImage(url="https://images.resort.com/villas/azure-bath.jpg", description="Luxury open-air bathroom", is_cover=False)
        ]
        
        # Initial Room Assets
        room1 = PropertyAsset(
            name="Deluxe Ocean Room 101",
            type="room",
            status="Available",
            base_price=450.0,
            max_adults=2,
            view="Ocean View"
        )
        room1.images = [
            AssetImage(url="https://images.resort.com/rooms/101-main.jpg", description="Deluxe bedding and balcony", is_cover=True)
        ]
        
        db.add_all([villa1, villa2, room1])
        await db.commit()
        print("Successfully seeded assets with multiple images.")

if __name__ == "__main__":
    asyncio.run(seed_data())
