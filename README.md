# NOI_backEnd 后端项目分析报告

> 生成时间：2026-03-20    
> 说明：本 README 汇总了对当前工作区后端代码的结构化梳理。任何 `.env` 中的真实密钥/密码均不会出现在文档中（已脱敏）。

## 0. 概览

该后端以「NoI 智能科研助手」为目标，围绕以下能力构建：

1. 文档摄入与结构化分析：通过 **RAGFlow** 完成上传、解析切片、切片获取；并由本地 LLM 将切片内容输出为结构化 JSON（summary/categories/topics/mind_map 等）。
2. 向量与语义去重：通过 **Xinference/OpenAI 兼容 embedding** 生成向量，并使用 **PostgreSQL + pgvector** 在 `topics` 等表中做相似度合并。
3. 个性化用户画像与上下文注入：使用行为追踪事件构建行为图谱（Neo4j + SQL 后备），再进行三维度画像分析（知识结构/学术风格/思维模式），最后在对话时注入上下文。
4. 双层记忆系统：短期记忆（STM）与长期记忆（LTM）提供创建、查询、巩固、冲突仲裁、注意力分配等能力。
5. Agent 会话引擎：提供 `SessionLoop`（流式/非流式）驱动 **LLM 工具调用**、Doom Loop 防护与工具执行迭代。

整体架构：
- API 层：`app/api/*`（`main.py` 注册 `api_router`）
- 服务层：`app/services/*`（LLM、Embedding、RAGFlow、图谱、记忆、工具系统、上下文聚合器）
- 数据层：`app/models/*`（SQLAlchemy + pgvector；行为图谱主要写 Neo4j）

---

## 1. 核心技术栈与工具链 (Technical Stack)

### 1.1 后端框架
| 类别 | 实现 |
|---|---|
| Python Web 框架 | `FastAPI` |
| ASGI Server | `uvicorn[standard]` |
| API 路由组织 | `/api` -> `/api/v1`（`app/api/api.py`、`app/api/v1/api.py`） |

### 1.2 数据库与存储
| 类别 | 实现 |
|---|---|
| 关系型数据库 | PostgreSQL（`DATABASE_URL`）+ `SQLAlchemy` ORM |
| 迁移 | `alembic` |
| 向量存储（Vector DB） | **PostgreSQL + pgvector**（`pgvector==0.3.6`，`Vector(...)` 字段） |
| 图数据库 | **Neo4j**（`neo4j==5.15.0`） |

关键点：
- `app/models/*` 多处定义了 `pgvector.sqlalchemy.Vector` 字段（例如 `topics.embedding`、`ShortTermMemory/LongTermMemory.embedding`、`InteractionEvent.feature_vector`）。
- `BehaviorGraphBuilder` 写 Neo4j，并在 Neo4j 不可用时进行 SQL 后备/降级策略（代码中存在 `_require_neo4j()` 与 fallback 逻辑）。

### 1.3 第三方工具与 API 集成
1. **RAGFlow API**
   - 文档上传/解析/切片拉取：由 `app/services/ragflow.py` 实现
   - 对话补全：由 `app/api/v1/endpoints/chat.py` 代理到 RAGFlow 的 `/completions`
   - 会话管理：会话创建/删除/历史拉取也走 RAGFlow
2. **LLM（OpenAI 兼容接口）**
   - 使用 `openai` 的 `AsyncOpenAI`
   - base_url 指向 **Ollama** 的 OpenAI 兼容 `v1` 接口（`.env` 中 `LLM_BASE_URL`）
   - `app/services/llm.py` 负责文档 JSON 化分析
3. **Embedding（OpenAI 兼容 / Xinference）**
   - `app/services/embedding.py` 使用 `AsyncOpenAI.embeddings.create`
   - base_url 与 `EMBEDDING_MODEL_UID` 来指定 embedding 模型
4. **MCP（Model Context Protocol）**
   - 存在 MCP 工具桥接与工具注册体系（`app/services/tools/mcp_bridge.py`、`registry.py`）
   - 但当前桥接实现包含占位/模拟：工具发现返回空列表，调用返回模拟输出
   - 因此：**MCP 工具调用并未形成可用闭环**

