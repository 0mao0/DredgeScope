# 企业微信推送改版设计（AI 重要度打分 + 重要新闻列表）

日期：2026-08-13
状态：设计已与用户确认

## 1. 背景与问题

当前定点 webhook 通知（每日早报/晚报）只发送一张"总结式"企业微信模板卡片：

- 卡片里只有分类统计，没有具体新闻，用户不知道有什么值得看的内容；
- 卡片图片（截图）使用 `http://IP:8000/assets/...` 地址，企业微信无法稳定加载；
- 整卡只有一个跳转链接，点击率低。

## 2. 目标与非目标

### 目标

- 在推送中直接展示 3~5 条重要新闻，每条可单独点击进入系统查看完整详情；
- 重要度由现有 AI 分析环节通过提示词打分，写入数据库已有的 `is_significant` 字段；
- 推送不再依赖截图图片，消除图片加载不出来的问题；
- 保留汇总信息（本次更新条数、分类分布）；
- 前端支持 `?id={article_id}` 直达并自动打开现有详情弹窗。

### 非目标

- 不接入 HTTPS 域名/证书（通过新增 `PUSH_BASE_URL` 配置预留切换能力）；
- 不做截图上传、图床或图片处理；
- 不新建独立详情页；
- 不修改推送时间窗口（早报 00:00-08:00、晚报 08:00-18:00 逻辑不变）；
- 不修改采集、分类、摘要等既有分析能力。

## 3. 总体结构

```
acquisition（不变）
  → analysis：现有 LLM 分析新增 significance 打分
  → database：写入 is_significant（列已存在，无需迁移）
  → reporting：推送单条消息（汇总 + 重要新闻列表）
  → frontend：/?id=N 直达详情弹窗
```

依赖方向不变：analysis 只写字段，reporting 只读取，frontend 通过现有 API 取详情。

## 4. AI 重要度打分

### 4.1 文本分析（`backend/analysis/info_analysis.py` 的 `analyze_with_text`）

在现有 JSON 输出 schema 中增加字段：

```json
{
  "is_junk": false,
  "category": "Bid",
  "title_cn": "...",
  "summary_cn": "...",
  "full_text_cn": "...",
  "publish_time": "YYYY-MM-DD",
  "significance": 8
}
```

提示词增加评分说明（放在任务说明末尾）：

> 8. 【重要度打分】(significance) - 基于以下标准输出 0-10 的整数，数字越大越重要：
>    - 与疏浚、港口、航道、海洋工程的直接相关度（相关度越高分越高）；
>    - 商业价值：中标、合同、金额、大型企业动态（金额越大、企业越知名分越高）；
>    - 影响范围：国家级/区域级项目、法规政策变化、重大事故或里程碑；
>    - 时效性：新发布、正在进行的重大事件优先。
>    只输出整数，不要输出小数或理由。

### 4.2 视觉分析（`analyze_with_vl`）

VL 输出目前是 6 行自然语言，新增第 7 行：

```text
7. 重要度打分：只输出 0-10 的整数
```

解析使用正则：`^7\.\s*(?:[^\n]*?)(\d{1,2})\s*$`（锚定行尾，避免误取范围描述里的数字），匹配失败时该条不计分（留空，由推送端兜底）。

### 4.3 归一化与兜底

- 垃圾/无效文章（`is_junk`、`is_relevant_news` 判定失败、明显垃圾标题）在 `_build_final_result` 中统一置 `significant: 0`；
- 分数解析后做 `clamp(0, 10)` 并转整数；
- 模型漏打分（None）时保留 `None`，不强制给分；
- `_build_final_result` 最终结果中携带 `significant` 字段，与现有 `upsert_article` 的 `significant` 参数对齐（`database.py` 已支持写入 `is_significant`）。

### 4.4 存储与查询

- `database.get_articles_by_time_range_strict` 的 SELECT 增加 `a.is_significant`，返回字典中暴露为 `significance`；
- 无需改表结构或迁移。

## 5. 推送改造（`backend/reporting/wecom_push.py`）

推送窗口、`get_push_window`、无情报文本消息保持现状。有情报时发送**一条** `news` 图文消息：

### 5.1 单条重要新闻消息（news）

