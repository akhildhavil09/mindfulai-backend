from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database models to ensure they are registered with SQLAlchemy
from app.models.journal import User, JournalEntry
from app.db.session import engine, Base
from app.db.session import get_db

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="MindfulAI API",
    description="API for MindfulAI journaling application",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your React Native app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
from app.api.endpoints import audio as audio_endpoints
app.include_router(audio_endpoints.router, prefix="/api", tags=["Audio Processing"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to MindfulAI API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
