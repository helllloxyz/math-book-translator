from dataclasses import dataclass


@dataclass(frozen=True)
class QuizSkill:
    question_type: str
    goal: str
    required_context: tuple[str, ...]
    question_style: str
    evaluation_rubric: dict[str, str]
    next_step_rule: str
    weight: float


QUIZ_SKILLS: dict[str, QuizSkill] = {
    "concept_explain": QuizSkill(
        question_type="concept_explain",
        goal="Check whether the reader can explain a core concept in their own words.",
        required_context=("learning_context", "chapter_excerpt"),
        question_style="Ask for a concise explanation plus one mathematical consequence or example.",
        evaluation_rubric={
            "completed": "Defines the concept accurately, names the required conditions, and gives a relevant consequence or example.",
            "partial": "Captures the broad idea but omits a condition, consequence, or precise mathematical language.",
            "wrong": "Confuses the concept with a different object or cannot state the defining properties.",
        },
        next_step_rule="If partial or wrong, ask for the missing condition or a minimal example.",
        weight=1.2,
    ),
    "concept_relation": QuizSkill(
        question_type="concept_relation",
        goal="Check whether the reader understands how two concepts or results depend on each other.",
        required_context=("chapter_guide", "book_guide"),
        question_style="Ask the reader to compare or connect two named concepts/results from the guide context.",
        evaluation_rubric={
            "completed": "States both concepts/results and explains the dependency or contrast accurately.",
            "partial": "Mentions both sides but leaves the relationship vague or one-directional.",
            "wrong": "Treats unrelated ideas as equivalent or misses the core relationship.",
        },
        next_step_rule="If partial or wrong, prompt for the direction of dependency.",
        weight=1.0,
    ),
    "reasoning_fill": QuizSkill(
        question_type="reasoning_fill",
        goal="Check whether the reader can fill a missing proof or derivation step.",
        required_context=("chapter_excerpt", "key_theorem_or_concept"),
        question_style="Present a short reasoning gap and ask what justifies the missing step.",
        evaluation_rubric={
            "completed": "Names the correct theorem/definition and explains why it applies in this step.",
            "partial": "Identifies the right idea but does not justify applicability.",
            "wrong": "Uses an inapplicable result or only restates the conclusion.",
        },
        next_step_rule="If partial or wrong, ask which hypothesis enables the step.",
        weight=1.1,
    ),
    "condition_boundary": QuizSkill(
        question_type="condition_boundary",
        goal="Check whether the reader recognizes theorem hypotheses and boundary cases.",
        required_context=("chapter_excerpt", "definition_or_theorem_excerpt"),
        question_style="Ask what breaks if a stated condition is removed or changed.",
        evaluation_rubric={
            "completed": "Identifies the condition, explains its role, and gives a boundary/counterexample intuition.",
            "partial": "Identifies the condition but not why it is needed.",
            "wrong": "Claims the result still holds without addressing the hypothesis.",
        },
        next_step_rule="If partial or wrong, ask for a counterexample shape.",
        weight=1.0,
    ),
    "application": QuizSkill(
        question_type="application",
        goal="Check whether the reader can apply a concept to an example or exercise-like situation.",
        required_context=("example_or_exercise_excerpt", "chapter_guide"),
        question_style="Ask a compact application question tied to a chapter example or exercise pattern.",
        evaluation_rubric={
            "completed": "Applies the right method and explains the decisive step.",
            "partial": "Chooses a plausible method but leaves the computation or justification incomplete.",
            "wrong": "Chooses an unrelated method or does not connect the answer to the chapter concept.",
        },
        next_step_rule="If partial or wrong, ask for the first method-selection signal.",
        weight=0.8,
    ),
    "compare": QuizSkill(
        question_type="compare",
        goal="Check whether the reader can compare nearby concepts or chapters.",
        required_context=("chapter_guide", "neighbor_chapter_guides", "book_guide"),
        question_style="Ask for a structured comparison with one similarity and one difference.",
        evaluation_rubric={
            "completed": "Names both objects, gives a valid similarity, and gives a valid difference.",
            "partial": "Gives only a similarity or only a difference.",
            "wrong": "Compares the wrong objects or gives generic statements not grounded in the guide.",
        },
        next_step_rule="If partial or wrong, ask for the missing side of the comparison.",
        weight=0.7,
    ),
    "global_structure": QuizSkill(
        question_type="global_structure",
        goal="Check whether the reader sees where this chapter fits in the book-level structure.",
        required_context=("book_guide", "chapter_guide"),
        question_style="Ask why the current chapter appears at this point in the book's reading path.",
        evaluation_rubric={
            "completed": "Explains the chapter's role using both prerequisite and later-use relationships.",
            "partial": "Identifies only a prerequisite or only a later-use relationship.",
            "wrong": "Cannot place the chapter in the book-level structure.",
        },
        next_step_rule="If partial or wrong, ask what later chapter/result uses this material.",
        weight=0.9,
    ),
}


def get_quiz_skill(question_type: str | None) -> QuizSkill:
    if not question_type:
        return QUIZ_SKILLS["concept_explain"]
    try:
        return QUIZ_SKILLS[question_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported quiz question type: {question_type}") from exc


def is_valid_question_type(question_type: str | None) -> bool:
    return bool(question_type) and question_type in QUIZ_SKILLS


def question_type_weights() -> dict[str, float]:
    return {question_type: skill.weight for question_type, skill in QUIZ_SKILLS.items()}
