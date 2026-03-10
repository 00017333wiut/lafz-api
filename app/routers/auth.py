from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def auth_test():
    return {"router": "auth ok"}