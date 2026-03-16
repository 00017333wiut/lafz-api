import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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