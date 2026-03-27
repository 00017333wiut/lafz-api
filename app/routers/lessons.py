from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import markdown
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth.dependencies import get_current_user
from app.models.content import LessonResponse, LessonDetailResponse, ExerciseResponse
from app.database import get_db
from typing import List
from app.services.tts_service import generate_and_store_audio

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

    raw_md = result[6]  # theory_content column
    html_content = markdown.markdown(raw_md, extensions=["extra", "tables"]) if raw_md else None

    return LessonDetailResponse(
        id=result[0],
        unit_id=result[1],
        lesson_type=result[3],
        title=result[4],
        subtitle=result[5],
        theory_content=html_content,   # send HTML instead of Markdown
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

@router.post("/{lesson_id}/exercises/{exercise_id}/generate-audio")
def generate_exercise_audio(
    lesson_id: int,
    exercise_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate TTS audio for an exercise question if not already stored.
    Called once per exercise — subsequent calls return the cached URL.
    """
    exercise = db.execute(
        text("SELECT * FROM exercise WHERE id = :eid AND lesson_id = :lid"),
        {"eid": exercise_id, "lid": lesson_id}
    ).fetchone()

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    # Return existing URL if already generated
    existing_url = exercise[5]  # audio_url column
    if existing_url:
        return {"audio_url": existing_url}

    # Generate new audio
    question_text = exercise[4]  # question_text column
    filename = f"exercise_{exercise_id}.mp3"

    audio_url = generate_and_store_audio(question_text, filename)

    if not audio_url:
        raise HTTPException(status_code=500, detail="Audio generation failed")

    # Store URL in DB so we never generate again
    db.execute(
        text("UPDATE exercise SET audio_url = :url WHERE id = :eid"),
        {"url": audio_url, "eid": exercise_id}
    )
    db.commit()

    return {"audio_url": audio_url}

@router.post("/{lesson_id}/generate-all-audio")
def generate_all_lesson_audio(
    lesson_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exercises = db.execute(
        text("""
            SELECT id, question_text, audio_url 
            FROM exercise 
            WHERE lesson_id = :lid
        """),
        {"lid": lesson_id}
    ).fetchall()

    pending = [(ex[0], ex[1]) for ex in exercises if not ex[2]]

    if not pending:
        return {"message": "All exercises already have audio", "count": 0}

    # Return immediately — process audio in background
    background_tasks.add_task(process_audio_batch, pending)

    return {
        "message": f"Generating audio for {len(pending)} exercises in background",
        "count": len(pending)
    }


def process_audio_batch(exercises: list):
    """Runs in background — generates and stores audio for each exercise."""
    from app.database import SessionLocal
    from app.services.tts_service import generate_and_store_audio
    import logging

    logger = logging.getLogger(__name__)
    db = SessionLocal()

    try:
        for ex_id, question_text in exercises:
            logger.info(f"Generating audio for exercise {ex_id}: {question_text}")
            filename = f"exercise_{ex_id}.mp3"
            url = generate_and_store_audio(question_text, filename)

            if url:
                db.execute(
                    text("UPDATE exercise SET audio_url = :url WHERE id = :eid"),
                    {"url": url, "eid": ex_id}
                )
                db.commit()
                logger.info(f"Exercise {ex_id} audio saved: {url}")
            else:
                logger.error(f"Exercise {ex_id} audio generation failed")
    except Exception as e:
        logger.error(f"Batch audio generation error: {e}")
    finally:
        db.close()


@router.post("/test-tts")
def test_tts(current_user: dict = Depends(get_current_user)):
    import httpx
    from app.config import UZBEKVOICE_API_KEY

    response = httpx.post(
        "https://uzbekvoice.ai/api/v1/tts",
        headers={
            "Authorization": UZBEKVOICE_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": "Salom",
            "model": "dilfuza-neutral",
            "blocking": True
        },
        timeout=30
    )

    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "content_length": len(response.content),
        "response_text": response.text[:500],  # first 500 chars
        "headers": dict(response.headers)
    }

