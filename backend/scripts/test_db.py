import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db import engine
from app.core.config import settings

def run_diagnostics():
    print("=" * 60)
    print(" Supabase Database Connection Diagnostics")
    print("=" * 60)

    raw_url = settings.database_url
    print("\n[1] Configured DATABASE_URL:")
    try:
        scheme, rest = raw_url.split("://", 1)
        if "@" in rest:
            userinfo, hostinfo = rest.rsplit("@", 1)
            if ":" in userinfo:
                user, _ = userinfo.split(":", 1)
                masked_url = f"{scheme}://{user}:******@{hostinfo}"
            else:
                masked_url = f"{scheme}://{userinfo}:******@{hostinfo}"
        else:
            masked_url = raw_url
        print(f"    URL: {masked_url}")
    except Exception:
        print("    (URL loaded from .env)")

    # Check for unencoded special characters in password
    print("\n[2] Checking Connection String Format:")
    if raw_url.count("@") > 1:
        print("    [WARNING] Found multiple '@' characters in DATABASE_URL.")
        print("       Your password appears to contain '@' (e.g. starts with '@').")
        print("       While app.db.normalize_database_url() handles this for the FastAPI app,")
        print("       external tools (psql, DBeaver, Prisma, etc.) will misinterpret this as")
        print("       the host name and fail with: 'failed to resolve host getaddrinfo failed'.")
        print("       -> Recommendation: URL-encode '@' as '%40' in backend/.env.")
    else:
        print("    [OK] Connection string formatting looks standard.")

    # Test live connection
    print("\n[3] Testing Live Database Connection...")
    start_time = time.time()
    try:
        with engine.connect() as conn:
            elapsed = (time.time() - start_time) * 1000
            print(f"    [OK] Connected successfully in {elapsed:.1f}ms!")
            
            # Query server info
            version = conn.execute(text("SELECT version();")).scalar()
            curr_user = conn.execute(text("SELECT current_user;")).scalar()
            curr_db = conn.execute(text("SELECT current_database();")).scalar()
            
            print(f"\n[4] Database Details:")
            print(f"    - Current User: {curr_user}")
            print(f"    - Current DB:   {curr_db}")
            print(f"    - PG Version:   {version}")
            print("\n[SUCCESS] Supabase connection is healthy and working properly!")
            print("=" * 60)
            return True

    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        print(f"    [FAILED] Connection failed after {elapsed:.1f}ms")
        print(f"\n[ERROR DETAILS]")
        print(f"    Type: {type(exc).__name__}")
        print(f"    Message: {exc}\n")

        print("[TROUBLESHOOTING GUIDE]")
        err_str = str(exc).lower()
        if "getaddrinfo failed" in err_str or "could not translate host name" in err_str:
            print("  * Host Resolution / DNS Failure:")
            print("    Check if your password contains '@'. If your password has '@', it MUST be")
            print("    URL-encoded as '%40' in your .env file.")
        elif "password authentication failed" in err_str:
            print("  * Authentication Failure:")
            print("    The password provided in .env does not match your Supabase database password.")
            print("    Reset your database password in the Supabase Dashboard under Project Settings > Database.")
        elif "timeout" in err_str or "timed out" in err_str or "connection refused" in err_str:
            print("  * Network / Project Inactivity:")
            print("    1. Is your Supabase project paused? Log into supabase.com to unpause it.")
            print("    2. If using direct connection (db.<ref>.supabase.co:5432), ensure IPv6 is supported")
            print("       or use the Supabase Connection Pooler (aws-0-*.pooler.supabase.com:5432).")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = run_diagnostics()
    sys.exit(0 if success else 1)
