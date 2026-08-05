class ReaderTreeService:
    @staticmethod
    def chapter_title(chapter) -> str:
        return chapter.title_zh or chapter.title_en or chapter.chapter_index

    @staticmethod
    def index_depth(chapter_index: str) -> int:
        return len(str(chapter_index or "").split("."))

    @staticmethod
    def parent_index(chapter_index: str) -> str | None:
        parts = str(chapter_index or "").split(".")
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])

    @staticmethod
    def major_index(chapter_index: str) -> str:
        return str(chapter_index or "").split(".")[0]

    @staticmethod
    def index_sort_key(chapter_index: str) -> list[tuple[int, int, str]]:
        parts = str(chapter_index or "").split(".")
        key = []
        for part in parts:
            if part.isdigit():
                key.append((0, int(part), ""))
            else:
                key.append((1, 0, part.casefold()))
        return key

    @staticmethod
    def sorted_chapters(chapters) -> list:
        return sorted(chapters, key=lambda chapter: (chapter.order is None, chapter.order or 0))

    @staticmethod
    def synthetic_directory(chapter_index: str) -> dict:
        return {
            "id": f"dir:book:{chapter_index}",
            "kind": "directory",
            "type": "directory",
            "title": chapter_index,
            "label": chapter_index,
            "chapter_id": None,
            "chapter_index": chapter_index,
            "children": [],
        }

    @staticmethod
    def chapter_leaf(chapter, *, title: str | None = None) -> dict:
        return {
            "id": f"chapter:{chapter.id}",
            "kind": "leaf",
            "type": "chapter",
            "title": title or ReaderTreeService.chapter_title(chapter),
            "label": chapter.chapter_index,
            "chapter_id": chapter.id,
            "chapter_index": chapter.chapter_index,
            "content_type": getattr(chapter, "content_type", None) or "main_text",
            "source_type": "chapter_content",
            "source_id": f"chapter:{chapter.id}",
            "source_title": ReaderTreeService.chapter_title(chapter),
        }

    @staticmethod
    def directory_for_chapter(chapter) -> dict:
        return {
            "id": f"dir:book:{chapter.chapter_index}",
            "kind": "directory",
            "type": "directory",
            "title": ReaderTreeService.chapter_title(chapter),
            "label": chapter.chapter_index,
            "chapter_id": chapter.id,
            "chapter_index": chapter.chapter_index,
            "content_type": getattr(chapter, "content_type", None) or "main_text",
            "children": [],
        }

    @staticmethod
    def build_book_tree(chapters) -> list[dict]:
        ordered = ReaderTreeService.sorted_chapters(chapters)
        by_index = {chapter.chapter_index: chapter for chapter in ordered}
        children_by_parent: dict[str | None, list] = {}
        for chapter in ordered:
            parent = ReaderTreeService.parent_index(chapter.chapter_index)
            while parent and parent not in by_index and ReaderTreeService.parent_index(parent) is not None:
                parent = ReaderTreeService.parent_index(parent)
            children_by_parent.setdefault(parent, []).append(chapter)

        def build_node(chapter):
            child_chapters = children_by_parent.get(chapter.chapter_index, [])
            if not child_chapters:
                return ReaderTreeService.chapter_leaf(chapter)

            node = ReaderTreeService.directory_for_chapter(chapter)
            node["children"].append(
                ReaderTreeService.chapter_leaf(chapter, title=f"{ReaderTreeService.chapter_title(chapter)} content")
            )
            node["children"].extend(build_node(child) for child in child_chapters if child.chapter_index in by_index)
            return node

        roots = [build_node(chapter) for chapter in children_by_parent.get(None, [])]
        missing_parent_indexes = [
            parent
            for parent in children_by_parent
            if parent is not None and parent not in by_index
        ]
        for parent in sorted(missing_parent_indexes, key=ReaderTreeService.index_sort_key):
            node = ReaderTreeService.synthetic_directory(parent)
            node["children"].extend(build_node(child) for child in children_by_parent.get(parent, []))
            roots.append(node)
        return roots

    @staticmethod
    def guide_leaf(guide: dict, chapter=None, chapter_index: str | None = None) -> dict:
        leaf = {
            "id": guide["id"],
            "kind": "leaf",
            "type": "guide",
            "title": guide["title"],
            "label": guide.get("label", ""),
            "filename": guide["filename"],
            "scope_type": guide.get("scope_type", "book"),
            "scope_id": guide.get("scope_id", "book"),
            "source_type": guide.get("source_type", "book_guide"),
            "source_id": guide.get("source_id", guide["id"]),
            "source_title": guide.get("source_title") or guide["title"],
        }
        if chapter is not None:
            leaf.update(
                {
                    "chapter_id": chapter.id,
                    "chapter_index": chapter.chapter_index,
                    "content_type": getattr(chapter, "content_type", None) or "main_text",
                }
            )
        elif chapter_index:
            leaf["chapter_index"] = chapter_index
        return leaf

    @staticmethod
    def _build_index_tree(chapters) -> list[dict]:
        ordered = ReaderTreeService.sorted_chapters(chapters)
        nodes: dict[str, dict] = {}
        child_indexes_by_parent: dict[str | None, set[str]] = {}

        def get_node(index: str, order: int) -> dict:
            node = nodes.get(index)
            if node is None:
                node = {
                    "index": index,
                    "chapter": None,
                    "children": [],
                    "order": order,
                }
                nodes[index] = node
            else:
                node["order"] = min(node["order"], order)
            return node

        for order, chapter in enumerate(ordered):
            chapter_index = str(chapter.chapter_index or "").strip() or str(order + 1)
            parts = [part for part in chapter_index.split(".") if part] or [str(order + 1)]
            for depth in range(1, len(parts) + 1):
                index = ".".join(parts[:depth])
                node = get_node(index, order)
                if depth == len(parts):
                    node["chapter"] = chapter
                parent = ".".join(parts[: depth - 1]) if depth > 1 else None
                child_indexes_by_parent.setdefault(parent, set()).add(index)

        for parent, child_indexes in child_indexes_by_parent.items():
            if parent is None:
                continue
            nodes[parent]["children"] = [nodes[index] for index in child_indexes]

        for node in nodes.values():
            node["children"].sort(
                key=lambda child: (child["order"], ReaderTreeService.index_sort_key(child["index"]))
            )

        roots = [nodes[index] for index in child_indexes_by_parent.get(None, set())]
        roots.sort(key=lambda node: (node["order"], ReaderTreeService.index_sort_key(node["index"])))
        return roots

    @staticmethod
    def build_guide_tree(chapters, guides) -> list[dict]:
        book_guides = [guide for guide in guides if guide.get("scope_type", "book") == "book"]
        scoped_guides: dict[str, list] = {}
        for guide in guides:
            if guide.get("scope_type") in {"chapter", "directory"}:
                scoped_guides.setdefault(str(guide.get("scope_id") or ""), []).append(guide)

        tree = []
        if book_guides:
            tree.append({
                "id": "dir:guide:book",
                "kind": "directory",
                "type": "directory",
                "title": "Book Guides",
                "children": [ReaderTreeService.guide_leaf(guide) for guide in book_guides],
            })

        def build_node(node: dict) -> dict | None:
            chapter = node["chapter"]
            chapter_index = node["index"]
            title = ReaderTreeService.chapter_title(chapter) if chapter else chapter_index
            children = [
                ReaderTreeService.guide_leaf(guide, chapter=chapter, chapter_index=chapter_index)
                for guide in scoped_guides.get(chapter_index, [])
            ]
            child_nodes = [
                built
                for child in node["children"]
                if (built := build_node(child)) is not None
            ]
            if not children and not child_nodes:
                return None
            if len(children) == 1 and not child_nodes:
                return children[0]

            children.extend(child_nodes)

            return {
                "id": f"dir:guide:{chapter_index}",
                "kind": "directory",
                "type": "directory",
                "title": title,
                "label": chapter_index,
                "chapter_id": chapter.id if chapter else None,
                "chapter_index": chapter_index,
                "children": children,
            }

        tree.extend(
            built
            for root in ReaderTreeService._build_index_tree(chapters)
            if (built := build_node(root)) is not None
        )

        return tree
