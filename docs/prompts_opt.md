> 历史说明：本文记录的是移除 Learning Context 之前的 prompt 审计快照。当前实现以章节正文为唯一事实源；Guide、Chat 与 Quiz 不再读取或生成持久化的 Learning Context。请以 `ARCHITECTURE.md` 为准。

 总入口
  所有真实 LLM 请求基本都收敛到 backend/app/services/translator.py:94：

  - complete(user_prompt, system_prompt, temperature)：非流式统一入口。
  - stream_messages(system_prompt, context, history)：流式聊天入口。
  - provider 分发：
      - OpenAI-compatible：system/user messages。
      - Gemini：system_instruction + contents。
      - Anthropic：system + user message。
  - 日志只记录长度、provider、model，不打印 prompt 正文，安全性还可以。

  1. 翻译流程
  入口：POST /books/{id}/translate -> BookService.process_book_translation() -> _translate_one_chapter() -> TranslatorService.translate_text()。

  关键位置：

  - 翻译调用：backend/app/services/book_service.py:166
  - 翻译 system prompt：backend/app/services/translator.py:121
  - 翻译完成后编译学习上下文：backend/app/services/book_service.py:191

  逻辑：

  1. 找出未翻译章节。
  2. 并发翻译，默认 TRANSLATION_CONCURRENCY=5。
  3. 每章原文作为 user prompt，翻译规则作为 system prompt。
  4. 写入 book_trans_md/。
  5. 基于原文和译文继续生成 learning context。

  完整性判断：

  - 主流程完整。
  - 数学 Markdown 保护目标明确：保留 Markdown、修复明显 LaTeX 错误、只输出译文。
  - 风险点：translate_text() 捕获异常后直接返回原文 backend/app/services/translator.py:140，上层会当作成功写入译文。这会污染后续 learning context 和 guide。
  - 风险点：整章一次性传入，没有 chunk/token 控制，长章节可能超上下文或被截断。

  2. 学习上下文编译
  入口：翻译完成后自动触发，或生成导读前补齐。

  关键位置：

  - prompt 构造：backend/app/services/learning_context_service.py:202
  - LLM 调用：backend/app/services/learning_context_service.py:252
  - 触发点：backend/app/services/book_service.py:191 和 backend/app/services/book_service.py:262

  逻辑：

  1. 原文截取 2000 字符，译文截取 7000 字符。
  2. prompt 要求返回 JSON：summary / concepts / key_theorems / dependencies。
  3. 用 llm_json.extract_json_candidate() 从返回中提取 JSON。
  4. 存成 Markdown，而不是 JSON。

  完整性判断：

  - 用 JSON schema 约束输出，解析也比较鲁棒。
  - 上下文内容正好服务后续 chat/quiz/guide。
  - 风险点：只取头尾 excerpt，中间核心定义/定理可能丢失。
  - 风险点：编译失败在翻译流程里只 warning，不阻断 backend/app/services/book_service.py:200，后续 guide 可能基于空上下文生成。

  3. Top-Down 导读生成
  入口：翻译完成后自动生成，或手动 POST /books/{id}/guides/top-down。

  关键位置：

  - prompt 构造：backend/app/services/guide_compiler_service.py:26
  - LLM 调用：backend/app/services/guide_compiler_service.py:148
  - 手动路由：backend/app/routers/guides.py:37

  逻辑：

  1. 读取所有章节 learning context。
  2. 拼成 chapter_contexts JSON。
  3. prompt 要求返回 { guides: [...] }，每个 guide 含 slug/title/scope/markdown。
  4. 规范化文件名和 scope 后写入 book_guides/ 与 guides.json。

  完整性判断：

  - 数据流合理：不是直接喂全文，而是用学习上下文生成导读。
  - 支持 book-level 和 chapter-level guide。
  - 风险点：chapter_contexts 没有限长，章节多时 prompt 可能过长。
  - 风险点：生成导读失败只 warning，不影响 book 最终 translated 状态 backend/app/services/book_service.py:279。

  4. Reader 聊天 / 笔记 / Quiz
  入口：前端 useChat() -> /chat/stream -> TranslatorService.stream_messages()。

  关键位置：

  - 后端 chat system prompt：backend/app/routers/chat.py:9
  - 流式序列化：backend/app/services/translator.py:311
  - 前端 history 构造：frontend/src/composables/useChat.js:38
  - 前端上下文构造：frontend/src/composables/useChapterLearningContext.js:23
  - Reader 根据当前阅读对象构造 context：frontend/src/views/Reader.vue:166

  逻辑：

  1. 用户选片段、本章、quiz 或 guide。
  2. 前端构造 context：
      - 章节：章节标题 + selected text + summary/concepts/theorems/dependencies。
      - guide/learning 等非章节：类型、标题、选中文本、可见正文前 12000 字。
  3. 前端把用户消息加入 messages。
  4. buildHistory() 对用户消息应用宏；对最后一条 user message 追加回答风格 prompt。
  5. 后端把 context + history 串成一个 user prompt，system prompt 固定为数学/物理 tutor。
  6. 流式返回 Markdown。

  完整性判断：

  - Reader 侧流程是闭环的：上下文来自当前阅读对象，聊天结果回写 note。
  - 支持 prompt macro 和 response style，后续 prompt 优化可以利用。
  - 风险点：后端没有把 history 作为真正多轮 chat messages 传给模型，而是序列化成一个大 user prompt backend/app/services/translator.py:311。这简化了多 provider 兼容，但会削弱 role
    语义。
  - 风险点：宏会应用到所有历史 user message，不只最新消息 frontend/src/composables/useChat.js:44。如果用户后来修改宏，旧消息的请求语义会变化。
  - 风险点：Quiz 没有专门 system prompt，本质还是通用 tutor，只靠上下文和用户输入驱动。

  5. 标题生成
  入口：首次创建聊天 note 后异步调用 /generate-title。

  关键位置：

  - 前端调用：frontend/src/composables/useChat.js:141 和 frontend/src/composables/useChat.js:257
  - 后端路由：backend/app/routers/legacy.py:102
  - prompt：backend/app/services/translator.py:393

  逻辑：

  - 只取 context 前 200 字符 + question。
  - system prompt 要求生成最多 5 个词的标题。
  - 失败回退 "Note"。

  完整性判断：

  - 功能独立，失败不影响主聊天。
  - 可以优化为中文标题、按 note 类型生成标题、限制标点和长度。

  6. 旧 ask-llm
  入口：POST /ask-llm。

  关键位置：

  - 路由：backend/app/routers/chat.py:20
  - prompt：backend/app/services/translator.py:195

  逻辑：

  - context + question。
  - 要求返回 JSON：title/content。
  - JSON 解析失败时返回原始内容。

  完整性判断：

  - 仍可用，但当前主 UI 更依赖 /chat/stream。
  - 这里 JSON 解析比 llm_json.extract_json_candidate() 弱，后续可统一。

  7. DeepTree Author Agent
  入口：兼容 `/agent/*` API 的 build / confirm / refine / regenerate 操作（前端控制台已下线）。

  关键位置：

  - Agent 统一适配：backend/app/services/agent_llm_adapter.py:20
  - Architect 调用：backend/app/services/agent_orchestrator.py:99
  - Refiner 调用：backend/app/services/agent_orchestrator.py:190
  - Writer 调用：backend/app/services/agent_orchestrator.py:360
  - Regenerate 调用：backend/app/services/agent_orchestrator.py:447
  - prompt 模板：
      - backend/app/skills/architect.md:1
      - backend/app/skills/refiner.md:1
      - backend/app/skills/writer.md:1

  逻辑：

  - architect：根据书名生成 vision/tree JSON。
  - refiner：根据当前 manifest 和用户修改指令更新 tree/vision。
  - writer：根据 vision、历史上下文、节点 id/title 写章节 Markdown。
  - regenerate：在 writer 上追加用户具体指令重写节点。

  完整性判断：

  - Agent prompt 是模板文件形式，适合后续集中优化。
  - 输出 JSON 的 architect/refiner 使用统一 JSON 提取。
  - writer 没有结构化输出校验，只直接写 Markdown。
  - 并发写作 semaphore=3，节点之间只带 recent history，不保证全书强一致性。

  后续 Prompt 优化建议
  优先级建议：

  1. 先抽象 prompt 注册表或模板层，把散落在 translator.py / learning_context_service.py / guide_compiler_service.py / skills/*.md / frontend styles 的 prompt 编号化、版本化。
  2. 修正翻译失败语义：LLM 失败不要返回原文当成功，至少标记 failed 或附带 error 状态。
  3. 聊天请求改为真实多 role messages，或者明确保留当前“串行化 prompt”但加强分隔符和 latest-user 指令。
  4. 给 Quiz 单独 system prompt，不要复用普通 tutor prompt。
  5. 给 learning context 和 guide 加 token/字符预算、分批汇总策略。
  6. 统一 JSON 解析：ask_llm() 也用 llm_json.extract_json_candidate()。
  7. 把 prompt macro 限制为只作用于最新用户消息，避免历史语义漂移。
