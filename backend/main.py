"""Platapicker FastAPI application entry point."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from backend.models.database import init_db
from backend.services.seed import seed_database
from backend.models.database import SessionLocal
from backend.api.routes import router

logger = logging.getLogger("platapicker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🦆 Platapicker starting up...")
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    logger.info("✅ Database ready. Platapicker is running.")
    yield
    logger.info("Platapicker shutting down.")


app = FastAPI(
    title="Platapicker",
    description="Deal monitoring control center for resale and auction opportunities.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serve frontend build if it exists
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
