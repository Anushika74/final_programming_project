"""Tests for the context-aware AI Assistant and System Context Service."""
from __future__ import annotations


def test_context_endpoint(client, auth_headers):
    # Skip predictions for speed/determinism.
    resp = client.get("/api/v1/assistant/context?predictions=false", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "sources" in body
    assert "timestamp" in body


def test_assistant_health_summary(client, auth_headers):
    resp = client.post(
        "/api/v1/assistant/ask",
        headers=auth_headers,
        json={"query": "How is my system?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "health_summary"
    assert isinstance(body["sources"], list)
    assert len(body["answer"]) > 0


def test_assistant_intent_detection(client, auth_headers):
    cases = {
        "Why is my laptop slow?": "why_slow",
        "Which application is overheating my laptop?": "overheating_app",
        "Why is the fan spinning so fast?": "fan",
        "Is my battery degrading?": "battery_health",
        "Explain thermal throttling": "explain_concept",
        "What should I optimize first?": "what_optimize",
    }
    for query, expected in cases.items():
        resp = client.post(
            "/api/v1/assistant/ask", headers=auth_headers, json={"query": query}
        )
        assert resp.status_code == 200, query
        assert resp.json()["intent"] == expected, f"{query} -> {resp.json()['intent']}"


def test_assistant_explains_concepts(client, auth_headers):
    resp = client.post(
        "/api/v1/assistant/ask",
        headers=auth_headers,
        json={"query": "explain thermal throttling"},
    )
    assert resp.status_code == 200
    assert "throttl" in resp.json()["answer"].lower()
