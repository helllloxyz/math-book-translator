from app.services.parser import MarkdownSplitter


def test_splitter_labels_content_before_first_numbered_heading_as_import_prefix():
    chunks = MarkdownSplitter().split_text("Cover\n\n# 1 Introduction\nBody")

    assert chunks[0]["chapter_index"] == "0"
    assert chunks[0]["title"] == "导入前置内容"
    assert chunks[1]["chapter_index"] == "1"


def test_splitter_labels_unmatched_document_as_import_prefix():
    chunks = MarkdownSplitter().split_text("Cover\n\nNo numbered headings")

    assert chunks == [
        {
            "chapter_index": "0",
            "title": "导入前置内容",
            "content": "Cover\n\nNo numbered headings",
        }
    ]


def test_analyze_outline_groups_section_and_appendix_numbering():
    text = "\n".join(
        [
            "# §28 Computation of de Rham Cohomology",
            "Body 28",
            "# 28.1 Cohomology Vector Space of a Torus",
            "Body 28.1",
            "# Problems",
            "Problem body",
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
            "# §A Point-Set Topology",
            "Body A",
            "# A.1 Topological Spaces",
            "Body A.1",
        ]
    )

    outline = MarkdownSplitter().analyze_outline(text)
    numbered = [node for node in outline["nodes"] if node["kind"] == "numbered"]
    problems = next(node for node in outline["nodes"] if node["title"] == "Problems")

    assert [node["key"] for node in numbered] == ["28", "28.1", "29", "A", "A.1"]
    assert [node["level"] for node in numbered] == [1, 2, 1, 1, 2]
    assert [node["split_level"] for node in numbered] == [1, 2, 1, 1, 2]
    assert outline["default_import_depth"] == 2
    assert problems["kind"] == "attachment"
    assert problems["key"] == "28.problems"
    assert problems["split_level"] == 2
    assert problems["level"] == 2
    assert problems["parent_key"] == "28"


def test_analyze_outline_marks_spaced_dot_leader_entries_as_toc_like():
    outline = MarkdownSplitter().analyze_outline("# §28 Computation . . . . . . 302\nBody")
    node = outline["nodes"][0]

    assert node["key"] == "28"
    assert node["title"] == "Computation"
    assert node["is_toc_like"] is True
    assert node["split_level"] is None
    assert outline["default_import_depth"] == 1


def test_splitter_accepts_short_nonspace_marker_after_numbered_heading_index():
    text = "\n".join(
        [
            "# 16.10\\* The pushforward of left-invariant vector fields",
            "Body 16.10",
            "# 16.11*** Next Section",
            "Body 16.11",
            "# E.12yy Appendix Section",
            "Body E.12",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    chunks = splitter.split_text(text, outline_plan=outline["default_outline_plan"])

    assert [node["key"] for node in outline["nodes"] if node["kind"] == "numbered"] == ["16.10", "16.11", "E.12"]
    assert [node["level"] for node in outline["nodes"] if node["kind"] == "numbered"] == [2, 2, 2]
    assert outline["nodes"][0]["marker"] == "16.10"
    assert outline["nodes"][0]["title"] == "The pushforward of left-invariant vector fields"
    assert outline["nodes"][1]["marker"] == "16.11"
    assert outline["nodes"][1]["title"] == "Next Section"
    assert outline["nodes"][2]["marker"] == "E.12"
    assert outline["nodes"][2]["title"] == "Appendix Section"
    assert [chunk["chapter_index"] for chunk in chunks] == ["16.10", "16.11", "E.12"]


def test_splitter_rejects_overlong_nonspace_marker_after_numbered_heading_index():
    outline = MarkdownSplitter().analyze_outline("# 16.10**** The title\nBody")

    assert outline["nodes"][0]["kind"] == "unmatched"


def test_splitter_uses_confirmed_outline_plan_and_import_depth_as_chunk_boundaries():
    text = "\n".join(
        [
            "Cover",
            "# §28 Computation of de Rham Cohomology",
            "Body 28",
            "# 28.1 Cohomology Vector Space of a Torus",
            "Body 28.1",
            "# Problems",
            "Problem body",
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    outline_plan = {
        "import_depth": 1,
        "nodes": [
            {"id": node["id"], "split_level": node["split_level"]}
            for node in outline["nodes"]
        ],
    }
    chunks = splitter.split_text(text, outline_plan=outline_plan)

    assert [chunk["chapter_index"] for chunk in chunks] == ["0", "28", "29"]
    assert "28.1 Cohomology Vector Space" in chunks[1]["content"]
    assert "# Problems" in chunks[1]["content"]


def test_splitter_can_cut_at_deeper_confirmed_import_depth():
    text = "\n".join(
        [
            "# §28 Computation of de Rham Cohomology",
            "Body 28",
            "# 28.1 Cohomology Vector Space of a Torus",
            "Body 28.1",
            "# 28.2 The Cohomology Ring of a Torus",
            "Body 28.2",
            "# Problems",
            "Problem body",
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    problems = next(node for node in outline["nodes"] if node["title"] == "Problems")
    outline_plan = {
        "import_depth": 2,
        "nodes": [
            {"id": node["id"], "split_level": node["split_level"]}
            for node in outline["nodes"]
        ],
    }
    chunks = splitter.split_text(text, outline_plan=outline_plan)

    assert problems["level"] == 2
    assert problems["split_level"] == 2
    assert [chunk["chapter_index"] for chunk in chunks] == ["28", "28.1", "28.2", "28.problems", "29"]
    assert chunks[3]["content"].startswith("# Problems")


def test_splitter_treats_problems_attachment_as_independent_child_section_by_default():
    text = "\n".join(
        [
            "# §28 Computation of de Rham Cohomology",
            "Body 28",
            "# 28.1 Cohomology Vector Space of a Torus",
            "Body 28.1",
            "# Problems",
            "Problem body",
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    problems = next(node for node in outline["nodes"] if node["title"] == "Problems")
    chunks = splitter.split_text(text, outline_plan=outline["default_outline_plan"])

    assert problems["kind"] == "attachment"
    assert problems["key"] == "28.problems"
    assert problems["level"] == 2
    assert problems["split_level"] == 2
    assert problems["parent_key"] == "28"
    assert problems["id"] in outline["default_selected_heading_ids"]
    assert [chunk["chapter_index"] for chunk in chunks] == ["28", "28.1", "28.problems", "29"]
    assert chunks[2]["title"] == "Problems"
    assert chunks[2]["content"].startswith("# Problems")


def test_splitter_attaches_problems_to_synthetic_major_parent_when_root_heading_is_missing():
    text = "\n".join(
        [
            "# 16.10\\* The pushforward of left-invariant vector fields",
            "Body 16.10",
            "# Problems",
            "Problem body",
            "# 16.11*** Next Section",
            "Body 16.11",
            "# 16.12 Exercise Mechanics",
            "Body 16.12",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    problems = next(node for node in outline["nodes"] if node["title"] == "Problems")
    chunks = splitter.split_text(text, outline_plan=outline["default_outline_plan"])

    assert problems["key"] == "16.problems"
    assert problems["level"] == 2
    assert problems["parent_key"] == "16"
    assert [chunk["chapter_index"] for chunk in chunks] == ["16.10", "16.problems", "16.11", "16.12"]


def test_analyze_outline_demotes_duplicate_numbered_headings_inside_same_group():
    text = "\n".join(
        [
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
            "# 29.1 Reduction to Two Sections",
            "Body 29.1",
            "# 29.1 Problem 1",
            "Problem body",
        ]
    )

    outline = MarkdownSplitter().analyze_outline(text)
    numbered = [node for node in outline["nodes"] if node["kind"] == "numbered"]
    chunks = MarkdownSplitter().split_text(text, outline_plan=outline["default_outline_plan"])

    assert [node["key"] for node in numbered] == ["29", "29.1", "29.1"]
    assert [node["split_level"] for node in numbered] == [1, 2, 3]
    assert numbered[2]["auto_demoted"] is True
    assert outline["default_import_depth"] == 2
    assert [chunk["chapter_index"] for chunk in chunks] == ["29", "29.1"]
    assert "# 29.1 Problem 1" in chunks[1]["content"]


def test_analyze_outline_demotes_same_group_numbered_headings_after_problems():
    text = "\n".join(
        [
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
            "# 29.1 Reduction to Two Sections",
            "Body 29.1",
            "# Problems",
            "Problem intro",
            "# 29.1 Exercise",
            "Exercise body",
            "# 29.2 Exercise",
            "Exercise body 2",
            "# §30 Next Chapter",
            "Body 30",
        ]
    )

    outline = MarkdownSplitter().analyze_outline(text)
    numbered = [node for node in outline["nodes"] if node["kind"] == "numbered"]
    problems = next(node for node in outline["nodes"] if node["title"] == "Problems")
    chunks = MarkdownSplitter().split_text(text, outline_plan=outline["default_outline_plan"])

    assert problems["level"] == 2
    assert [node["key"] for node in numbered] == ["29", "29.1", "29.1", "29.2", "30"]
    assert [node["split_level"] for node in numbered] == [1, 2, 3, 3, 1]
    assert numbered[2]["auto_demoted"] is True
    assert numbered[3]["auto_demoted"] is True
    assert numbered[4]["auto_demoted"] is False
    assert outline["default_import_depth"] == 2
    assert [chunk["chapter_index"] for chunk in chunks] == ["29", "29.1", "29.problems", "30"]
    assert "# 29.1 Exercise" in chunks[2]["content"]
    assert "# 29.2 Exercise" in chunks[2]["content"]


def test_analyze_outline_excludes_numbered_math_environment_headings_from_directory():
    text = "\n".join(
        [
            "# §21 Orientations",
            "Body 21",
            "# 21.3 Orientable Manifolds",
            "Body 21.3",
            "# Proposition 21.3. A connected orientable manifold M has exactly two orientations.",
            "Proposition proof",
            "# §22 Next Chapter",
            "Body 22",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    chunks = splitter.split_text(text, outline_plan=outline["default_outline_plan"])

    assert [node["title"] for node in outline["nodes"]] == [
        "Orientations",
        "Orientable Manifolds",
        "Next Chapter",
    ]
    assert [chunk["chapter_index"] for chunk in chunks] == ["21", "21.3", "22"]
    assert "# Proposition 21.3." in chunks[1]["content"]


def test_splitter_suffixes_duplicate_confirmed_chapter_indexes():
    text = "\n".join(
        [
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
            "# 29.1 Reduction to Two Sections",
            "Body 29.1",
            "# 29.1 Duplicate Section",
            "Duplicate body",
            "# 29.1 Duplicate Section Again",
            "Duplicate body 2",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    outline_plan = {
        "import_depth": 3,
        "nodes": [
            {"id": node["id"], "split_level": 2 if node["key"] == "29.1" else node["split_level"]}
            for node in outline["nodes"]
        ],
    }

    chunks = splitter.split_text(text, outline_plan=outline_plan)

    assert [chunk["chapter_index"] for chunk in chunks] == ["29", "29.1", "29.1-2", "29.1-3"]


def test_splitter_respects_deleted_heading_ids_in_outline_plan():
    text = "\n".join(
        [
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
            "# 29.1 Reduction to Two Sections",
            "Body 29.1",
            "# 29.2 Cochain Homotopies",
            "Body 29.2",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    deleted_node = next(node for node in outline["nodes"] if node["key"] == "29.1")
    outline_plan = {
        "import_depth": 2,
        "deleted_heading_ids": [deleted_node["id"]],
        "nodes": [
            {"id": node["id"], "split_level": node["split_level"]}
            for node in outline["nodes"]
        ],
    }

    chunks = splitter.split_text(text, outline_plan=outline_plan)

    assert [chunk["chapter_index"] for chunk in chunks] == ["29", "29.2"]
    assert "# 29.1 Reduction to Two Sections" in chunks[0]["content"]
