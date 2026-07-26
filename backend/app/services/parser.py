import re
from typing import List, Dict


ATTACHMENT_TITLES = {
    "problem",
    "problems",
    "exercise",
    "exercises",
    "note",
    "notes",
    "reference",
    "references",
}

MATH_ENVIRONMENT_TITLES = {
    "axiom",
    "claim",
    "conjecture",
    "corollary",
    "definition",
    "example",
    "exercise",
    "fact",
    "lemma",
    "notation",
    "proposition",
    "remark",
    "theorem",
}


class HeadingToken:
    def __init__(self, marker: str, key: str, title: str, raw_marker: str | None = None):
        self.marker = marker
        self.key = key
        self.title = title
        self.raw_marker = raw_marker or marker

class MarkdownSplitter:
    # Allow for multiple # characters for nested headers (standard markdown)
    # Group 1: Chapter Index (e.g., "1", "1.1", "17.1")
    # Group 2: Title (e.g., "Introduction")
    REGEX_PATTERN = r"^#+\s+(\d+(?:\.\d+)*)\s+(.*)"
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    LEADER_PAGE_PATTERN = re.compile(r"\s*(?:\.{3,}|(?:\.\s*){3,})\s*\d+\s*$")

    @staticmethod
    def _clean_heading_title(raw_title: str) -> str:
        return MarkdownSplitter.LEADER_PAGE_PATTERN.sub("", raw_title).strip()

    @staticmethod
    def _normalize_key(raw_key: str) -> str:
        parts = [part for part in re.split(r"\s*\.\s*", raw_key.strip().strip(".")) if part]
        normalized = []
        for part in parts:
            normalized.append(part.upper() if part.isalpha() else part)
        return ".".join(normalized)

    @staticmethod
    def _split_marker_title(title: str, marker: str) -> str:
        remainder = title[len(marker):].strip()
        return re.sub(r"^[\s:.)、\-–—]+", "", remainder).strip() or title.strip()

    @staticmethod
    def _extract_heading_token(raw_title: str) -> HeadingToken | None:
        title = MarkdownSplitter._clean_heading_title(raw_title)
        marker_suffix = r"(?:\S{2,3})?"
        patterns = (
            rf"^(?P<marker>§\s*(?P<key>[0-9]+(?:\.[0-9]+)*|[A-Za-z](?:\.[0-9]+)*){marker_suffix})(?!\.\d)(?=$|[\s:.)、\-–—])",
            rf"^(?P<marker>(?:chapter|section|appendix|part)\s+(?P<key>[0-9]+(?:\.[0-9]+)*|[A-Za-z](?:\.[0-9]+)*){marker_suffix})(?!\.\d)(?=$|[\s:.)、\-–—])",
            rf"^(?P<marker>(?P<key>[0-9]+(?:\.[0-9]+)*){marker_suffix})(?!\.\d)(?=$|[\s:.)、\-–—])",
            rf"^(?P<marker>(?P<key>[A-Za-z]\.[0-9]+(?:\.[0-9]+)*){marker_suffix})(?!\.\d)(?=$|[\s:.)、\-–—])",
        )
        for pattern in patterns:
            match = re.match(pattern, title, flags=re.IGNORECASE)
            if not match:
                continue
            raw_marker = match.group("marker").strip()
            key = MarkdownSplitter._normalize_key(match.group("key"))
            marker = raw_marker[: raw_marker.find(match.group("key"))] + key
            return HeadingToken(
                marker=marker.strip(),
                key=key,
                title=MarkdownSplitter._split_marker_title(title, raw_marker),
                raw_marker=raw_marker,
            )
        return None

    @staticmethod
    def _node_level(key: str) -> int:
        return len([part for part in str(key or "").split(".") if part])

    @staticmethod
    def _parent_key_for(key: str) -> str | None:
        parts = [part for part in str(key or "").split(".") if part]
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])

    @staticmethod
    def _is_toc_like(raw_title: str) -> bool:
        return bool(MarkdownSplitter.LEADER_PAGE_PATTERN.search(raw_title))

    @staticmethod
    def _is_math_environment_heading(title: str) -> bool:
        match = re.match(r"^([A-Za-z]+)\s+\d+(?:\.\d+)*(?=$|[\s:.)、\-–—])", title.strip())
        return bool(match and match.group(1).casefold() in MATH_ENVIRONMENT_TITLES)

    @staticmethod
    def _is_attachment_item_title(title: str) -> bool:
        normalized = str(title or "").strip().casefold()
        return bool(re.search(r"\b(problems?|exercises?|questions?)\b", normalized))

    @staticmethod
    def _attachment_parent(nodes: list[dict]) -> str | None:
        parent = MarkdownSplitter._attachment_parent_node(nodes)
        return parent.get("key") if parent else None

    @staticmethod
    def _attachment_parent_node(nodes: list[dict]) -> dict | None:
        for node in reversed(nodes):
            if node.get("kind") == "numbered" and node.get("level") == 1:
                return node
        for node in reversed(nodes):
            if node.get("kind") == "numbered" and node.get("key"):
                root_key = str(node["key"]).split(".", 1)[0]
                return {"key": root_key, "level": 1}
        return None

    @staticmethod
    def _attachment_level(nodes: list[dict]) -> int:
        parent = MarkdownSplitter._attachment_parent_node(nodes)
        return int(parent.get("level") or 1) + 1 if parent else 1

    @staticmethod
    def _attachment_key(nodes: list[dict], title: str) -> str:
        slug = re.sub(r"[^0-9a-z]+", "-", title.casefold()).strip("-")
        parent = MarkdownSplitter._attachment_parent_node(nodes)
        if parent and parent.get("key") and slug:
            return f"{parent['key']}.{slug}"
        return slug

    @staticmethod
    def _default_selected_heading_ids(nodes: list[dict]) -> list[str]:
        split_nodes = [node for node in nodes if node.get("split_level")]
        if not split_nodes:
            return []
        import_depth = MarkdownSplitter._default_import_depth(nodes)
        return [
            node["id"]
            for node in split_nodes
            if int(node.get("split_level") or 0) <= import_depth
        ]

    @staticmethod
    def _default_import_depth(nodes: list[dict]) -> int:
        split_levels = [
            int(node["split_level"])
            for node in nodes
            if isinstance(node.get("split_level"), int) and node.get("split_level") > 0
            and not node.get("auto_demoted")
        ]
        return max(split_levels) if split_levels else 1

    @staticmethod
    def _default_outline_plan(nodes: list[dict]) -> dict:
        return {
            "import_depth": MarkdownSplitter._default_import_depth(nodes),
            "nodes": [
                {"id": node["id"], "split_level": node.get("split_level")}
                for node in nodes
            ],
        }

    @staticmethod
    def _normalize_split_level(value) -> int | None:
        if value in (None, "", False):
            return None
        if isinstance(value, str) and value.casefold() in {"delete", "deleted", "__delete__"}:
            return None
        try:
            level = int(value)
        except (TypeError, ValueError):
            return None
        return level if level > 0 else None

    @staticmethod
    def _is_deleted_outline_node(raw_node: dict) -> bool:
        split_level = raw_node.get("split_level")
        return (
            raw_node.get("deleted") is True
            or raw_node.get("delete") is True
            or (isinstance(split_level, str) and split_level.casefold() in {"delete", "deleted", "__delete__"})
        )

    @staticmethod
    def _selected_heading_ids_from_plan(outline: dict, outline_plan: dict | None) -> list[str]:
        nodes = outline.get("nodes") or []
        if not outline_plan:
            import_depth = outline.get("default_import_depth") or MarkdownSplitter._default_import_depth(nodes)
            split_by_id = {node["id"]: node.get("split_level") for node in nodes}
        else:
            import_depth = outline_plan.get("import_depth") or outline.get("default_import_depth") or 1
            try:
                import_depth = int(import_depth)
            except (TypeError, ValueError):
                import_depth = 1
            split_by_id = {node["id"]: node.get("split_level") for node in nodes}
            deleted_heading_ids = {
                str(node_id)
                for node_id in outline_plan.get("deleted_heading_ids") or []
            }
            raw_nodes = outline_plan.get("nodes") or []
            if isinstance(raw_nodes, list):
                for raw_node in raw_nodes:
                    if not isinstance(raw_node, dict) or not raw_node.get("id"):
                        continue
                    if MarkdownSplitter._is_deleted_outline_node(raw_node):
                        deleted_heading_ids.add(str(raw_node["id"]))
                    split_by_id[str(raw_node["id"])] = MarkdownSplitter._normalize_split_level(
                        raw_node.get("split_level")
                    )
            raw_map = outline_plan.get("split_level_by_heading") or {}
            if isinstance(raw_map, dict):
                for node_id, split_level in raw_map.items():
                    if isinstance(split_level, str) and split_level.casefold() in {"delete", "deleted", "__delete__"}:
                        deleted_heading_ids.add(str(node_id))
                    split_by_id[str(node_id)] = MarkdownSplitter._normalize_split_level(split_level)
            for node_id in deleted_heading_ids:
                split_by_id[node_id] = None

        return [
            node["id"]
            for node in nodes
            if (split_by_id.get(node["id"]) is not None and int(split_by_id[node["id"]]) <= import_depth)
        ]

    def analyze_outline(self, text: str) -> Dict:
        lines = text.split("\n")
        nodes = []
        seen_numbered_keys = set()
        active_attachment_parent = None
        active_attachment_level = None
        for index, line in enumerate(lines):
            heading_match = self.HEADING_PATTERN.match(line)
            if not heading_match:
                continue

            raw_title = heading_match.group(2).strip()
            title = self._clean_heading_title(raw_title)
            if self._is_math_environment_heading(title):
                continue

            token = self._extract_heading_token(raw_title)
            node_id = f"h-{index + 1}"
            is_toc_like = self._is_toc_like(raw_title)

            if token:
                base_level = self._node_level(token.key)
                root_key = token.key.split(".", 1)[0]
                duplicate_demote = token.key in seen_numbered_keys
                attachment_demote = (
                    active_attachment_parent is not None
                    and root_key == active_attachment_parent
                    and active_attachment_level is not None
                    and base_level >= active_attachment_level
                    and self._is_attachment_item_title(token.title)
                )
                auto_demoted = duplicate_demote or attachment_demote
                level = base_level + 1 if auto_demoted else base_level
                split_level = level if not is_toc_like else None
                nodes.append(
                    {
                        "id": node_id,
                        "line": index + 1,
                        "raw": line,
                        "title": token.title,
                        "marker": token.marker,
                        "key": token.key,
                        "level": level,
                        "split_level": split_level,
                        "kind": "numbered",
                        "parent_key": self._parent_key_for(token.key),
                        "enabled": split_level is not None,
                        "is_toc_like": is_toc_like,
                        "auto_demoted": auto_demoted,
                    }
                )
                if split_level is not None:
                    seen_numbered_keys.add(token.key)
                if base_level == 1 and root_key != active_attachment_parent:
                    active_attachment_parent = None
                    active_attachment_level = None
                elif (
                    active_attachment_parent is not None
                    and not auto_demoted
                    and active_attachment_level is not None
                    and base_level <= active_attachment_level
                ):
                    active_attachment_parent = None
                    active_attachment_level = None
                continue

            normalized_title = title.casefold()
            is_attachment = normalized_title in ATTACHMENT_TITLES
            attachment_level = self._attachment_level(nodes)
            parent_key = self._attachment_parent(nodes)
            attachment_key = self._attachment_key(nodes, title) if is_attachment else ""
            split_level = attachment_level if is_attachment and not is_toc_like else None
            nodes.append(
                {
                    "id": node_id,
                    "line": index + 1,
                    "raw": line,
                    "title": title,
                    "marker": "",
                    "key": attachment_key,
                    "level": attachment_level,
                    "split_level": split_level,
                    "kind": "attachment" if is_attachment else "unmatched",
                    "parent_key": parent_key,
                    "enabled": split_level is not None,
                    "is_toc_like": is_toc_like,
                    "auto_demoted": False,
                }
            )
            if is_attachment and parent_key:
                active_attachment_parent = parent_key.split(".", 1)[0]
                active_attachment_level = attachment_level

        for index, node in enumerate(nodes):
            start_line = node["line"] - 1
            end_line = nodes[index + 1]["line"] - 1 if index + 1 < len(nodes) else len(lines)
            node["char_count"] = len("\n".join(lines[start_line:end_line]))

        return {
            "nodes": nodes,
            "default_selected_heading_ids": self._default_selected_heading_ids(nodes),
            "default_import_depth": self._default_import_depth(nodes),
            "default_outline_plan": self._default_outline_plan(nodes),
            "heading_count": len(nodes),
        }

    def split_text(
        self,
        text: str,
        selected_heading_ids: list[str] | None = None,
        outline_plan: dict | None = None,
    ) -> List[Dict]:
        """
        Splits markdown text into chunks based on numbered headers.
        Returns a list of dictionaries with keys: 'chapter_index', 'title', 'content'.
        """
        lines = text.split('\n')
        chunks = []
        matches = []

        outline = self.analyze_outline(text)
        if outline_plan is not None:
            selected_heading_ids = self._selected_heading_ids_from_plan(outline, outline_plan)
        elif selected_heading_ids is None:
            selected_heading_ids = self._selected_heading_ids_from_plan(outline, None)

        selected_ids = set(selected_heading_ids)
        nodes_by_line = {
            node["line"] - 1: node
            for node in outline["nodes"]
            if node["id"] in selected_ids
        }

        # Find all selected headers.
        for i, line in enumerate(lines):
            node = nodes_by_line.get(i)
            if node:
                matches.append((i, node))

        # Handle text before the first numbered header.
        if not matches:
             # No headers found, return whole text as one chunk
             return [{"chapter_index": "0", "title": "导入前置内容", "content": text}]
        
        if matches[0][0] > 0:
            preamble_content = "\n".join(lines[:matches[0][0]])
            if preamble_content.strip():
                chunks.append({
                    "chapter_index": "0",
                    "title": "导入前置内容",
                    "content": preamble_content
                })

        # Process each section
        chapter_index_counts = {}
        for idx, (start_line, node) in enumerate(matches):
            # End line is the start of the next match, or the end of the file
            end_line = matches[idx+1][0] if idx + 1 < len(matches) else len(lines)
            
            content_lines = lines[start_line:end_line]
            full_content = "\n".join(content_lines)
            
            chapter_index = node.get("key") or f"line-{node['line']}"
            chapter_index_counts[chapter_index] = chapter_index_counts.get(chapter_index, 0) + 1
            if chapter_index_counts[chapter_index] > 1:
                chapter_index = f"{chapter_index}-{chapter_index_counts[chapter_index]}"

            chunks.append({
                "chapter_index": chapter_index,
                "title": node.get("title") or "Untitled",
                "content": full_content
            })

        return chunks
