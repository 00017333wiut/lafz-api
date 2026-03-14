from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from app.config import SUPABASE_URL

bearer_scheme = HTTPBearer()

# Cache the public keys — they rarely change
_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        response = httpx.get(url)
        _jwks_cache = response.json()
    return _jwks_cache

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            get_jwks(),
            algorithms=["ES256"],
            audience="authenticated"
        )

        user_id: str = payload.get("sub")
        email: str = payload.get("email")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user ID"
            )

        return {"user_id": user_id, "email": email}

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )