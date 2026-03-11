from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

print(f"Connecting to: {SUPABASE_URL}")
print(f"Key starts with: {SUPABASE_SERVICE_KEY[:20] if SUPABASE_SERVICE_KEY else 'MISSING'}")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)