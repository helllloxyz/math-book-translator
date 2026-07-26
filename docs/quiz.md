初始思路
"""
我有个思路

1.题型预定义，给出几种种类，这是固定性的框架，类似于 skill

2.分两种Quiz逻辑

A.章节Quiz
    2.1 章节页面的Quiz按钮，还是问关于这一章具体内容紧密相关的问题
    2.2 初始状态按照概率随机选一种， 将题型输入给LLM
	2.3 context 取决于题型: 正文全文 或者 章节 / book 的 guides
	特别注意因为有book level guides, 所以全书层次的问题也是可以生成出来的
	在complie知识或者生成guides可以让LLM顺手生成几个考题，这样问的时候就不用等待，可以直接出来，需要个题库，LLM记录和分析用户对题目的回答状况
	回答完毕后可以根据回答状态，生成更多针对性的题目（一次若干题目）
	题库需要设计下
	
B.书本的Quiz, 个性化 User.md， 放在library的面板上， 比如翻译旁边 
  根据未分析的note和quiz交互的数量和文本长度等指标，提示用户需要分析， 因为过程需要等待，让用户手动执行，按照交互时间线压缩进 User.md
  可以把分析结果展示给用户
  根据分析，选择用户可能比较薄弱的环节提问， 会转到 章节Quiz， 章节由决策层选择，同时决策时会把用户的一些分析结论一起传过去  
"""


这个思路很对。建议这样定稿：

## 总体拆分

Quiz 分两套：

```text
Chapter Quiz：围绕当前章节内容出题
Book Quiz：基于 User.md 做个性化诊断，再跳转到某个 Chapter Quiz
```

也就是：

```text
Chapter Quiz = 局部检查
Book Quiz = 全书学习画像驱动的薄弱点检查
```

---

# A. Chapter Quiz

## 1. 题型 Skill 固定

题型不要让 LLM 自由发挥，预定义：

```ts
question_type:
  | 'concept_explain'
  | 'concept_relation'
  | 'reasoning_fill'
  | 'condition_boundary'
  | 'application'
  | 'compare'
  | 'global_structure'
```

每个题型是一个 skill：

```ts
QuizSkill = {
  type,
  goal,
  required_context,
  question_style,
  evaluation_rubric,
  next_step_rule
}
```

---

## 2. Context 按题型取

```ts
concept_explain:
  - 当前章节正文
  - 当前章节 guide

concept_relation:
  - 当前章节 guide
  - book level guide

reasoning_fill:
  - 当前章节正文
  - 相关公式/推导片段

condition_boundary:
  - 当前章节正文
  - theorem / proposition / definition blocks

application:
  - 当前章节例子
  - 当前章节 guide

compare:
  - 当前章节 guide
  - book guide
  - 前后章节 guide

global_structure:
  - book guide
  - chapter guide
```

重点：

```text
章节 Quiz 不等于只能问局部问题。
如果题型是 global_structure，可以基于 book guide 问“这一章在全书里的作用”。
```

---

## 3. 初始出题逻辑

打开章节 Quiz：

```text
1. 判断是否已有题库可用
2. 有题库：按权重抽一道
3. 没题库：按概率选题型，然后实时生成
4. 第一轮直接出题
```

题型概率可以先这样：

```ts
concept_explain: 25%
concept_relation: 20%
reasoning_fill: 20%
condition_boundary: 15%
application: 10%
compare: 5%
global_structure: 5%
```

后续根据用户表现调整。

---

# 4. 题库设计

题库最好挂在 chapter 层，也可以有 book 层。

```ts
QuizQuestion = {
  id,
  book_id,
  chapter_id,
  source: 'pre_generated' | 'runtime_generated' | 'personalized',
  question_type,
  difficulty: 'basic' | 'normal' | 'advanced',
  target_concepts: string[],
  question_text,
  expected_points: string[],
  common_mistakes: string[],
  context_refs: [
    {
      type: 'chapter_text' | 'chapter_guide' | 'book_guide' | 'note' | 'user_md',
      ref_id,
      quote?
    }
  ],
  evaluation_rubric,
  followup_strategy,
  created_at,
  usage_stats: {
    asked_count,
    completed_count,
    partial_count,
    avg_attempts
  }
}
```

