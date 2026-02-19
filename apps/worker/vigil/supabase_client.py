"""
Supabase client for the Python worker.

Uses the SERVICE_ROLE key (not anon key) because:
1. This is a backend worker, not a browser client.
2. Service role bypasses RLS — needed for writing matches from the polling engine.
3. Never expose the service role key to the frontend.

The Next.js frontend uses the anon key with RLS policies.
"""

from supabase import create_client, Client
from vigil.config import settings

supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)
