from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from datetime import datetime

app = FastAPI(title="MindfulAI API", version="1.0.0")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your React Native app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database models (will be moved to separate files)
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/mindfulai")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    audio_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create all tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class JournalEntryCreate(BaseModel):
    content: str
    audio_path: Optional[str] = None

class JournalEntryResponse(JournalEntryCreate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Welcome to MindfulAI API"}

@app.post("/api/journal/", response_model=JournalEntryResponse)
def create_journal_entry(entry: JournalEntryCreate, db: Session = Depends(get_db)):
    # In a real app, you would get the user_id from the JWT token
    db_entry = JournalEntry(**entry.dict(), user_id=1)  # Hardcoded user_id for now
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

@app.get("/api/journal/", response_model=List[JournalEntryResponse])
def get_journal_entries(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    # In a real app, filter by authenticated user
    return db.query(JournalEntry).filter(JournalEntry.user_id == 1).offset(skip).limit(limit).all()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

