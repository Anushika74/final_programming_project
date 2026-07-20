"""Tests for authentication and role-based access control."""
from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_admin_login(client):
    resp = client.post(
        "/api/v1/auth/login/json",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"


def test_login_rejects_bad_password(client):
    resp = client.post(
        "/api/v1/auth/login/json",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_register_creates_standard_user(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "user"


def test_protected_route_requires_token(client):
    assert client.get("/api/v1/metrics/current").status_code == 401


def test_me_returns_current_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_non_admin_cannot_list_users(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
    )
    token = client.post(
        "/api/v1/auth/login/json",
        json={"username": "bob", "password": "secret123"},
    ).json()["access_token"]
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
