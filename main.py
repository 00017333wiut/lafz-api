from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import get_current_user
from app.routers import auth, units, lessons, progress
from app.database import supabase

app = FastAPI(title="Lafz API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lafz-backend-service-production.up.railway.app",
        "http://10.0.2.2:8000",  # Android emulator localhost
        "http://localhost:8000",  # local testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ─────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# ── Routers ───────────────────────────────────
app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(units.router,    prefix="/units",    tags=["units"])
app.include_router(lessons.router,  prefix="/lessons",  tags=["lessons"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])

@app.get("/health")
def health():
    try:
        supabase.table("user_profile").select("id").limit(1).execute()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "ok", "database": "error", "detail": str(e)}

@app.get("/protected-test")
def protected_test(current_user: dict = Depends(get_current_user)):
    return {
        "message": "you are authenticated",
        "user_id": current_user["user_id"],
        "email": current_user["email"]
    }