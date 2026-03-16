import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ── Helper ────────────────────────────────────
def get_valid_token():
    response = client.post("/auth/login", json={
        "email": "thienrylsoptessi@gmail.com",
        "password": "string"
    })
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return response.json()["access_token"]

# ── Tests ─────────────────────────────────────
def test_get_units_unauthenticated():
    """Should reject requests with no token."""
    response = client.get("/units")
    assert response.status_code == 401


def test_get_units_authenticated():
    """Should return list of units for valid token."""
    token = get_valid_token()
    response = client.get(
        "/units",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_exercises_invalid_lesson():
    """Should return empty list for non-existent lesson."""
    token = get_valid_token()
    response = client.get(
        "/lessons/99999/exercises",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == []

def test_get_my_stats():
    """Should return user stats with proficiency level."""
    token = get_valid_token()
    response = client.get(
        "/progress/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_exp" in data
    assert "proficiency_level" in data
    assert data["proficiency_level"] in ["A1","A2","B1","B2","C1","C2"]


def test_complete_lesson():
    """Should award EXP on lesson completion."""
    token = get_valid_token()
    # Get stats before
    before = client.get(
        "/progress/me",
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    # Complete lesson 1
    response = client.post(
        "/progress/lessons/1/complete",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "exp_earned" in data
    assert "proficiency_level" in data


def test_complete_lesson_twice_no_double_exp():
    """Completing same lesson twice should not award EXP twice."""
    token = get_valid_token()

    first = client.post(
        "/progress/lessons/1/complete",
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    second = client.post(
        "/progress/lessons/1/complete",
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert second["exp_earned"] == 0


def test_attempt_exercise_wrong_answer():
    """Wrong answer should return is_correct false and 0 points."""
    token = get_valid_token()
    response = client.post(
        "/progress/exercises/1/attempt",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_answer": "wrong answer"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] == False
    assert data["points_earned"] == 0