from supabase import create_client
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, DATABASE_URL

# Keep supabase client for Auth only
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Use SQLAlchemy for all DB queries
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()