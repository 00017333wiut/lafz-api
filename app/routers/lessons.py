from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def lessons_test():
    return {"router": "lessons ok"}