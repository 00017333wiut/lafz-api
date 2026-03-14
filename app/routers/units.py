from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth.dependencies import get_current_user
from app.models.content import UnitResponse
from app.database import get_db
from typing import List

router = APIRouter()

@router.get("", response_model=List[UnitResponse])
def get_units(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]

    units = db.execute(
        text("SELECT * FROM unit WHERE is_published = true ORDER BY order_index")
    ).fetchall()

    if not units:
        return []

    completed = db.execute(
        text("""
            SELECT lesson_id FROM user_progress 
            WHERE user_id = :uid AND status = 'COMPLETED'
        """),
        {"uid": user_id}
    ).fetchall()
    completed_ids = set(row[0] for row in completed)

    lessons = db.execute(
        text("SELECT id, unit_id FROM lesson WHERE is_published = true")
    ).fetchall()
    lessons_by_unit = {}
    for lesson in lessons:
        lessons_by_unit.setdefault(lesson[1], []).append(lesson[0])

    response = []
    for i, unit in enumerate(units):
        if i == 0:
            is_locked = False
        else:
            prev_unit_id = units[i - 1][0]
            prev_lessons = lessons_by_unit.get(prev_unit_id, [])
            is_locked = not all(
                lid in completed_ids for lid in prev_lessons
            ) if prev_lessons else False

        response.append(UnitResponse(
            id=unit[0],
            order_index=unit[1],
            title=unit[3],
            description=unit[4],
            icon_url=unit[5],
            is_locked=is_locked
        ))

    return response