- 取当前窗口内 `is_retained=1` 的文章；
- 排序：`significance` 降序（None 排最后）→ 分类优先级（Bid > Project > Equipment > Regulation > R&D > Market）→ `created_at` 降序；
- 取前 3~5 条（有 1 条就发 1 条，最多 5 条）；
- 消息结构：
  - **第一张卡片 = 汇总**：标题为"{label} · 更新 N 条"，描述为分类分布，点击进入系统总览（`{PUSH_BASE_URL}/?mode=recent`）；
  - **中间卡片 = 重要新闻**，每条 article：
  - `title`：`title_cn` 或 `title`，截断到 40 个字符（约 120 字节，企业微信限制 128 字节）；
  - `description`：`summary_cn`，截断到 160 个字符（约 480 字节，企业微信限制 512 字节）；无摘要时用标题；
  - `url`：`{PUSH_BASE_URL}/?id={article_id}`；
  - 不设置 `picurl`。
  - **最后一张卡片 = "查看全部 N 条 →"**，`url` 指向 `{PUSH_BASE_URL}/?mode=recent`；
  - 总条数 ≤ 7（1 条汇总 + 5 条新闻 + 1 条查看全部），在企业微信 8 条上限内。

### 5.3 PUSH_BASE_URL 配置

- `backend/config.py` 新增 `PUSH_BASE_URL = os.getenv("PUSH_BASE_URL") or BACKEND_URL`；
- 所有推送跳转链接统一使用 `PUSH_BASE_URL` 拼接；
- 文档注明：后续接入 HTTPS 域名后，只需在 `.env` 配置 `PUSH_BASE_URL=https://域名`，无需改代码。

### 5.4 无新闻

保持现有逻辑：发送"【全球疏浚情报 {label}】暂无最新情报更新"文本消息。

### 5.5 失败降级

- 单条 news 消息发送失败：降级为一条 markdown 文本，内容为汇总信息 + 每条新闻 `[标题](url)` 链接；
- 降级也失败：写调度日志，不重复重试。

## 6. 前端直达（`frontend/src/views/Dashboard.vue`）

- 引入 `useRoute`，`onMounted` 完成现有数据加载后读取 `route.query.id`；
- 若存在 `id`，调用现有接口 `/api/article/{id}`；
- 返回有效文章时，映射为 `NewsItem`（含 `details`），设置 `currentArticle` 并打开现有详情弹窗（复用 `openDetail` 逻辑）；
- `id` 无效、接口失败或文章不存在：不弹窗、不报错、不影响正常页面加载；
- 只在首次挂载时处理直达参数，不新增路由监听（企业微信点击会新开页面）。

## 7. 错误处理与降级汇总

| 场景 | 行为 |
|------|------|
| LLM 未返回 significance | 留空，排序时按分类优先级兜底 |
| significance 非法（非整数/越界） | clamp 到 0-10，解析失败置空 |
| 窗口内无文章 | 发送"暂无更新"文本 |
| 窗口内只有 1-2 篇文章 | 有多少发多少 |
| 汇总卡片发送失败 | 文本降级 |
| 新闻列表发送失败 | markdown 链接降级 |
| 文章无摘要 | description 用标题 |
| Webhook 未配置 | 写调度日志并返回，不发送 |

## 8. 测试计划

测试文件放在 `tests/`：

- `test_significance.py`：VL 第 7 行解析、文本 JSON 解析、clamp/归一化；
- `test_wecom_payload.py`：新闻列表排序与兜底、标题/摘要截断、news payload 结构、查看全部条目、空列表行为、失败降级逻辑；
- `test_frontend_deeplink` 不单独建前端测试，通过手动验证 + `pnpm run lint` 覆盖。

手动验证：

1. 后端脚本 dry-run 打印单条消息 payload；
2. 向测试群发送真实推送，确认第一条为汇总、中间 3~5 条新闻、每条可跳转；
3. 点击新闻条目确认打开对应详情弹窗；无效 id 不弹窗。

## 9. 验证清单

- [ ] `ruff check backend/` 通过
- [ ] `pnpm run lint` 通过
- [ ] `pytest` 新增用例通过
- [ ] 数据库无迁移（`is_significant` 列已存在）
- [ ] 新增配置 `PUSH_BASE_URL` 有默认值（回退 `BACKEND_URL`）
- [ ] 日志使用 `[Push]` / `[Text]` / `[VL]` 前缀，符合 AGENTS.md 规范

## 10. 涉及文件

| 文件 | 改动 |
|------|------|
| `backend/analysis/info_analysis.py` | 文本/视觉提示词加 significance、解析与归一化 |
| `backend/database.py` | 时间窗口查询返回 `significance` 字段 |
| `backend/reporting/wecom_push.py` | 汇总卡片去图、新增 news 新闻列表、降级逻辑 |
| `backend/config.py` | 新增 `PUSH_BASE_URL` |
| `frontend/src/views/Dashboard.vue` | `?id=` 直达打开详情弹窗 |
| `.env`（部署时） | 可选配置 `PUSH_BASE_URL` |
| `tests/` | 新增打分与推送 payload 测试 |
