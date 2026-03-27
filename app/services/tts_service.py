import httpx
import logging
from app.config import UZBEKVOICE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

UZBEKVOICE_URL = "https://uzbekvoice.ai/api/v1/tts"
SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object/audio"


def generate_and_store_audio(text: str, filename: str) -> str | None:
    try:
        # Step 1 — submit blocking TTS job
        response = httpx.post(
            UZBEKVOICE_URL,
            headers={
                "Authorization": UZBEKVOICE_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "model": "lola",
                "blocking": "true",
                "webhook_notification_url": "https://example.com"
            },
            timeout=60
        )

        if response.status_code != 200:
            logger.error(f"TTS failed: {response.status_code} {response.text}")
            return None

        data = response.json()
        status = data.get("status")

        if status != "SUCCESS":
            logger.error(f"TTS status not SUCCESS: {data}")
            return None

        audio_url = data.get("result", {}).get("url")
        if not audio_url:
            logger.error(f"No URL in result: {data}")
            return None

        logger.info(f"TTS generated, downloading from CDN...")

        # Step 2 — download the wav file from S3
        audio_response = httpx.get(audio_url, timeout=30)
        if audio_response.status_code != 200:
            logger.error(f"Audio download failed: {audio_response.status_code}")
            return None

        audio_bytes = audio_response.content
        logger.info(f"Downloaded {len(audio_bytes)} bytes")

        # Step 3 — upload to Supabase Storage as wav
        wav_filename = filename.replace(".mp3", ".wav")
        upload_url = f"{SUPABASE_STORAGE_URL}/{wav_filename}"

        upload_response = httpx.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "audio/wav",
                "x-upsert": "true"
            },
            content=audio_bytes,
            timeout=30
        )

        if upload_response.status_code not in (200, 201):
            logger.error(f"Supabase upload failed: {upload_response.status_code} {upload_response.text}")
            return None

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/audio/{wav_filename}"
        logger.info(f"Audio stored: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None