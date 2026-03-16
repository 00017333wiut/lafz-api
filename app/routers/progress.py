import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth.dependencies import get_current_user
from app.models.progress import (
    ExerciseAttemptRequest,
    ExerciseAttemptResponse,
    LessonCompleteResponse,
    UserStatsResponse,
    get_proficiency_level
)
from app.database import get_db
import json

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/me", response_model=UserStatsResponse)
def get_my_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]

    profile = db.execute(
        text("SELECT * FROM user_profile WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    completed_lessons = db.execute(
        text("""
            SELECT COUNT(*) FROM user_progress
            WHERE user_id = :uid AND status = 'COMPLETED'
        """),
        {"uid": user_id}
    ).scalar()

    # A unit is completed if ALL its published lessons are completed
    units = db.execute(
        text("SELECT id FROM unit WHERE is_published = true")
    ).fetchall()

    completed_units = 0
    for unit in units:
        unit_id = unit[0]
        total = db.execute(
            text("SELECT COUNT(*) FROM lesson WHERE unit_id = :uid AND is_published = true"),
            {"uid": unit_id}
        ).scalar()
        done = db.execute(
            text("""
                SELECT COUNT(*) FROM user_progress up
                JOIN lesson l ON l.id = up.lesson_id
                WHERE l.unit_id = :unit_id
                AND up.user_id = :user_id
                AND up.status = 'COMPLETED'
            """),
            {"unit_id": unit_id, "user_id": user_id}
        ).scalar()
        if total > 0 and total == done:
            completed_units += 1

    total_exp = profile[6]  # total_exp column index

    return UserStatsResponse(
        user_id=user_id,
        email=current_user["email"],
        full_name=profile[2],
        total_exp=total_exp,
        proficiency_level=get_proficiency_level(total_exp),
        subscription_type=profile[3],
        completed_lessons=completed_lessons or 0,
        completed_units=completed_units
    )


@router.post("/exercises/{exercise_id}/attempt",
             response_model=ExerciseAttemptResponse)
def attempt_exercise(
    exercise_id: int,
    body: ExerciseAttemptRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]

    exercise = db.execute(
        text("SELECT * FROM exercise WHERE id = :eid"),
        {"eid": exercise_id}
    ).fetchone()

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    correct_answer = exercise[7]  # correct_answer column
    points = exercise[9]

    # Normalise both to strings for comparison
    user_ans = json.dumps(body.user_answer, sort_keys=True) \
        if isinstance(body.user_answer, dict) \
        else str(body.user_answer)
    correct_ans = json.dumps(correct_answer, sort_keys=True) \
        if isinstance(correct_answer, dict) \
        else str(correct_answer)

    is_correct = user_ans.strip().lower() == correct_ans.strip().lower()
    points_earned = points if is_correct else 0

    # Record the attempt
    db.execute(
        text("""
            INSERT INTO exercise_attempt
            (user_id, exercise_id, user_answer, is_correct, points_earned, attempted_at)
            VALUES (:uid, :eid, :ans, :correct, :pts, now())
        """),
        {
            "uid": user_id,
            "eid": exercise_id,
            "ans": json.dumps(body.user_answer),
            "correct": is_correct,
            "pts": points_earned
        }
    )
    db.commit()

    logger.info(f"User {user_id} attempted exercise {exercise_id} — correct: {is_correct}")

    return ExerciseAttemptResponse(
        is_correct=is_correct,
        points_earned=points_earned,
        correct_answer=correct_answer,
        feedback="Correct!" if is_correct else "Try again!"
    )


@router.post("/lessons/{lesson_id}/complete",
             response_model=LessonCompleteResponse)
def complete_lesson(
    lesson_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]

    # Check lesson exists
    lesson = db.execute(
        text("SELECT * FROM lesson WHERE id = :lid AND is_published = true"),
        {"lid": lesson_id}
    ).fetchone()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    exp_reward = lesson[8]

    # Upsert user_progress
    existing = db.execute(
        text("""
            SELECT id, status FROM user_progress
            WHERE user_id = :uid AND lesson_id = :lid
        """),
        {"uid": user_id, "lid": lesson_id}
    ).fetchone()

    if existing and existing[1] == "COMPLETED":
        # Already completed — don't award EXP again
        profile = db.execute(
            text("SELECT total_exp FROM user_profile WHERE id = :uid"),
            {"uid": user_id}
        ).fetchone()
        total_exp = profile[0]
        return LessonCompleteResponse(
            exp_earned=0,
            total_exp=total_exp,
            proficiency_level=get_proficiency_level(total_exp),
            milestones_achieved=[]
        )

    if existing:
        db.execute(
            text("""
                UPDATE user_progress
                SET status = 'COMPLETED',
                    completion_percentage = 100,
                    earned_exp = :exp,
                    completed_at = now(),
                    last_accessed_at = now()
                WHERE user_id = :uid AND lesson_id = :lid
            """),
            {"exp": exp_reward, "uid": user_id, "lid": lesson_id}
        )
    else:
        db.execute(
            text("""
                INSERT INTO user_progress
                (user_id, lesson_id, status, completion_percentage,
                 earned_exp, started_at, completed_at, last_accessed_at)
                VALUES (:uid, :lid, 'COMPLETED', 100, :exp, now(), now(), now())
            """),
            {"uid": user_id, "lid": lesson_id, "exp": exp_reward}
        )

    # Award EXP to user profile
    db.execute(
        text("""
            UPDATE user_profile
            SET total_exp = total_exp + :exp,
                last_active_at = now()
            WHERE id = :uid
        """),
        {"exp": exp_reward, "uid": user_id}
    )
    db.commit()

    # Get updated total EXP
    profile = db.execute(
        text("SELECT total_exp FROM user_profile WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    total_exp = profile[0]

    # Check milestones
    milestones_achieved = []
    milestones = db.execute(
        text("SELECT * FROM milestone")
    ).fetchall()

    for milestone in milestones:
        milestone_id = milestone[0]
        criteria = milestone[4]
        milestone_type = milestone[3]

        # Skip if already achieved
        already = db.execute(
            text("""
                SELECT id FROM user_milestone
                WHERE user_id = :uid AND milestone_id = :mid
            """),
            {"uid": user_id, "mid": milestone_id}
        ).fetchone()
        if already:
            continue

        achieved = False

        if milestone_type == "TOTAL_EXP":
            threshold = criteria.get("exp_threshold", 0)
            achieved = total_exp >= threshold

        elif milestone_type == "UNIT_COMPLETION":
            required = criteria.get("units_completed", 0)
            # Count completed units
            units = db.execute(
                text("SELECT id FROM unit WHERE is_published = true")
            ).fetchall()
            completed_units = 0
            for unit in units:
                unit_lessons = db.execute(
                    text("""
                        SELECT COUNT(*) FROM lesson
                        WHERE unit_id = :uid AND is_published = true
                    """),
                    {"uid": unit[0]}
                ).scalar()
                done = db.execute(
                    text("""
                        SELECT COUNT(*) FROM user_progress up
                        JOIN lesson l ON l.id = up.lesson_id
                        WHERE l.unit_id = :unit_id
                        AND up.user_id = :user_id
                        AND up.status = 'COMPLETED'
                    """),
                    {"unit_id": unit[0], "user_id": user_id}
                ).scalar()
                if unit_lessons > 0 and unit_lessons == done:
                    completed_units += 1
            achieved = completed_units >= required

        if achieved:
            bonus = milestone[6]
            db.execute(
                text("""
                    INSERT INTO user_milestone (user_id, milestone_id, achieved_at)
                    VALUES (:uid, :mid, now())
                """),
                {"uid": user_id, "mid": milestone_id}
            )
            if bonus > 0:
                db.execute(
                    text("""
                        UPDATE user_profile
                        SET total_exp = total_exp + :bonus
                        WHERE id = :uid
                    """),
                    {"bonus": bonus, "uid": user_id}
                )
            milestones_achieved.append(milestone[1])
            logger.info(f"User {user_id} achieved milestone: {milestone[1]}")

    db.commit()

    logger.info(f"User {user_id} completed lesson {lesson_id}, earned {exp_reward} EXP")

    return LessonCompleteResponse(
        exp_earned=exp_reward,
        total_exp=total_exp,
        proficiency_level=get_proficiency_level(total_exp),
        milestones_achieved=milestones_achieved
    )