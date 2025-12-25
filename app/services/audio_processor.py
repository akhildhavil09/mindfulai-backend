# /Users/akhil/Documents/MIndfulAI/backend/app/services/audio_processor.py
import os
import logging
import torch
import numpy as np
from pydub import AudioSegment
from typing import Optional, Tuple
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model and processor instances
_model = None
_processor = None

async def load_glm_model():
    """Load the GLM ASR Nano-2512 model asynchronously"""
    global _model, _processor
    
    if _model is None or _processor is None:
        try:
            model_name = "THUDM/glm-asr-nano-2512"
            
            # Load model and processor
            _processor = AutoProcessor.from_pretrained(model_name)
            _model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                low_cpu_mem_usage=True,
                use_safetensors=True
            )
            
            # Move model to GPU if available
            if torch.cuda.is_available():
                _model = _model.to("cuda")
                
            logger.info("GLM ASR Nano-2512 model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load GLM ASR model: {str(e)}")
            raise
            
    return _model, _processor

def convert_audio_format(audio_file_path: str, target_format: str = "wav") -> str:
    """Convert audio file to target format using pydub"""
    try:
        audio = AudioSegment.from_file(audio_file_path)
        temp_path = f"{os.path.splitext(audio_file_path)[0]}.{target_format}"
        audio.export(temp_path, format=target_format)
        return temp_path
    except Exception as e:
        logger.error(f"Audio conversion failed: {str(e)}")
        raise

async def transcribe_audio(
    audio_file_path: str,
    language: Optional[str] = "en",
    **kwargs
) -> Tuple[str, dict]:
    """
    Transcribe audio using GLM ASR Nano-2512 model
    
    Args:
        audio_file_path: Path to audio file
        language: Language code (e.g., 'en', 'zh')
        **kwargs: Additional arguments for the model
        
    Returns:
        Tuple of (transcribed_text, metadata)
    """
    try:
        # Load model
        model, processor = await load_glm_model()
        
        # Convert to WAV if needed
        if not audio_file_path.lower().endswith('.wav'):
            audio_file_path = convert_audio_format(audio_file_path, "wav")
        
        # Load audio
        audio = AudioSegment.from_file(audio_file_path)
        
        # Convert to mono and 16kHz sample rate if needed
        if audio.channels > 1:
            audio = audio.set_channels(1)
        if audio.frame_rate != 16000:
            audio = audio.set_frame_rate(16000)
            
        # Convert to numpy array
        samples = np.array(audio.get_array_of_samples())
        input_features = processor(
            samples, 
            sampling_rate=16000, 
            return_tensors="pt"
        ).input_features
        
        # Move to GPU if available
        if torch.cuda.is_available():
            input_features = input_features.to("cuda")
        
        # Generate transcription
        with torch.no_grad():
            predicted_ids = model.generate(input_features, **kwargs)
            
        # Decode the prediction
        transcription = processor.batch_decode(
            predicted_ids, 
            skip_special_tokens=True
        )[0]
        
        # Prepare metadata
        metadata = {
            "language": language,
            "model": "GLM-ASR-Nano-2512",
            "duration": len(audio) / 1000.0,  # in seconds
            "sample_rate": audio.frame_rate,
            "channels": audio.channels
        }
        
        return transcription, metadata
        
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise
    finally:
        # Clean up temporary files if any
        if 'temp_path' in locals() and os.path.exists(locals()['temp_path']):
            os.unlink(locals()['temp_path'])

def clean_text(text: str) -> str:
    """Basic text cleaning function"""
    if not text:
        return ""
        
    # Basic text cleaning
    text = " ".join(text.split())  # Remove extra whitespace
    text = text.strip()
    
    # Capitalize first letter
    if text:
        text = text[0].upper() + text[1:]
        # Ensure it ends with a period
        if not text.endswith(('.', '!', '?')):
            text += '.'
            
    return text