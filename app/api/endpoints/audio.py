from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import os
import uuid
import shutil
import asyncio

from app.services.audio_processor import transcribe_audio
from app.db.session import get_db
from app.models.journal import JournalEntry
from app.schemas.journal import (
    JournalEntryCreate, 
    JournalEntryResponse,
    AudioTranscriptionResponse
)

router = APIRouter()

# Ensure uploads directory exists
UPLOAD_DIR = "uploads/audio"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_upload_file(upload_file: UploadFile, destination: str) -> str:
    """Save uploaded file asynchronously"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # Save file in chunks to handle large files
        with open(destination, "wb") as buffer:
            while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
        return destination
    except Exception as e:
        if os.path.exists(destination):
            os.unlink(destination)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
    finally:
        await upload_file.close()

@router.post("/transcribe/", response_model=AudioTranscriptionResponse)
async def transcribe_audio_file(
    audio_file: UploadFile = File(...),
    language: Optional[str] = "en"
):
    """
    Upload an audio file and transcribe it to text using Whisper ASR.
    Supports various audio formats including WAV, MP3, M4A, etc.
    """
    try:
        # Validate file type
        file_ext = os.path.splitext(audio_file.filename.lower())[1]
        if file_ext not in ('.wav', '.mp3', '.m4a', '.ogg', '.webm'):
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Supported formats: WAV, MP3, M4A, OGG, WEBM"
            )
        
        # Generate a unique filename
        filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save the uploaded file
        await save_upload_file(audio_file, file_path)
        
        try:
            # Transcribe audio asynchronously
            text, metadata = await transcribe_audio(
                file_path,
                language=language,
                beam_size=5
            )
            
            return {
                "status": "success",
                "text": text,
                "audio_path": file_path,
                "metadata": metadata
            }
            
        except Exception as e:
            # Clean up the file if transcription fails
            if os.path.exists(file_path):
                os.unlink(file_path)
            raise HTTPException(
                status_code=500,
                detail=f"Transcription failed: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/journal/audio/", response_model=JournalEntryResponse)
async def create_journal_from_audio(
    audio_file: UploadFile = File(...),
    db=Depends(get_db)
):
    """
    Create a new journal entry from an audio recording.
    The audio is automatically transcribed and stored with the journal entry.
    """
    try:
        # First, transcribe the audio
        transcription = await transcribe_audio_file(audio_file)
        
        if transcription["status"] != "success":
            raise HTTPException(
                status_code=400,
                detail="Failed to transcribe audio"
            )
        
        # Create journal entry
        journal_data = JournalEntryCreate(
            content=transcription["text"],
            audio_path=transcription["audio_path"]
        )
        
        # Save to database
        db_journal = JournalEntry(**journal_data.dict(), user_id=1)  # TODO: Get user_id from auth
        db.add(db_journal)
        await asyncio.get_event_loop().run_in_executor(None, db.commit)
        db.refresh(db_journal)
        
        return db_journal
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create journal entry: {str(e)}"
        )

@router.post("/journal/text/", response_model=JournalEntryResponse)
async def create_journal_from_text(
    content: str,
    db=Depends(get_db)
):
    """
    Create a new journal entry from text.
    The text is automatically cleaned before being stored.
    """
    try:
        from app.services.audio_processor import clean_text
        cleaned_text = clean_text(content)
        
        # Create journal entry
        journal_data = JournalEntryCreate(
            content=cleaned_text,
            audio_path=None
        )
        
        # Save to database
        db_journal = JournalEntry(**journal_data.dict(), user_id=1)  # TODO: Get user_id from auth
        db.add(db_journal)
        await asyncio.get_event_loop().run_in_executor(None, db.commit)
        db.refresh(db_journal)
        
        return db_journal
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create journal entry: {str(e)}"
        )

@router.get("/journal/{journal_id}/transcribe", response_model=Dict[str, Any])
async def transcribe_existing_journal_audio(
    journal_id: int,
    db=Depends(get_db)
):
    """
    Re-transcribe the audio of an existing journal entry.
    Useful if the transcription quality improves or if the audio was updated.
    """
    try:
        # Get the journal entry
        journal = db.query(JournalEntry).filter(
            JournalEntry.id == journal_id
        ).first()
        
        if not journal:
            raise HTTPException(status_code=404, detail="Journal entry not found")
            
        if not journal.audio_path or not os.path.exists(journal.audio_path):
            raise HTTPException(
                status_code=400,
                detail="No audio file associated with this journal entry or file not found"
            )
        
        # Transcribe the audio
        text, metadata = await transcribe_audio(journal.audio_path)
        
        # Update the journal entry
        journal.content = text
        await asyncio.get_event_loop().run_in_executor(None, db.commit)
        
        return {
            "status": "success",
            "journal_id": journal_id,
            "text": text,
            "metadata": metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transcribe journal audio: {str(e)}"
        )