import json

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routers import settings as settings_router


def _settings_client():
    app = FastAPI()
    app.include_router(settings_router.router)
    return TestClient(app)


def test_get_conversation_styles_reads_config_file(tmp_path, monkeypatch):
    styles_path = tmp_path / "conversation-styles.json"
    styles_path.write_text(
        json.dumps(
            [
                {
                    "id": "concise",
                    "label": "Concise",
                    "description": "Short answers",
                    "prompt": "Be brief.",
                    "ignored": "value",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_router, "CONVERSATION_STYLES_PATH", styles_path, raising=False)

    with _settings_client() as client:
        response = client.get("/settings/conversation-styles")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "concise",
            "label": "Concise",
            "description": "Short answers",
            "prompt": "Be brief.",
        }
    ]


def test_put_conversation_styles_validates_and_persists_normalized_styles(tmp_path, monkeypatch):
    styles_path = tmp_path / "config" / "conversation-styles.json"
    monkeypatch.setattr(settings_router, "CONVERSATION_STYLES_PATH", styles_path, raising=False)

    payload = [
        {
            "id": "  detail_1 ",
            "label": " Detailed ",
            "description": " Expand ideas ",
            "prompt": " Explain fully. ",
        },
        {"id": "simple", "label": "Simple", "prompt": "Use direct language."},
    ]

    with _settings_client() as client:
        response = client.put("/settings/conversation-styles", json=payload)

    assert response.status_code == 200
    expected = [
        {
            "id": "detail_1",
            "label": "Detailed",
            "description": "Expand ideas",
            "prompt": "Explain fully.",
        },
        {"id": "simple", "label": "Simple", "description": "", "prompt": "Use direct language."},
    ]
    assert response.json() == expected
    assert json.loads(styles_path.read_text(encoding="utf-8")) == expected


def test_put_conversation_styles_rejects_duplicate_or_unsafe_ids(tmp_path, monkeypatch):
    styles_path = tmp_path / "conversation-styles.json"
    monkeypatch.setattr(settings_router, "CONVERSATION_STYLES_PATH", styles_path, raising=False)

    with _settings_client() as client:
        duplicate_response = client.put(
            "/settings/conversation-styles",
            json=[
                {"id": "simple", "label": "Simple", "prompt": "A"},
                {"id": "simple", "label": "Simple 2", "prompt": "B"},
            ],
        )
        unsafe_response = client.put(
            "/settings/conversation-styles",
            json=[{"id": "../bad", "label": "Bad", "prompt": "No"}],
        )

    assert duplicate_response.status_code == 422
    assert unsafe_response.status_code == 422
    assert not styles_path.exists()
