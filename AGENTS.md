# DredgeScope AI Agent 规范

> 本文档定义 AI 智能体在项目中的行为准则与代码规范。AI 必须严格遵守。

## 1. 核心原则

### 分层依赖
```
Types → Config → Database → Acquisition/Analysis → Reporting → Frontend
```
- 依赖**单向流动**，禁止循环依赖
- 前端不得直接访问数据库，必须通过 API

### 模块边界
| 模块 | 职责 | 禁止事项 |
|------|------|---------|
| `acquisition` | 数据采集、入库 | ❌ 不做分析、不生成报告 |
| `analysis` | LLM分析、分类、翻译 | ❌ 不做采集、不直接推送 |
| `reporting` | 报告生成、API服务、推送 | ❌ 不做采集、不修改分析逻辑 |
| `frontend` | UI展示、用户交互 | ❌ 不直接访问数据库 |

## 2. 代码规范

### Python
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
    pass
```

- 命名：`snake_case` 变量/函数，`PascalCase` 类名
- 必须添加函数级文档字符串
- 函数外上方需有一句话注释说明作用
- 推荐使用类型提示
- 异步函数使用 `async/await`

### Vue/TypeScript
```vue
<script setup lang="ts">
interface ArticleItem {
  id: number
  title: string
}

const props = defineProps<{ articles: ArticleItem[] }>()
const emit = defineEmits<{ (e: 'select', article: ArticleItem): void }>()
</script>
```

- 使用 Composition API (`<script setup lang="ts">`)
- 优先使用 Tailwind CSS
- 组件命名 `PascalCase`，变量/函数 `camelCase`
- 显式定义 props 和 emits 类型

## 3. 错误处理

```python
# ✅ 正确示例 - 记录健康状态并优雅降级
try:
    items = await source.fetch(hours=hours)
except Exception as e:
    logger.error(f"[{source.name}] 采集失败: {e}")
    record_source_health(source.name, 'failed', error_message=str(e))
    items = []  # 优雅降级
```

## 4. 日志规范

- 使用 `[模块名:来源]` 前缀标识日志来源
- 例: `[RSS:Dredging Today] 正在抓取...`
- 例: `[Web:Van Oord] 获取 3 篇文章`

## 5. 文件定位

| 任务 | 文件 |
|------|------|
| 修改采集源配置 | `backend/static/sources.json` |
| 修改全局配置 | `backend/config.py` |
| 修改数据库模型 | `backend/database.py` |
| 修改采集逻辑 | `backend/acquisition/sources/base.py` |
| 修改分析逻辑 | `backend/analysis/info_analysis.py` |
| 修改前端页面 | `frontend/src/views/` |
| 修改API接口 | `backend/reporting/dashboard_server.py` |

## 6. 验证清单

提交代码前必须确保：
- [ ] Python 代码通过 `ruff check backend/`
- [ ] 前端代码通过 `pnpm run lint`
- [ ] 数据库变更向后兼容
- [ ] 新增配置有默认值
- [ ] 新增采集源已测试

## 7. 测试文件

- 所有测试文件放在 `/tests` 目录
- 命名: `test_*.py` 或 `*_test.py`

## 8. 其他

- **语言**: 所有用户交互和注释使用中文
- **路径**: 使用 `os.path.join` 或绝对路径
- **数据库**: 注意 SQLite 并发限制
- **健康监控**: 使用 `database.record_source_health()` 记录采集状态
