import logging
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.routers import auth, units, lessons, progress
from app.database import supabase

# ── Logging setup ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Lafz API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lafz-backend-service-production.up.railway.app",
        "http://10.0.2.2:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(units.router,    prefix="/units",    tags=["units"])
app.include_router(lessons.router,  prefix="/lessons",  tags=["lessons"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])

@app.get("/health")
def health():
    logger.info("Health check called")
    try:
        from app.database import engine
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        return {"status": "ok", "database": "error", "detail": str(e)}

@app.get("/debug-tts")
def debug_tts(current_user: dict = Depends(get_current_user)):
    import httpx, time
    from app.config import UZBEKVOICE_API_KEY

    response = httpx.post(
        "https://uzbekvoice.ai/api/v1/tts",
        headers={
            "Authorization": UZBEKVOICE_API_KEY,
            "Content-Type": "application/json"
        },
        json={"text": "Salom", "model": "dilfuza-neutral", "blocking": False},
        timeout=30
    )

    job_data = response.json()
    job_id = job_data.get("id")  # e.g. "tts/47b714de.../4e48af74..."
    job_parts = job_id.replace("tts/", "")

    time.sleep(5)

    # Use job_id directly as the path — don't prepend /tts/
    poll = httpx.get(
        f"https://uzbekvoice.ai/api/v1/tts/{job_parts}",
        headers={"Authorization": UZBEKVOICE_API_KEY},
        timeout=15
    )

    return {
        "job_id": job_id,
        "poll_status": poll.status_code,
        "poll_response": poll.json() if poll.status_code == 200 else poll.text
    }