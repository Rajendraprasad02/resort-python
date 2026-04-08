from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Register a direct root-level route specifically for WhatsApp (for Meta Dashboard ease of use)
from app.api.v1.endpoints import whatsapp
app.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp_root"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Mount the uploads directory so the frontend can retrieve WhatsApp Media
os.makedirs("uploads/whatsapp_media", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
