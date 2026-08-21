"""
Single shared Supabase client used across the whole app.
Import `supabase` from here anywhere you need to read/write the database.
"""
import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set (see .env.example)."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
