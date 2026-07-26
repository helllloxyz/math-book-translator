import json

import pytest

from app.services.agent_service import AgentService


class FakeSession:
    def __init__(self):
        self.objects = []
        self.commits = 0

    def add(self, obj):
        self.objects.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        obj.id = 123


def test_validate_tree_structure_normalizes_invalid_nodes():
    tree = AgentService._validate_tree_structure(
        {
            "title": "Root",
            "children": [
                {"title": "Missing Id", "children": "bad"},
                "skip me",
                {"id": "2"},
            ],
        }
    )

    assert tree["id"] == "0"
    assert tree["children"] == [
        {"id": "0", "title": "Missing Id", "children": []},
        {"id": "2", "title": "Untitled"},
    ]


def test_generate_preview_md_renders_vision_and_nested_toc():
    preview = AgentService._generate_preview_md(
        {
            "vision": {"audience": "undergraduates", "tone": "rigorous"},
            "tree": {
                "id": "root",
                "title": "Linear Algebra",
                "children": [
                    {
                        "id": "1",
                        "title": "Vectors",
                        "children": [{"id": "1.1", "title": "Span"}],
                    },
                    "ignored",
                ],
            },
        }
    )

    assert "#### Foundational Vision" in preview
    assert "- **audience**: undergraduates" in preview
    assert "- 1 Vectors" in preview
    assert "  - 1.1 Span" in preview
    assert "ignored" not in preview


def test_get_node_path_maps_dotted_node_ids_into_book_md(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    path = AgentService.get_node_path("book-uuid", "1.2.3", "Ignored Title")

    assert path == str(tmp_path / "book-uuid" / "book_md" / "1_2_3.md")


@pytest.mark.asyncio
async def test_initialize_agent_book_creates_manifest_and_history(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.agent_service.uuid.uuid4", lambda: "agent-book-uuid")
    db = FakeSession()

    book = await AgentService.initialize_agent_book("Linear Algebra", db)

    manifest_path = tmp_path / "agent-book-uuid" / "00_meta.json"
    history_path = tmp_path / "agent-book-uuid" / "history.jsonl"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    history_entries = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert book.id == 123
    assert book.uuid == "agent-book-uuid"
    assert book.original_filename == "Linear Algebra.agent"
    assert manifest == {
        "uuid": "agent-book-uuid",
        "title": "Linear Algebra",
        "type": "generated",
        "stage": "init",
        "vision": {},
        "tree": {"id": "root", "title": "Linear Algebra", "children": []},
    }
    assert history_entries[0]["command"] == "init"
    assert "Type `build` to begin architecting the landscape." in history_entries[0]["response"]
