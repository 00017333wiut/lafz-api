from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ExerciseAttemptRequest(BaseModel):
    user_answer: dict | str | list
    # Accepts any JSON shape — string for MC, dict for matching


class ExerciseAttemptResponse(BaseModel):
    is_correct: bool
    points_earned: int
    correct_answer: dict | str | list  # revealed after attempt
    feedback: Optional[str] = None


class LessonCompleteResponse(BaseModel):
    exp_earned: int
    total_exp: int
    proficiency_level: str
    milestones_achieved: List[str] = []


class UserStatsResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    total_exp: int
    proficiency_level: str
    subscription_type: str
    completed_lessons: int
    completed_units: int


def get_proficiency_level(exp: int) -> str:
    if exp < 300:   return "A1"
    if exp < 700:   return "A2"
    if exp < 1200:  return "B1"
    if exp < 2000:  return "B2"
    if exp < 3000:  return "C1"
    return "C2"