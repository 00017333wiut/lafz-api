import httpx
import logging
import time
from app.config import UZBEKVOICE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

UZBEKVOICE_BASE = "https://uzbekvoice.ai/api/v1"
SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object/audio"


def generate_and_store_audio(text: str, filename: str) -> str | None:
    try:
        # Step 1 — submit TTS job
        response = httpx.post(
            f"{UZBEKVOICE_BASE}/tts",
            headers={
                "Authorization": UZBEKVOICE_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "model": "dilfuza-neutral",
                "blocking": False
            },
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"TTS submit failed: {response.status_code} {response.text}")
            return None

        job_id = response.json().get("id")
        if not job_id:
            logger.error("No job ID returned from UzbekVoice")
            return None

        logger.info(f"TTS job submitted: {job_id}")

        job_parts = job_id.replace("tts/", "")

        # Step 2 — poll until complete (max 30 seconds)
        audio_url = None
        for attempt in range(15):
            time.sleep(2)

            poll = httpx.get(
                f"https://uzbekvoice.ai/api/v1/tts/{job_parts}",
                headers={"Authorization": UZBEKVOICE_API_KEY},
                timeout=15
            )

            if poll.status_code != 200:
                logger.error(f"Poll failed: {poll.status_code}")
                continue

            poll_data = poll.json()
            status = poll_data.get("status")
            logger.info(f"TTS poll attempt {attempt + 1}: status={status}")

            if status == "SUCCESS":
                # Try common field names for the audio URL
                audio_url = (
                    poll_data.get("url") or
                    poll_data.get("audio_url") or
                    poll_data.get("file_url") or
                    poll_data.get("result")
                )
                logger.info(f"TTS success, full response: {poll_data}")
                break
            elif status in ("FAILED", "ERROR"):
                logger.error(f"TTS job failed: {poll_data}")
                return None

        if not audio_url:
            logger.error(f"TTS timed out or no URL found for job {job_id}")
            return None

        # Step 3 — download audio from UzbekVoice
        audio_response = httpx.get(audio_url, timeout=30)
        if audio_response.status_code != 200:
            logger.error(f"Audio download failed: {audio_response.status_code}")
            return None

        audio_bytes = audio_response.content
        logger.info(f"Downloaded {len(audio_bytes)} bytes of audio")

        # Step 4 — upload to Supabase Storage
        upload_url = f"{SUPABASE_STORAGE_URL}/{filename}"
        upload_response = httpx.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "audio/mpeg",
                "x-upsert": "true"
            },
            content=audio_bytes,
            timeout=30
        )

        if upload_response.status_code not in (200, 201):
            logger.error(f"Supabase upload failed: {upload_response.status_code} {upload_response.text}")
            return None

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/audio/{filename}"
        logger.info(f"Audio stored successfully: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None