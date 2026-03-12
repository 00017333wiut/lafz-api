from fastapi import APIRouter, HTTPException
from app.models.user import RegisterRequest, LoginRequest, AuthResponse
from app.database import supabase

router = APIRouter()


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    try:
        # Register with Supabase Auth
        result = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {"full_name": body.full_name}
            }
        })

        if result.user is None:
            raise HTTPException(status_code=400, detail="Registration failed")

        # update full_name in user_profile
        # (trigger already created the row, we just update the name)
        supabase.table("user_profile").update(
            {"full_name": body.full_name}
        ).eq("id", str(result.user.id)).execute()

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