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


@router.post("/exercises/{exercise_id}/attempt", response_model=ExerciseAttemptResponse)
def attempt_exercise(
    exercise_id: int,
    body: ExerciseAttemptRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    exercise = db.execute(text("SELECT * FROM exercise WHERE id = :eid"), {"eid": exercise_id}).fetchone()

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    correct_answer = exercise[7]
    points = exercise[9]
    exercise_type = exercise[3] # Make sure index 3 is exercise_type!

    user_ans_raw = body.user_answer

    # --- LOGIC START ---
    if exercise_type == "SPEAKING":
        if user_ans_raw == "skipped":
            is_correct = True
            points_earned = 0
            feedback_msg = "Skipped"
        else:
            is_correct = True
            points_earned = points
            feedback_msg = "Great speaking!"
    else:
        # Standard logic for Multiple Choice / Spelling
        user_ans = str(user_ans_raw).strip().lower()
        correct_ans = str(correct_answer).strip().lower()
        is_correct = (user_ans == correct_ans)
        points_earned = points if is_correct else 0
        feedback_msg = "Correct!" if is_correct else "Try again!"
    # --- LOGIC END ---

    # Record the attempt
    db.execute(
        text("""
            INSERT INTO exercise_attempt 
            (user_id, exercise_id, user_answer, is_correct, points_earned, attempted_at)
            VALUES (:uid, :eid, :ans, :correct, :pts, now())
        """),
        {
            "uid": user_id, "eid": exercise_id,
            "ans": json.dumps(user_ans_raw), "correct": is_correct, "pts": points_earned
        }
    )
    db.commit()

    return ExerciseAttemptResponse(
        is_correct=is_correct,
        points_earned=points_earned,
        correct_answer=correct_answer,
        feedback=feedback_msg,
        answer_explanation=exercise[8]
    )

@router.get("/achievements")
def get_achievements(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]

    all_milestones = db.execute(
        text("SELECT id, title, description, milestone_type, exp_bonus FROM milestone")
    ).fetchall()

    achieved = db.execute(
        text("SELECT milestone_id FROM user_milestone WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchall()

    achieved_ids = [row[0] for row in achieved]

    return {
        "all_milestones": [
            {
                "id": m[0],
                "title": m[1],
                "description": m[2],
                "milestone_type": m[3],
                "exp_bonus": m[4]
            }
            for m in all_milestones
        ],
        "achieved_ids": achieved_ids
    }

@router.post("/lessons/{lesson_id}/complete",
             response_model=LessonCompleteResponse)
def complete_lesson(
    lesson_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    is_perfect: bool = False  # query param: /lessons/1/complete?is_perfect=true
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
    milestones = db.execute(text("SELECT * FROM milestone")).fetchall()

    # Get stats needed for milestone checks
    completed_lessons_count = db.execute(
        text("""
            SELECT COUNT(*) FROM user_progress
            WHERE user_id = :uid AND status = 'COMPLETED'
        """),
        {"uid": user_id}
    ).scalar()

    units = db.execute(
        text("SELECT id FROM unit WHERE is_published = true")
    ).fetchall()

    completed_units_count = 0
    for unit in units:
        unit_lessons_total = db.execute(
            text("SELECT COUNT(*) FROM lesson WHERE unit_id = :uid AND is_published = true"),
            {"uid": unit[0]}
        ).scalar()
        unit_lessons_done = db.execute(
            text("""
                SELECT COUNT(*) FROM user_progress up
                JOIN lesson l ON l.id = up.lesson_id
                WHERE l.unit_id = :unit_id
                AND up.user_id = :user_id
                AND up.status = 'COMPLETED'
            """),
            {"unit_id": unit[0], "user_id": user_id}
        ).scalar()
        if unit_lessons_total > 0 and unit_lessons_total == unit_lessons_done:
            completed_units_count += 1

    for milestone in milestones:
        milestone_id = milestone[0]
        milestone_title = milestone[1]
        milestone_type = milestone[3]
        criteria = milestone[4]
        exp_bonus = milestone[6]

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
            # Handle both exp threshold and perfect lesson
            if "exp_threshold" in criteria:
                achieved = total_exp >= criteria["exp_threshold"]
            elif "perfect_lesson" in criteria:
                achieved = is_perfect  # passed in from endpoint

        elif milestone_type == "UNIT_COMPLETION":
            if "lessons_completed" in criteria:
                achieved = completed_lessons_count >= criteria["lessons_completed"]
            elif "units_completed" in criteria:
                achieved = completed_units_count >= criteria["units_completed"]

        if achieved:
            db.execute(
                text("""
                    INSERT INTO user_milestone (user_id, milestone_id, achieved_at)
                    VALUES (:uid, :mid, now())
                """),
                {"uid": user_id, "mid": milestone_id}
            )
            if exp_bonus > 0:
                db.execute(
                    text("""
                        UPDATE user_profile
                        SET total_exp = total_exp + :bonus
                        WHERE id = :uid
                    """),
                    {"bonus": exp_bonus, "uid": user_id}
                )
                total_exp += exp_bonus
            milestones_achieved.append(milestone_title)
            logger.info(f"User {user_id} achieved milestone: {milestone_title}")

    db.commit()

    logger.info(f"User {user_id} completed lesson {lesson_id}, earned {exp_reward} EXP")

    return LessonCompleteResponse(
        exp_earned=exp_reward,
        total_exp=total_exp,
        proficiency_level=get_proficiency_level(total_exp),
        milestones_achieved=milestones_achieved
    )