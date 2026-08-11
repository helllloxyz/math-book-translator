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


def test_splitter_recognizes_chinese_chapter_markers_and_preserves_source_order():
    text = "\n".join(
        [
            "封面",
            "# 第1章 合情推理",
            "第一章正文",
            "# 第二章 定量规则",
            "第二章正文",
            "# 第3章 初等抽样论",
            "第三章正文",
            "# 第四章 初等假设检验",
            "第四章正文",
            "# 第5章 概率论的怪异应用",
            "第五章正文",
        ]
    )

    splitter = MarkdownSplitter()
    outline = splitter.analyze_outline(text)
    chunks = splitter.split_text(text, outline_plan=outline["default_outline_plan"])

    assert [node["marker"] for node in outline["nodes"]] == [
        "第1章",
        "第二章",
        "第3章",
        "第四章",
        "第5章",
    ]
    assert [node["key"] for node in outline["nodes"]] == ["1", "2", "3", "4", "5"]
    assert [node["title"] for node in outline["nodes"]] == [
        "合情推理",
        "定量规则",
        "初等抽样论",
        "初等假设检验",
        "概率论的怪异应用",
    ]
    assert [chunk["chapter_index"] for chunk in chunks] == ["0", "1", "2", "3", "4", "5"]


def test_splitter_nests_single_number_chinese_sections_under_latest_chapter():
    text = "\n".join(
        [
            "# 第2章 定量规则",
            "章正文",
            "# 第1节 基本规则",
            "节正文",
            "# 第2节 进阶规则",
            "节正文",
        ]
    )

    outline = MarkdownSplitter().analyze_outline(text)

    assert [node["key"] for node in outline["nodes"]] == ["2", "2.1", "2.2"]
    assert [node["split_level"] for node in outline["nodes"]] == [1, 2, 2]


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


def test_analyze_outline_includes_fifteen_lines_of_context_around_each_heading():
    text = "\n".join(
        [f"Before {index}" for index in range(1, 21)]
        + ["# 1 Context Heading"]
        + [f"After {index}" for index in range(1, 21)]
    )

    node = MarkdownSplitter().analyze_outline(text)["nodes"][0]
    context = node["context"]

    assert context["radius"] == 15
    assert context["start_line"] == 6
    assert context["heading_line"] == 21
    assert context["end_line"] == 36
    assert len(context["lines"]) == 31
    assert context["lines"][0] == "Before 6"
    assert context["lines"][15] == "# 1 Context Heading"
    assert context["lines"][-1] == "After 15"


def test_analyze_outline_context_stops_at_document_boundaries_and_truncates_long_lines():
    long_line = "x" * 520
    nodes = MarkdownSplitter().analyze_outline(f"# 1 Start\n{long_line}\n# 2 End")["nodes"]

    first_context = nodes[0]["context"]
    last_context = nodes[-1]["context"]

    assert first_context["start_line"] == 1
    assert first_context["end_line"] == 3
    assert len(first_context["lines"][1]) == 501
    assert first_context["lines"][1].endswith("…")
    assert last_context["start_line"] == 1
    assert last_context["heading_line"] == 3
    assert last_context["end_line"] == 3


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
