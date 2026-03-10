from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def units_test():
    return {"router": "units ok"}