### 1.4 依赖管理（requirements.txt 核心库）
`requirements.txt` 包含关键库：
- `fastapi`, `uvicorn[standard]`
- `sqlalchemy`, `psycopg2-binary`, `alembic`
- `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt`
- `httpx`
- `openai`（LLM 与 Embedding 的兼容调用）
- `pgvector`
- `neo4j`
- `structlog`, `pytest`, `pytest-asyncio`, `numpy`

---

## 2. AI 核心技术应用 (AI Capabilities)

### 2.1 RAG（检索增强生成）
该项目的“RAG 典型链路”主要由 **RAGFlow** 承担。后端主要做两件事：

1. 文档结构化分析闭环（RAGFlow + 本地 LLM + pgvector 去重）
2. 对话代理与引用落库（把 RAGFlow 的答案与 reference 写回本地 DB，支持流式 SSE 转发）

文档分析/闭环（由 `app/services/ragflow.py`）：
1. 上传文件到 RAGFlow：`POST /api/v1/datasets/{dataset_id}/documents`
2. 触发解析切片：`POST /api/v1/datasets/{dataset_id}/chunks`
3. 轮询文档状态：`GET /api/v1/datasets/{dataset_id}/documents?id=...`
4. 拉取切片文本：`GET /api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks`
5. 将切片拼接后交给本地 LLM 输出 JSON：`llm_service.analyze_content(chunks_text)`
6. 调用 `process_tags(db, raw_topics)`：
   - 使用 `embedding_service.get_embedding(tag)` 生成向量
   - 通过 `pgvector` 在 `topics` 表做相似度匹配与合并（语义去重）
7. 写入 `assets` 表：`summary/tags/topics/categories/mind_map_json/status`

对话链路（由 `app/api/v1/endpoints/chat.py`）：
- 认证：`get_current_user`（JWT Bearer）
- 校验会话属于用户
- 需要时注入画像 + 记忆聚合上下文（`ContextAggregator`）
- 代理请求到 RAGFlow：`POST /api/v1/chats/{chat_id}/completions`
- 流式时把 RAGFlow SSE 原样转发；同时解析并保存 `reference`

结论：
- 聊天检索/生成：主要在 RAGFlow 内部完成
- 后端的向量检索：主要落在标签/主题语义去重（`topics` 的 pgvector）

### 2.2 模型微调 (Fine-tuning)
- 未发现相关实现：仓库中没有训练脚本、LoRA/QLoRA/peft 或微调配置。
- 当前主要是推理调用（LLM 与 Embedding 通过 OpenAI 兼容接口在线调用）。

### 2.3 大模型交互与 Prompt 管理
1. 文档深度分析（`app/services/llm.py`）
   - Prompt 要求：严格输出 JSON，不要 Markdown
   - 用正则提取 `{...}` JSON 片段后 `json.loads`
   - JSON 解析失败回退 fallback 数据
2. SessionLoop（Agent）
   - 使用 OpenAI 工具调用协议：传入 `tools=[...]` 与 `tool_choice="auto"`
   - 通过流式 `chat.completions.create(stream=True)` 解析 `delta.tool_calls`
   - tool 执行结果回填为 `role="tool"` 并继续迭代

### 2.4 MCP 集成现状（重要）
- 存在 MCP 工具桥接与工具抽象层，但当前工具发现与调用是占位/模拟。
- 因此：**MCP 工具调用闭环目前不可用**。

---

## 3. 产品功能与业务逻辑 (Features & Purpose)

### 3.1 核心功能清单（对外 API）
主要 API（前缀 `api/v1`）：

1. 认证（`/api/auth`）
   - `POST /register`
   - `POST /login`
   - `POST /logout`
   - `GET /me`
   - `PUT /me`
   - `GET /verify-token`

2. 文档上传与资产管理（`/api/v1/upload`、`/api/v1/assets`）
   - `POST /upload/file`
   - `POST /upload/init`、`POST /upload/chunk`、`GET /upload/status/{upload_id}`
   - `POST /upload/complete`、`POST /upload/abort`
   - `PATCH /assets/{asset_id}`
   - `POST /assets/check-duplicates`
   - `GET /constellation/data`、`GET /galaxy/data`
   - `GET /assets/list`、`GET /assets/{asset_id}`、`GET /assets/{asset_id}/file`
   - `POST /assets/{asset_id}/retry`
   - `DELETE /assets/{asset_id}`
   - `GET /assets/{asset_id}/status`

