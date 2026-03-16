from fastapi import APIRouter, HTTPException
from app.models.user import RegisterRequest, LoginRequest, AuthResponse
from app.database import supabase
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    try:
        result = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {"full_name": body.full_name}
            }
        })

        if result.user is None:
            raise HTTPException(status_code=400, detail="Registration failed")

        # Try to update full_name but don't fail if DB is unavailable
        try:
            from app.database import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(
                    text("UPDATE user_profile SET full_name = :name WHERE id = :uid"),
                    {"name": body.full_name, "uid": str(result.user.id)}
                )
                conn.commit()
        except Exception as db_err:
            logger.warning(f"Could not update full_name after register: {db_err}")

        return AuthResponse(
            access_token=result.session.access_token,
            user_id=str(result.user.id),
            email=result.user.email,
            full_name=body.full_name
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    try:
        result = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })

        if result.user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Try to get full_name but don't fail if DB is unavailable
        full_name = None
        try:
            profile = supabase.table("user_profile").select(
                "full_name"
            ).eq("id", str(result.user.id)).single().execute()
            full_name = profile.data.get("full_name") if profile.data else None
        except Exception:
            pass  # non-critical, continue without full_name

        return AuthResponse(
            access_token=result.session.access_token,
            user_id=str(result.user.id),
            email=result.user.email,
            full_name=full_name
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))