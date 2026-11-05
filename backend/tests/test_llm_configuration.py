from fastapi.testclient import TestClient

from app.main import create_app


def test_gemini_mode_fails_closed_when_api_key_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("PAYPOOL_LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with TestClient(create_app()) as client:
        response = client.post("/api/v1/procurement/parse", json={"message": "need rice"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LLM_UNAVAILABLE"
