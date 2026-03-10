from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def progress_test():
    return {"router": "progress ok"}