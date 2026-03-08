# DredgeScope AI Agent 指南

> 基于 OpenAI Harness Engineering 最佳实践，为 AI 智能体提供项目导航与开发规范。

## 1. 项目入口与地图

本文件是 AI 智能体在 DredgeScope 项目中的导航入口。请按需深入，而非一次性加载全部上下文。

### 核心目录结构
```
dredgescope/
├── backend/                 # Python 后端服务
│   ├── acquisition/         # 数据采集模块 → 详见 docs/acquisition.md
│   ├── analysis/            # 数据分析模块 → 详见 docs/analysis.md
│   ├── reporting/           # 报告与推送模块 → 详见 docs/reporting.md
│   ├── static/              # 静态配置与资源
│   ├── data/                # 数据存储 (SQLite)
│   ├── config.py            # 全局配置入口
│   ├── main.py              # 采集任务入口
│   └── scheduler.py         # 任务调度器
├── frontend/                # Vue 3 + TypeScript 前端
│   ├── src/views/           # 页面视图
│   ├── src/components/      # 公共组件
│   └── src/stores/          # Pinia 状态管理
└── docs/                    # 详细文档目录
```

### 关键文件快速索引
| 任务类型 | 首选文件 | 说明 |
|---------|---------|------|
| 修改采集源配置 | `backend/static/sources.json` | RSS/Web/WeChat 源定义 |
| 修改全局配置 | `backend/config.py` | API密钥、路径、环境变量 |
| 修改数据库模型 | `backend/database.py` | SQLite 表结构定义 |
| 修改采集逻辑 | `backend/acquisition/sources/base.py` | RSS/Web 基类 |
| 修改分析逻辑 | `backend/analysis/info_analysis.py` | LLM 分析入口 |
| 修改前端页面 | `frontend/src/views/` | Dashboard, Map, History 等 |
| 修改API接口 | `backend/reporting/dashboard_server.py` | FastAPI 路由 |

## 2. 架构约束

### 分层依赖原则
```
Types → Config → Database → Acquisition/Analysis → Reporting → Frontend
```
- 依赖必须沿此有向图**单向流动**
- 禁止循环依赖
- 前端不得直接访问数据库，必须通过 API

### 模块边界
| 模块 | 职责 | 禁止事项 |
|------|------|---------|
| `acquisition` | 数据采集、入库 | ❌ 不做分析、不生成报告 |
| `analysis` | LLM分析、分类、翻译 | ❌ 不做采集、不直接推送 |
| `reporting` | 报告生成、API服务、推送 | ❌ 不做采集、不修改分析逻辑 |
| `frontend` | UI展示、用户交互 | ❌ 不直接访问数据库 |

### 命名约定
- **Python**: `snake_case` 变量/函数, `PascalCase` 类名
- **Vue/TS**: `camelCase` 变量/函数, `PascalCase` 组件名
- **数据库**: `snake_case` 表名和字段名
- **常量**: `UPPER_SNAKE_CASE`

## 3. 开发规范

### Python 代码规范
```python
# ✅ 正确示例
async def fetch_articles(source_name: str, hours: int = 24) -> List[Dict[str, Any]]:
    """
    获取指定采集源的文章列表
    
    Args:
        source_name: 采集源名称
        hours: 获取最近几小时的文章
        
    Returns:
        文章字典列表
    """
    # 函数外上方需有一句话注释说明函数作用
    pass
```

### Vue/TypeScript 代码规范
```vue
<script setup lang="ts">
// ✅ 正确示例
interface ArticleItem {
  id: number
  title: string
  url: string
}

const props = defineProps<{
  articles: ArticleItem[]
}>()

const emit = defineEmits<{
  (e: 'select', article: ArticleItem): void
}>()
</script>
```

### 错误处理规范
```python
# ✅ 正确示例 - 记录健康状态并优雅降级
try:
    items = await source.fetch(hours=hours)
except Exception as e:
    logger.error(f"[{source.name}] 采集失败: {e}")
    record_source_health(source.name, 'failed', error_message=str(e))
    items = []  # 优雅降级，不中断整体流程
```

