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