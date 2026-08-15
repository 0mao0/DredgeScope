# AI 正文清洗（content_clean）设计文档

日期：2026-08-15

## 背景与目标

新闻网页抓取文本中经常混入导航、面包屑、标签列表、相关新闻、订阅提示、页脚等冗余内容（例如 Dredging Today 页面尾部的“查看帖子标签”“相关新闻”“订阅通讯”区块）。这些冗余会：

- 占用 LLM 输入 token，增加成本；
- 干扰分类、摘要、翻译等分析的准确度；
- 长正文可能被 `text_content[:8000]` 截断，导致分析丢失主体。

目标：对每篇抓取文本调用一次 LLM 清洗，把结果存入独立字段 `content_clean`，后续 AI 分析（分类/摘要/翻译）和前端原文展示都基于清洗后的文本。

## 方案

采用用户已确认的方案：直接复用现有 Qwen 模型（`config.TEXT_MODEL` / `config.TEXT_LLM_API_KEY`），对每篇未清洗文章调用一次正文清洗，结果存 `articles.content_clean`。

## 范围

包含：

- `articles` 表新增 `content_clean TEXT` 列（`ALTER TABLE`，向后兼容旧库）；
- 新增规则预清洗 + LLM 清洗函数；
- 分析流程在分类/摘要/翻译之前先清洗，分析输入改用清洗后文本；
- 已清洗文章（`content_clean` 非空）跳过，不重复调用 LLM；
- API（`/api/events`、`/api/articles`、`/api/article/{id}`）返回 `content_clean`；
- 前端详情弹窗新增“原文”展示区，优先显示 `content_clean`，为空时隐藏；
- 提供手动批量补跑历史文章的入口（不自动执行）。

不包含：

- 不自动全量清洗历史 1857 篇文章（成本与耗时不可控）；
- 不修改采集模块；
- 不新增配置项（复用现有文本模型配置）；
- 不删除或修改现有 `content` 字段及历史行为。

## 数据流

```text
采集入库(content)
    ↓
process_items_from_db 处理每篇文章
    ↓
content_clean 为空且 content 非空？
    ├─ 否 → 跳过，直接使用已有 content_clean
    └─ 是 → clean_article_text() 规则预清洗
              ↓
            LLM 清洗（提示词同已验证版本）
              ↓
            成功 → 写回 articles.content_clean，item['content'] 替换为清洗结果
            失败 → 降级，保留原 content，流程继续
    ↓
分类 / 摘要 / 全文翻译（基于清洗后文本）
    ↓
API 返回 content_clean → 前端“原文”区展示
```

## 组件设计

### 1. database.py

- `init_db()`：在 `CREATE TABLE IF NOT EXISTS` 之外，追加兼容性检查：尝试 `SELECT content_clean FROM articles LIMIT 1`，若报错则 `ALTER TABLE articles ADD COLUMN content_clean TEXT`（与现有 `title_cn` 列迁移方式一致）。
- `get_articles_need_clean(limit=100)`：返回 `content_clean` 为空、`content` 非空、`valid = 1` 的文章，按 `id` 倒序。
- `update_content_clean(article_id, text)`：回写清洗结果。

### 2. analysis/info_analysis.py

- 新增模块级常量 `CLEAN_PROMPT`：使用已实际验证成功的提示词（要求只输出主体正文、去掉标签/相关新闻/订阅/导航等冗余、不翻译不总结不改写）。
- 新增 `async def clean_content_with_llm(client, item) -> str | None`：
  - 输入取 `item['content']`，先经现有 `clean_article_text()` 规则预清洗；
  - 文本过长时截断到合理上限（例如 12000 字符）再调用；
  - 返回模型输出的干净正文；异常返回 `None`。
- `process_items_from_db()`：在并发处理每篇文章时，先执行清洗：
  - 清洗成功：`database.update_content_clean()`，并把 `item['content']` 替换为清洗结果；
  - 清洗失败或已清洗：跳过，流程不变。
- `analyze_with_text()` 不需要改动：它读取的 `item['content']` 已被替换为清洗后文本。

### 3. reporting/dashboard_server.py

- `/api/events`、`/api/articles`、`/api/article/{article_id}` 三个查询的 `SELECT` 增加 `a.content_clean`（或 `content_clean`），返回给前端。

### 4. 前端

- `frontend/src/stores/index.ts`：`NewsItem` 增加 `content_clean?: string`。
- `frontend/src/views/Dashboard.vue` 与 `frontend/src/views/History.vue`：详情弹窗新增“原文”区块，`v-if="currentArticle?.content_clean"`，展示清洗后的正文；为空不渲染。

### 5. 手动补跑入口

- 新增 `backend/scripts/clean_content_backfill.py`：
  - 支持 `--limit N`（默认 100）、`--all`、`--ids 1,2,3`；
  - 复用 `info_analysis` 的清洗函数与 `database.get_articles_need_clean()`；
  - 并发 3，逐条回写；打印统计；
  - 不纳入自动调度，需要时手动运行。

## 错误处理与降级

- LLM 调用失败/超时：`clean_content_with_llm` 返回 `None`，`content_clean` 保持为空，分析继续使用原 `content`；
- 数据库回写失败：打印日志，不中断分析流程；
- `content` 为空或过短（< 50 字符）：跳过清洗；
- 并发控制与现有分析一致（`asyncio.Semaphore(3)`）。

## 验证

- 用 Boskalis《Seaway 启动首个项目》示例文本做回归用例：LLM 输出应只含主体正文，去除“查看帖子标签”“相关新闻”“订阅通讯”等冗余（该提示词已在真实环境验证通过）；
- 数据库迁移：在数据库副本上执行 `init_db()`，确认 `content_clean` 列可正常添加且旧数据不受影响；
- `python -m ruff check backend/`：本次新增代码不引入新的 lint 错误（仓库现存历史错误不处理）；
- `vue-tsc --noEmit` 通过；
- 启动 dashboard_server 后，调用三个 API 确认返回 `content_clean`。

## 成功标准

- 新采集文章分析时，`content_clean` 被写入且不含标签/相关新闻/订阅等冗余；
- 分析（分类/摘要/翻译）输入基于清洗后文本；
- 前端详情弹窗能看到“原文”区块（有清洗结果时）；
- 旧数据库无需手动重建即可升级。
