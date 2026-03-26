from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL      = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
UZBEKVOICE_API_KEY = os.getenv("UZBEKVOICE_API_KEY")
SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1"