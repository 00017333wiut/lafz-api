from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UnitResponse(BaseModel):
    id: int
    order_index: int
    title: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    is_locked: bool = False


class LessonResponse(BaseModel):
    id: int
    unit_id: int
    order_index: int
    lesson_type: str
    title: str
    subtitle: Optional[str] = None
    estimated_minutes: int
    exp_reward: int
    is_completed: bool = False


class LessonDetailResponse(BaseModel):
    id: int
    unit_id: int
    lesson_type: str
    title: str
    subtitle: Optional[str] = None
    theory_content: Optional[str] = None
    estimated_minutes: int
    exp_reward: int


class ExerciseResponse(BaseModel):
    id: int
    lesson_id: int
    order_index: int
    exercise_type: str
    question_text: str
    audio_url: Optional[str] = None
    options: Optional[list] = None
    points: int