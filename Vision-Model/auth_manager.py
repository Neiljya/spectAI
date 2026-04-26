import os
from dataclasses import dataclass
from typing import Optional

import dotenv
from supabase import Client, create_client

dotenv.load_dotenv()

@dataclass
class AuthContext:
    user_id: str
    email: str
    profile_id: str
    access_token: str = ""

def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY are required.")
    return create_client(url, key)

def resolve_profile_id(sb: Client, user_id: str) -> str:
    """
    profiles.id is expected to match auth.users.id.
    If no profile row exists yet, we still return the auth user id so foreign keys remain stable.
    """
    try:
        res = sb.table("profiles").select("id").eq("id", user_id).limit(1).execute()
        rows = res.data or []
        if rows:
            return rows[0]["id"]
    except Exception:
        pass
    return user_id

def sign_in_with_email_password(email: str, password: str) -> AuthContext:
    sb = get_supabase_client()
    auth_res = sb.auth.sign_in_with_password({"email": email, "password": password})
    user = getattr(auth_res, "user", None)
    if not user or not getattr(user, "id", None):
        raise RuntimeError("Supabase sign-in failed. Check email/password.")

    user_id = str(user.id)
    profile_id = resolve_profile_id(sb, user_id)
    access_token = str(auth_res.session.access_token) if auth_res.session else ""
    return AuthContext(user_id=user_id, email=email, profile_id=profile_id, access_token=access_token)

def try_sign_in(email: str, password: str) -> Optional[AuthContext]:
    try:
        return sign_in_with_email_password(email, password)
    except Exception as e:
        print(f"\n[Error Details]: {e}")
        return None

if __name__ == "__main__":
    import getpass
    print("=== Supabase Auth Standalone Test ===")
    test_email = input("Enter Supabase Email: ").strip()
    test_password = getpass.getpass("Enter Supabase Password: ")
    
    print("\nAttempting to connect to Supabase...")
    ctx = try_sign_in(test_email, test_password)
    
    if ctx:
        print(f"✅ SUCCESS! Logged in perfectly.")
        print(f"Profile ID mapped to: {ctx.profile_id}")
    else:
        print("❌ FAILED. Please double-check your email, password, and the API keys in your .env file.")
