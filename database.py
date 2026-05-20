"""
Conexión a Supabase
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_supabase: Client = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")  # service role for backend
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase = create_client(url, key)
    return _supabase