### 日志规范
- 使用 `[模块名:来源]` 前缀标识日志来源
- 例: `[RSS:Dredging Today] 正在抓取...`
- 例: `[Web:Van Oord] 成功获取 5 条新闻链接`

## 4. 测试与验证

### 测试文件位置
- 所有测试文件放在 `/tests` 目录下
- 测试文件命名: `test_*.py` 或 `*_test.py`

### 验证清单
在提交代码前，请确保：
- [ ] Python 代码通过 `ruff check backend/` 检查
- [ ] 前端代码通过 `pnpm run lint` 检查
- [ ] 数据库变更已在 `database.py` 的 `init_db()` 中处理向后兼容
- [ ] 新增配置项已在 `config.py` 中定义默认值
- [ ] 新增采集源已在 `sources.json` 中配置并测试

### 手动测试命令
```bash
# 后端单次采集测试
cd backend && python run_tasks_manually.py --test

# 前端开发服务器
cd frontend && pnpm run serve

# 后端开发服务器
cd backend && python -m uvicorn reporting.dashboard_server:app --reload
```

## 5. 常见任务指南

### 添加新的采集源
1. 在 `backend/static/sources.json` 添加源配置
2. 如果是特殊网站，可能需要在 `backend/acquisition/sources/` 创建专用类
3. 运行 `python run_tasks_manually.py --test` 验证

### 修改分析提示词
1. 定位 `backend/analysis/info_analysis.py`
2. 修改对应的 prompt 模板
3. 注意保持 prompt 的结构化格式

### 添加新的 API 端点
1. 在 `backend/reporting/dashboard_server.py` 添加路由
2. 遵循 RESTful 命名约定
3. 添加适当的错误处理和日志

### 修改前端页面
1. 在 `frontend/src/views/` 找到对应页面
2. 使用 Composition API (`<script setup lang="ts">`)
3. 优先使用 Tailwind CSS 进行样式编写

## 6. 质量保障机制

### 自动化检查
- **Linter**: Python (ruff), TypeScript (ESLint)
- **类型检查**: Python (type hints), TypeScript (tsc)
- **架构约束**: 通过代码审查确保模块边界

### 代码评审要点
1. 是否遵循分层依赖原则？
2. 是否有适当的错误处理和日志？
3. 数据库变更是否向后兼容？
4. 新增配置是否有默认值？

### 重构指南
当发现以下情况时，应考虑重构：
- 函数超过 50 行
- 模块间存在循环依赖
- 相同逻辑在多处重复
- 测试覆盖率低于 50%

## 7. 上下文工程技巧

### 渐进式信息获取
AI 智能体应按需获取信息，避免一次性加载过多上下文：
1. 先阅读本文件了解项目结构
2. 根据任务定位具体模块
3. 只在必要时深入阅读详细文档

### 有效提问模式
```
❌ 错误: "帮我看看代码有什么问题"
✅ 正确: "在 backend/acquisition/sources/base.py 的 WebSource.fetch 方法中，
       添加 url_patterns 过滤逻辑后，测试发现所有链接都被过滤掉了，
       请检查 _is_valid_link 方法的逻辑是否正确"
```

### 任务分解策略
对于复杂任务，应分解为小步骤：
1. 先理解现有代码结构
2. 设计变更方案
3. 逐步实现并验证
4. 最后进行整体测试

## 8. 文档索引

详细文档位于 `docs/` 目录：
- `docs/acquisition.md` - 采集模块详细设计
- `docs/analysis.md` - 分析模块详细设计
- `docs/reporting.md` - 报告与推送模块详细设计
- `docs/database.md` - 数据库设计文档
- `docs/api.md` - API 接口文档

---

**注意**: 本文件应保持在约 100 行左右，作为入口索引。详细内容请查阅对应的详细文档。