3. 聊天（RAGFlow 代理，含上下文注入与引用落库）
   - `POST /chat/completions`
   - `GET /chat/sessions`
   - `POST /chat/sessions`
   - `PATCH /chat/sessions/{session_id}`
   - `DELETE /chat/sessions/{session_id}`
   - `GET /chat/sessions/{session_id}/history`
   - `DELETE /chat/sessions/{session_id}/messages/truncate`
   - `GET /chat/images/{image_id}`

4. 行为追踪（行为图谱事件流）
   - `POST /behavior/track`
   - `POST /behavior/batch`
   - `GET /behavior/events`
   - `GET /behavior/events/{event_id}`
   - `GET /behavior/events/{event_id}/parts`
   - `POST /behavior/events/{event_id}/parts`
   - `GET /behavior/graph/stats`
   - `GET /behavior/graph/event-nodes`
   - `GET /behavior/graph/object-nodes`
   - `GET /behavior/event-types`

5. 画像（科研画像分析）
   - `POST /profile/analyze`
   - `GET /profile/analyze/quick`
   - `GET /profile/context`、`POST /profile/context`
   - `GET /profile/context/quick`
   - `GET /profile/summary`
   - `GET /profile/knowledge-structure`
   - `GET /profile/academic-style`
   - `GET /profile/thinking-pattern`
   - `GET /profile/dimensions`

6. 双层记忆（`/api/v1/memory`）
   - 短期/长期/巩固/注意力/冲突仲裁/上下文导出等接口

7. Session Engine（Agent + 工具调用）
   - `POST /session/chat`
   - `GET /session/status/{session_id}`
   - `GET /session/tools`

### 3.2 核心目的（痛点与业务目标）
从代码命名与主链路逻辑推断：

1. 将科研文档转为结构化、可检索、可沉淀的知识资产
   - 上传后自动解析、总结、主题/标签抽取
   - embedding + pgvector 做语义去重，减少知识库污染
2. 把用户行为与偏好沉淀为画像，并注入对话上下文
   - 行为图谱 -> 三维画像 -> ContextAggregator 注入
3. 把对话过程 Agent 化
   - LLM 工具调用循环 + Doom Loop 防护
   - 对话结束写入 STM，参与后续上下文

---

## 4. 优势与创新点 (Advantages & Innovations)

### 4.1 技术亮点
1. 文档摄入与结构化分析闭环（RAGFlow + 本地 LLM + pgvector 去重 + 落库）
2. 流式 SSE 代理与引用落库
3. 个性化上下文聚合（token 预算、缓存、截断）
4. 记忆系统具备冲突治理与注意力分配机制
5. 行为图谱层支持 Neo4j 降级策略
6. Agent 会话引擎具备工具 schema 与迭代控制（最大迭代次数、工具调用次数限制、上下文压缩、Doom Loop）

### 4.2 产品创新点
1. 将画像（profile）+ 记忆（memory）+ 工具调用（tools）形成可注入上下文与可控迭代链路
2. 相比传统“向量检索->生成”的 RAG，这里强调“用户个性化记忆与认知特征”的工程化注入

---

## 5. 当前缺口与状态判断

1. RAGFlow 驱动的文档摄入、结构化分析、聊天代理：已形成闭环并可落库。
2. 向量能力：
   - 已落地：`topics` 的语义去重使用 pgvector
   - 但 STM/LTM 的 embedding 在 SessionLoop 写入链路中未显式生成，因此向量检索对记忆的作用有限
3. MCP 工具调用：
   - 存在框架但关键步骤未打通（发现与调用目前为模拟）
4. 微调：
   - 未发现训练/LoRA/微调实现

---

## 6. 建议的下一步（可选）

1. 补齐 MCP 闭环：实现工具发现与 tools/call 调用。
2. 强化记忆向量化：在写入 STM/LTM 时生成 embedding，并基于向量实现记忆检索注入。
3. 将内置 tools（`knowledge_search` 等）从模拟接入真实数据源（RAGFlow/pgvector/文档存储）。