不要存标准答案长文，存：

```ts
expected_points
common_mistakes
rubric
```

这样更适合审阅用户回答。

---

## 5. 预生成时机

在 compile / generate guides 时顺手生成：

```text
每章 5-10 道
全书 10-20 道
```

每章建议覆盖：

```text
2 道概念题
2 道关系题
2 道推理/条件题
1 道全书结构题
```

这样打开 Quiz 几乎秒出题。

---

## 6. 回答后逻辑

用户答完：

```text
evaluate answer
  -> completed / partial / wrong
  -> 记录到 quiz_attempt
  -> 更新该题 usage_stats
  -> 如果 partial/wrong，生成 followup
  -> 如果 completed，锁定本题
```

完成后可以后台/手动生成针对性题：

```text
基于本次 missing_points，生成 2-3 道 personalized questions
```

---

# B. Book Quiz

Book Quiz 本质是：

```text
User.md 驱动的诊断入口
```

它不直接聊天出题，而是先做决策：

```text
用户现在最该检查哪一章、哪个概念、哪种题型？
```

然后跳转到对应 Chapter Quiz。

---

## 1. User.md 分析入口

放 Library 面板，翻译按钮旁边：

```text
Analyze Learning Profile
```

显示提示条件：

```ts
shouldSuggestAnalyze =
  unprocessed_notes_count >= 5
  || unprocessed_quiz_count >= 3
  || unprocessed_text_length >= 3000
  || last_analyzed_at > 7 days
```

文案：

```text
你最近有一些新笔记和 Quiz 记录，可以分析生成学习画像。
```

---

## 2. User.md 内容

```md
# User Learning Profile

## Summary
用户当前整体理解状态。

## Strong Concepts
- ...

## Weak Concepts
- concept:
  chapter:
  weakness_type:
  evidence:
  priority:

## Misconceptions
- concept:
  wrong_belief:
  correction_target:
  evidence:

## Recent Learning Timeline
- ...

## Recommended Quiz Targets
- chapter:
  concept:
  question_type:
  reason:
```

---

## 3. 分析过程

手动触发：

```text
collect unprocessed notes + quiz attempts
  -> 按时间线压缩
  -> merge into User.md
  -> 标记 processed
  -> 展示分析结果
```

输出展示给用户：

```text
这次分析发现：
1. 你对 xxx 的定义比较清楚
2. 但 yyy 和 zzz 的关系还不稳
3. 建议下一题检查 chapter 4 的 condition_boundary
```

---

## 4. Book Quiz 决策层

点击 Book Quiz：

```ts
selectPersonalizedQuizTarget(User.md, book_guide, chapter_guides)
```

输出：

```json
{
  "chapter_id": "...",
  "target_concept": "...",
  "question_type": "condition_boundary",
  "difficulty": "normal",
  "reason": "用户多次漏掉 xxx 的前提条件",
  "personalization_context": {
    "weakness_type": "condition_missing",
    "evidence": "...",
    "avoid": ["最近刚问过的题"]
  }
}
```

然后：

```text
跳转到该章节的 Chapter Quiz
```

并把这个 payload 传过去。

---

# C. 两者关系

```text
Chapter Quiz:
  当前章 + 题库 + guides + 正文
  偏内容检查

Book Quiz:
  User.md + guides + 历史交互
  偏个性化选题
```

最终还是统一进入：

```text
ConversationPage(mode='quiz')
```

只是 payload 不同。

---

# D. 推荐 MVP

先做：

```text
1. 题型 Skill 配置
2. Chapter 题库表
3. compile/guides 时预生成题
4. Quiz attempt 记录
5. User.md 手动分析
6. Book Quiz 根据 User.md 选 chapter + question_type
```

最关键的设计点：

```text
Book Quiz 不负责出题，只负责选“该去哪个章节问什么类型的问题”。
Chapter Quiz 负责真正出题和审阅。
```

