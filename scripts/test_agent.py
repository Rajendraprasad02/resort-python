import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import AsyncSessionLocal
from app.ai.groq_service import GroqService
from app.ai.agent_service import EliteHMAgent

async def test_agent():
    groq = GroqService()
    agent = EliteHMAgent(groq)
    
    queries = [
        "hi how are you?",
        "What are your checkout times?",
        "Show me all villas under $2000 per night",
        "How many guests do we have in our CRM?",
        "Which rooms are available with an ocean view?"
    ]
    
    async with AsyncSessionLocal() as db:
        for q in queries:
            print(f"\n[GUEST]: {q}")
            response = await agent.process_request(db, q)
            print(f"[CONCIERGE]: {response}")

if __name__ == "__main__":
    asyncio.run(test_agent())
