import json

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routers import settings as settings_router


def _settings_client():
    app = FastAPI()
    app.include_router(settings_router.router)
    return TestClient(app)


def test_get_quick_inputs_reads_config_file(tmp_path, monkeypatch):
    inputs_path = tmp_path / "quick-inputs.json"
    inputs_path.write_text(
        json.dumps(
            [
                {
                    "id": "concise",
                    "label": "Concise",
                    "prompt": "Be brief.",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_router, "QUICK_INPUTS_PATH", inputs_path)

    with _settings_client() as client:
        response = client.get("/settings/quick-inputs")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "concise",
            "label": "Concise",
            "prompt": "Be brief.",
        }
    ]


def test_put_quick_inputs_validates_and_persists_normalized_inputs(tmp_path, monkeypatch):
    inputs_path = tmp_path / "config" / "quick-inputs.json"
    monkeypatch.setattr(settings_router, "QUICK_INPUTS_PATH", inputs_path)

    payload = [
        {
            "id": "  detail_1 ",
            "label": " Detailed ",
            "prompt": " Explain fully. ",
        },
        {"id": "simple", "label": "Simple", "prompt": "Use direct language."},
    ]

    with _settings_client() as client:
        response = client.put("/settings/quick-inputs", json=payload)

    assert response.status_code == 200
    expected = [
        {
            "id": "detail_1",
            "label": "Detailed",
            "prompt": "Explain fully.",
        },
        {"id": "simple", "label": "Simple", "prompt": "Use direct language."},
    ]
    assert response.json() == expected
    assert json.loads(inputs_path.read_text(encoding="utf-8")) == expected


def test_put_quick_inputs_rejects_duplicate_or_unsafe_ids(tmp_path, monkeypatch):
    inputs_path = tmp_path / "quick-inputs.json"
    monkeypatch.setattr(settings_router, "QUICK_INPUTS_PATH", inputs_path)

    with _settings_client() as client:
        duplicate_response = client.put(
            "/settings/quick-inputs",
            json=[
                {"id": "simple", "label": "Simple", "prompt": "A"},
                {"id": "simple", "label": "Simple 2", "prompt": "B"},
            ],
        )
        unsafe_response = client.put(
            "/settings/quick-inputs",
            json=[{"id": "../bad", "label": "Bad", "prompt": "No"}],
        )
        extra_field_response = client.put(
            "/settings/quick-inputs",
            json=[{"id": "simple", "label": "Simple", "prompt": "A", "extra": "No"}],
        )

    assert duplicate_response.status_code == 422
    assert unsafe_response.status_code == 422
    assert extra_field_response.status_code == 422
    assert not inputs_path.exists()
