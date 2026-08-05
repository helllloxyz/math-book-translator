from app.services.reader_tree_service import ReaderTreeService


class Chapter:
    def __init__(self, id, chapter_index, title_en, order):
        self.id = id
        self.chapter_index = chapter_index
        self.title_en = title_en
        self.title_zh = None
        self.order = order


def titles(nodes):
    return [node["title"] for node in nodes]


def test_book_tree_uses_directories_for_chapters_with_children_and_content_leaf():
    chapters = [
        Chapter(1, "0", "Pre Content", 0),
        Chapter(2, "1", "Chapter 1", 1),
        Chapter(3, "1.1", "c 1.1", 2),
        Chapter(4, "1.1.1", "c 1.1.1", 3),
        Chapter(5, "1.2", "c 1.2", 4),
        Chapter(6, "2", "Chapter 2", 5),
        Chapter(7, "2.1", "c 2.1", 6),
        Chapter(8, "2.2", "c 2.2", 7),
    ]

    tree = ReaderTreeService.build_book_tree(chapters)

    assert titles(tree) == ["Pre Content", "Chapter 1", "Chapter 2"]
    assert tree[0]["kind"] == "leaf"
    assert tree[0]["source_type"] == "chapter_content"
    assert tree[0]["source_id"] == "chapter:1"

    chapter_1 = tree[1]
    assert chapter_1["kind"] == "directory"
    assert titles(chapter_1["children"]) == ["Chapter 1 content", "c 1.1", "c 1.2"]
    assert chapter_1["children"][0]["kind"] == "leaf"
    assert chapter_1["children"][0]["chapter_id"] == 2
    assert chapter_1["children"][1]["kind"] == "directory"
    assert titles(chapter_1["children"][1]["children"]) == ["c 1.1 content", "c 1.1.1"]
    assert chapter_1["children"][2]["kind"] == "leaf"


def test_book_tree_keeps_chapters_when_parent_index_is_missing():
    chapters = [
        Chapter(11, "1.1", "c 1.1", 1),
        Chapter(12, "1.2", "c 1.2", 2),
    ]

    tree = ReaderTreeService.build_book_tree(chapters)

    assert titles(tree) == ["1"]
    assert tree[0]["kind"] == "directory"
    assert tree[0]["chapter_index"] == "1"
    assert titles(tree[0]["children"]) == ["c 1.1", "c 1.2"]


def test_book_tree_sorts_mixed_missing_parent_indexes_without_type_error():
    chapters = [
        Chapter(21, "A.1", "appendix child", 1),
        Chapter(22, "1.1", "numeric child", 2),
    ]

    tree = ReaderTreeService.build_book_tree(chapters)

    assert titles(tree) == ["1", "A"]
    assert titles(tree[0]["children"]) == ["numeric child"]
    assert titles(tree[1]["children"]) == ["appendix child"]


def test_guide_tree_omits_empty_directories_when_no_guides_exist():
    chapters = [
        Chapter(11, "1.1", "c 1.1", 1),
        Chapter(12, "1.2", "c 1.2", 2),
    ]

    tree = ReaderTreeService.build_guide_tree(chapters, [])

    assert tree == []


def test_guide_tree_contains_only_generated_guides():
    chapters = [
        Chapter(10, "1", "Chapter 1", 1),
        Chapter(11, "1.1", "c 1.1", 2),
        Chapter(12, "1.1.1", "c 1.1.1", 3),
        Chapter(13, "1.2", "c 1.2", 4),
        Chapter(20, "2", "Chapter 2", 5),
    ]
    guides = [
        {
            "id": "guide:book-overview.md",
            "filename": "book-overview.md",
            "title": "Book Overview",
            "scope_type": "book",
            "scope_id": "book",
            "source_type": "book_guide",
            "source_id": "guide:book:book-overview",
        },
        {
            "id": "guide:chapter-1-map.md",
            "filename": "chapter-1-map.md",
            "title": "Guides 0",
            "scope_type": "directory",
            "scope_id": "1",
            "source_type": "directory_guide",
            "source_id": "guide:directory:1:map",
        },
        {
            "id": "guide:chapter-1_1_1-map.md",
            "filename": "chapter-1_1_1-map.md",
            "title": "Guide 1.1.1",
            "scope_type": "chapter",
            "scope_id": "1.1.1",
            "source_type": "chapter_guide",
            "source_id": "guide:chapter:1.1.1:map",
        },
    ]

    tree = ReaderTreeService.build_guide_tree(chapters, guides)

    assert titles(tree) == ["Book Guides", "Chapter 1"]
    assert titles(tree[0]["children"]) == ["Book Overview"]
    assert tree[0]["children"][0]["source_type"] == "book_guide"

    chapter_1 = tree[1]
    assert titles(chapter_1["children"]) == ["Guides 0", "c 1.1"]
    assert chapter_1["children"][0]["type"] == "guide"
    assert chapter_1["children"][0]["source_type"] == "directory_guide"
    assert chapter_1["children"][0]["chapter_id"] == 10
    assert chapter_1["children"][0]["chapter_index"] == "1"
    section_1_1 = chapter_1["children"][1]
    assert titles(section_1_1["children"]) == ["Guide 1.1.1"]
    leaf_1_1_1 = section_1_1["children"][0]
    assert leaf_1_1_1["source_type"] == "chapter_guide"
    assert leaf_1_1_1["chapter_id"] == 12
    assert leaf_1_1_1["chapter_index"] == "1.1.1"
