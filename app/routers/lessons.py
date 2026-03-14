from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth.dependencies import get_current_user
from app.models.content import LessonResponse, LessonDetailResponse, ExerciseResponse
from app.database import get_db
from typing import List

router = APIRouter()

@router.get("/unit/{unit_id}", response_model=List[LessonResponse])
def get_lessons_by_unit(
    unit_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]

    lessons = db.execute(
        text("""
            SELECT * FROM lesson 
            WHERE unit_id = :uid AND is_published = true 
            ORDER BY order_index
        """),
        {"uid": unit_id}
    ).fetchall()

    if not lessons:
        return []

    progress = db.execute(
        text("""
            SELECT lesson_id, status FROM user_progress 
            WHERE user_id = :uid
        """),
        {"uid": user_id}
    ).fetchall()
    progress_map = {row[0]: row[1] for row in progress}

    return [
        LessonResponse(
            id=l[0],
            unit_id=l[1],
            order_index=l[2],
            lesson_type=l[3],
            title=l[4],
            subtitle=l[5],
            estimated_minutes=l[7],
            exp_reward=l[8],
            is_completed=progress_map.get(l[0]) == "COMPLETED"
        )
        for l in lessons
    ]


@router.get("/{lesson_id}", response_model=LessonDetailResponse)
def get_lesson_detail(
    lesson_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = db.execute(
        text("""
            SELECT * FROM lesson 
            WHERE id = :lid AND is_published = true
        """),
        {"lid": lesson_id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Lesson not found")

    return LessonDetailResponse(
        id=result[0],
        unit_id=result[1],
        lesson_type=result[3],
        title=result[4],
        subtitle=result[5],
        theory_content=result[6],
        estimated_minutes=result[7],
        exp_reward=result[8]
    )


@router.get("/{lesson_id}/exercises", response_model=List[ExerciseResponse])
def get_exercises(
    lesson_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    results = db.execute(
        text("""
            SELECT * FROM exercise 
            WHERE lesson_id = :lid 
            ORDER BY order_index
        """),
        {"lid": lesson_id}
    ).fetchall()

    if not results:
        return []

    return [
        ExerciseResponse(
            id=ex[0],
            lesson_id=ex[1],
            order_index=ex[2],
            exercise_type=ex[3],
            question_text=ex[4],
            audio_url=ex[5],
            options=ex[6],
            points=ex[9]
        )
        for ex in results
    ]