import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.schema import Chapter
from app.services.agent_manifest_repo import AgentManifestRepo
from app.services.agent_service import AgentService
from app.services.agent_writer_runner import AgentWriterRunner


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _FakeExecuteResult:
    def __init__(self, payload):
        self._payload = payload

    def scalar_one_or_none(self):
        return self._payload

    def scalars(self):
        return _FakeScalarResult(self._payload)


class FakeSession:
    def __init__(self, *, book=None, chapters=None):
        self.book = book
        self.chapters = list(chapters or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshed = []

    async def execute(self, stmt):
        text = str(stmt)
        if "FROM books" in text:
            return _FakeExecuteResult(self.book)
        if "FROM chapters" in text:
            return _FakeExecuteResult(self.chapters)
        raise AssertionError(f"Unexpected statement: {stmt}")

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Chapter):
            self.chapters.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)
        self.chapters = [chapter for chapter in self.chapters if chapter is not obj]

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 100 + len(self.refreshed)


@pytest.mark.asyncio
async def test_manifest_repo_sync_manifest_to_db_reconciles_file_nodes():
    book = SimpleNamespace(id=7, uuid="book-uuid")
    existing_keep = Chapter(book_id=7, chapter_index="1.0.0", title_en="Old Intro", order=9)
    existing_drop = Chapter(book_id=7, chapter_index="9.9.9", title_en="Remove Me", order=10)
    db = FakeSession(book=book, chapters=[existing_keep, existing_drop])
    manifest = {
        "tree": {
            "id": "root",
            "title": "Discrete Math",
            "children": [
                {"id": "1.0.0", "title": "Origins", "type": "file"},
                {
                    "id": "2.0.0",
                    "title": "Structures",
                    "type": "dir",
                    "children": [
                        {"id": "2.1", "title": "Sets", "type": "file"},
                        {"id": "2.2", "title": "Relations", "type": "file"},
                    ],
                },
            ],
        }
    }

    await AgentManifestRepo.sync_manifest_to_db(book, manifest, db)

    assert existing_keep.title_en == "Origins"
    assert existing_keep.order == 0
    assert [chapter.chapter_index for chapter in db.chapters] == ["1.0.0", "2.1", "2.2"]
    assert [chapter.title_en for chapter in db.chapters] == ["Origins", "Sets", "Relations"]
    assert db.deleted == [existing_drop]


@pytest.mark.asyncio
async def test_writer_runner_writes_node_content_with_book_storage_path(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    path = await AgentWriterRunner.write_node_content("book-uuid", "4.1", "Ignored", "# Generated")

    assert path == tmp_path / "book-uuid" / "book_md" / "4_1.md"
    assert path.read_text(encoding="utf-8") == "# Generated"


def test_writer_runner_collects_file_nodes_depth_first():
    tree = {
        "id": "root",
        "children": [
            {"id": "1.0.0", "title": "Origins", "type": "file"},
            {
                "id": "2.0.0",
                "title": "Structures",
                "type": "dir",
                "children": [
                    {"id": "2.1", "title": "Sets", "type": "file"},
                    {"id": "2.2", "title": "Relations", "type": "file"},
                ],
            },
        ],
    }

    nodes = AgentWriterRunner.collect_file_nodes(tree)

    assert [node["id"] for node in nodes] == ["1.0.0", "2.1", "2.2"]


@pytest.mark.asyncio
async def test_agent_service_initialize_agent_book_delegates_to_orchestrator(monkeypatch):
    expected = object()

    async def fake_initialize_agent_book(title, db):
        assert title == "Graph Theory"
        assert db is marker
        return expected

    marker = object()
    monkeypatch.setattr(
        "app.services.agent_service.AgentOrchestrator.initialize_agent_book",
        fake_initialize_agent_book,
    )

    result = await AgentService.initialize_agent_book("Graph Theory", marker)

    assert result is expected


@pytest.mark.asyncio
async def test_manifest_repo_persists_and_loads_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    manifest = {"uuid": "book-uuid", "title": "Topology", "tree": {"id": "root", "children": []}}

    await AgentManifestRepo.save_manifest("book-uuid", manifest)
    loaded = await AgentManifestRepo.load_manifest("book-uuid")

    assert loaded == manifest
    assert json.loads((tmp_path / "book-uuid" / "00_meta.json").read_text(encoding="utf-8")) == manifest
