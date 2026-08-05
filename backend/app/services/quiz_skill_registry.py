from dataclasses import dataclass


CHAPTER_QUIZ_MODE = "chapter"
BOOK_QUIZ_MODE = "book"
QUIZ_MODES = {CHAPTER_QUIZ_MODE, BOOK_QUIZ_MODE}


@dataclass(frozen=True)
class QuizSkill:
    question_type: str
    label: str
    goal: str
    required_context: tuple[str, ...]
    generation_prompt: str
    evaluation_prompt: str
    answer_guidance: str
    expected_points: tuple[str, ...]
    evaluation_rubric: dict[str, str]
    next_step_rule: str
    weight: float


QUIZ_SKILLS: dict[str, QuizSkill] = {
    "concept_explain": QuizSkill(
        question_type="concept_explain",
        label="概念讲解",
        goal="让读者像给初学者讲课一样，用自己的话说明一个核心概念。",
        required_context=("chapter_body", "chapter_guide"),
        generation_prompt=(
            "从正文明确出现的核心概念中选择一个。请读者向一个刚接触本章的人解释："
            "它要描述或解决什么、抓住它必须说清的关键性质是什么，并用一个直观例子、反例或后果帮助理解。"
            "不要要求逐字背定义，也不要把多个概念塞进一题。"
        ),
        evaluation_prompt=(
            "判断回答是否讲清了概念的对象、核心性质和意义。日常语言只要数学含义准确就应认可；"
            "例子不是必须精确计算，但必须与概念相符。"
        ),
        answer_guidance="请像向同学讲解一样回答；可以用例子或比喻，不要求背定义，也不必输入公式。",
        expected_points=(
            "说清概念描述的对象或要解决的问题",
            "指出决定这个概念的核心性质或边界",
            "用有效例子、反例或后果帮助理解",
        ),
        evaluation_rubric={
            "completed": "用自己的话准确说清对象、核心性质与意义，并给出有效例子、反例或后果。",
            "partial": "抓住了大意，但关键性质、适用边界或例子仍有一处含糊。",
            "wrong": "把概念和别的对象混淆，或没有说出决定性的性质。",
        },
        next_step_rule="只追问当前回答中最关键的一个缺口，让读者继续自己讲清楚。",
        weight=1.25,
    ),
    "theorem_understanding": QuizSkill(
        question_type="theorem_understanding",
        label="定理理解",
        goal="检查读者是否理解定理在说什么、条件为何存在，而非只会复述公式。",
        required_context=("chapter_body", "chapter_guide"),
        generation_prompt=(
            "选择正文中明确陈述的一个定理、命题或关键结论。请读者用自然语言说明："
            "它从哪些关键条件出发、保证了什么、为什么这个结论值得关心；可进一步问去掉某个关键条件后直觉上会出什么问题。"
            "题面应给出定理名称或足够的定位信息，但不要在问题里泄露完整答案。"
        ),
        evaluation_prompt=(
            "重点判断条件与结论的方向是否正确、读者是否理解条件的作用。"
            "不要求复写正式符号或逐字陈述；若直觉解释准确，应视为真实理解。"
        ),
        answer_guidance="请用普通语言说清“需要什么条件、能得到什么、为什么”；不要求复写定理公式。",
        expected_points=(
            "正确区分定理的关键条件与结论",
            "解释至少一个关键条件的作用",
            "说明结论的意义、用途或直觉",
        ),
        evaluation_rubric={
            "completed": "准确区分关键条件和结论，并解释定理的意义或至少一个条件的作用。",
            "partial": "结论方向基本正确，但漏掉关键条件、条件作用或定理意义。",
            "wrong": "颠倒条件与结论、误述结论，或把定理和无关结果混淆。",
        },
        next_step_rule="围绕遗漏的条件、结论方向或条件作用提出一个短追问。",
        weight=1.1,
    ),
    "proof_strategy": QuizSkill(
        question_type="proof_strategy",
        label="证明思路",
        goal="让读者讲出证明的路线、关键转折和各步骤为何有效，而不是誊写推导。",
        required_context=("chapter_body",),
        generation_prompt=(
            "选择正文中确实给出证明或推导思路的一个结果。请读者口头讲解证明路线："
            "从哪里出发、最关键的构造/引理/观察是什么、它怎样把问题推进到结论。"
            "可以聚焦一个关键转折，但不要挖掉某行公式让用户补写，也不要要求完整形式化证明或计算。"
        ),
        evaluation_prompt=(
            "重点判断路线是否连贯、关键工具是否适用、关键转折是否真的通向结论。"
            "允许省略代数细节和符号，但不能只说“由定理可得”而不解释为何可用。"
        ),
        answer_guidance="请讲证明的路线和关键转折，不用写完整证明，也不必补公式或计算细节。",
        expected_points=(
            "说明证明从什么已知或目标出发",
            "指出决定性的工具、构造、引理或观察",
            "解释关键转折怎样把论证推进到结论",
        ),
        evaluation_rubric={
            "completed": "说清起点、关键工具或构造、以及它如何导向结论，逻辑方向正确。",
            "partial": "知道主要工具或大致路线，但关键转折、适用原因或终点连接仍不清楚。",
            "wrong": "路线与正文证明无关、使用了不适用的结果，或只复述结论。",
        },
        next_step_rule="指出已经讲对的路线，再追问一个决定性的连接步骤；不要直接给完整证明。",
        weight=1.05,
    ),
    "concept_connection": QuizSkill(
        question_type="concept_connection",
        label="概念联系",
        goal="让读者解释两个概念或结果之间的依赖、区别或分工。",
        required_context=("chapter_body", "chapter_guide", "book_guide"),
        generation_prompt=(
            "选择正文或导读中明确存在联系的两个概念、定理或章节角色。请读者说明："
            "两者各自做什么、联系的方向是什么、为什么需要把它们放在一起理解。"
            "关系必须有来源依据；不要凭名称相似硬凑比较，也不要只要求列相同点/不同点。"
        ),
        evaluation_prompt=(
            "重点判断两边是否都被正确理解、关系方向是否准确、连接是否具体。"
            "不能因读者没有使用书中的原句而扣分。"
        ),
        answer_guidance="请分别说清两者的角色，再讲它们怎样连接；用自己的话即可，不必写公式。",
        expected_points=(
            "分别准确说明两个概念或结果的角色",
            "说清依赖、区别或作用关系的方向",
            "解释为什么这条联系有助于理解本章或全书",
        ),
        evaluation_rubric={
            "completed": "准确说明两边的角色，并给出有方向、可解释的依赖、区别或分工。",
            "partial": "两边大致正确，但关系仍停留在“有关”或只说明了单向的一部分。",
            "wrong": "混淆两边、把无关概念说成等价，或没有给出实际联系。",
        },
        next_step_rule="要求读者补清关系的方向或其中一边承担的具体作用。",
        weight=0.8,
    ),
}


