from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class JournalEntryBase(BaseModel):
    content: str = Field(..., description="The text content of the journal entry")
    audio_path: Optional[str] = Field(None, description="Path to the associated audio file, if any")

class JournalEntryCreate(JournalEntryBase):
    user_id: int = Field(..., description="ID of the user who created the entry")

class JournalEntryUpdate(BaseModel):
    content: Optional[str] = Field(None, description="Updated text content of the journal entry")
    audio_path: Optional[str] = Field(None, description="Updated path to the associated audio file")

class JournalEntryResponse(JournalEntryBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AudioTranscriptionResponse(BaseModel):
    status: str
    text: str
    audio_path: str
    
    class Config:
        json_encoders = {
            'bytes': lambda v: v.decode('utf-8') if isinstance(v, bytes) else v
        }
