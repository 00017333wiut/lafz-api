import httpx
import logging
from app.config import UZBEKVOICE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

UZBEKVOICE_URL = "https://uzbekvoice.ai/api/v1/tts"
SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object/audio"


def generate_and_store_audio(text: str, filename: str) -> str | None:
    """
    Generate TTS audio for text and store in Supabase Storage.
    Returns the public URL or None on failure.
    filename should be unique e.g. 'exercise_42.mp3' or 'word_salom.mp3'
    """
    try:
        # Call UzbekVoice TTS
        response = httpx.post(
            UZBEKVOICE_URL,
            headers={
                "Authorization": UZBEKVOICE_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "model": "dilfuza-neutral",
                "blocking": True
            },
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"UzbekVoice TTS failed: {response.status_code} {response.text}")
            return None

        # Response is raw audio bytes (mp3)
        audio_bytes = response.content

        # Upload to Supabase Storage
        upload_url = f"{SUPABASE_STORAGE_URL}/{filename}"
        upload_response = httpx.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "audio/mpeg",
                "x-upsert": "true"  # overwrite if exists
            },
            content=audio_bytes,
            timeout=30
        )

        if upload_response.status_code not in (200, 201):
            logger.error(f"Supabase upload failed: {upload_response.status_code} {upload_response.text}")
            return None

        # Return public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/audio/{filename}"
        logger.info(f"Audio stored: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None