# Old saved links and questions remain readable after the question-type redesign.
LEGACY_QUESTION_TYPE_ALIASES: dict[str, str] = {
    "concept_relation": "concept_connection",
    "reasoning_fill": "proof_strategy",
    "condition_boundary": "theorem_understanding",
    "application": "concept_explain",
    "compare": "concept_connection",
    "global_structure": "concept_connection",
}


def canonical_question_type(question_type: str | None) -> str:
    value = str(question_type or "concept_explain").strip()
    return LEGACY_QUESTION_TYPE_ALIASES.get(value, value)


def get_quiz_skill(question_type: str | None) -> QuizSkill:
    canonical = canonical_question_type(question_type)
    try:
        return QUIZ_SKILLS[canonical]
    except KeyError as exc:
        raise ValueError(f"Unsupported quiz question type: {question_type}") from exc


def is_valid_question_type(question_type: str | None) -> bool:
    if not question_type:
        return False
    return canonical_question_type(question_type) in QUIZ_SKILLS


def normalize_quiz_mode(quiz_mode: str | None) -> str:
    value = str(quiz_mode or CHAPTER_QUIZ_MODE).strip().lower()
    if value not in QUIZ_MODES:
        raise ValueError(f"Unsupported quiz mode: {quiz_mode}")
    return value


def question_type_weights() -> dict[str, float]:
    return {question_type: skill.weight for question_type, skill in QUIZ_SKILLS.items()}
