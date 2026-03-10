from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import supabase
from app.routers import auth, units, lessons, progress

app = FastAPI(title="Uzbek Learning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(units.router,    prefix="/units",    tags=["units"])
app.include_router(lessons.router,  prefix="/lessons",  tags=["lessons"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])

@app.get("/health")
def health():
    try:
        # Tries to read one row from user_profile — proves DB is reachable
        supabase.table("user_profile").select("id").limit(1).execute()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "ok", "database": "error", "detail": str(e)}