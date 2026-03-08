# DredgeScope 项目文档

## 1. 项目概览
DredgeScope 是一个面向疏浚和海洋基础设施行业的综合情报系统。它自动完成行业新闻和船舶追踪数据的采集、分析与分发。

### 核心功能
- **自动采集**：从 RSS 源、网站（使用 Playwright）和微信公众号抓取新闻，支持 72 小时时间窗口
- **智能分析**：使用大模型（Qwen/Aliyun）进行文本分类、翻译和摘要生成
- **船舶追踪**：使用 Fleet API 追踪疏浚船舶并在地图上可视化
- **Dashboard**: 基于 Vue 3 的前端界面，支持早报/晚报自动切换、历史归档、船舶分布与轨迹追踪
- **Map Visualization**: 支持天地图（矢量/卫星）与 ArcGIS（全球影像）无缝切换，解决海外区域地图覆盖问题
- **消息推送**: 发送每日早报/晚报到企业微信（WeCom）
- **健康监控**: 采集源状态实时监控与告警

## 2. 架构

### 目录结构
- `backend/`: Python 后端服务。
  - `acquisition/`: 数据采集模块。
    - `sources/base.py`: RSS 和 Web 采集基类
    - `sources/rss/`: RSS 源实现
    - `sources/web/`: Web 源实现
    - `wechat_acquisition.py`: 微信公众号采集
    - `ship_status_fetcher.py`: 船舶状态抓取
  - `analysis/`: 数据分析模块。
    - `info_analysis.py`: 新闻内容分析（LLM）
    - `ships_status.py`: 船舶数据处理
  - `reporting/`: 报告与服务模块。
    - `dashboard_server.py`: FastAPI 后端服务
    - `report_generation.py`: 报告生成逻辑
    - `wecom_push.py`: 企业微信推送
  - `data/`: 数据存储。
    - `dredge_intel.db`: 主数据库 (SQLite)
    - `ship_tracks.db`: 船舶轨迹数据库
  - `scripts/`: 实用脚本（如初始化数据）。
    - `init_ships.py`: 初始化船舶数据
    - `init_wechat_session.py`: 初始化微信 Session
  - `static/`: 静态资源与配置。
    - `sources.json`: 新闻源配置
    - `constants.py`: 常量定义（关键词、垃圾过滤等）
    - `wechat_session.json`: 微信 Session 存储（本地）
    - `continents.geojson`: 地图数据
  - `config.py`: 全局配置管理。
    - 包含 API 密钥、路径配置、环境变量加载
  - `database.py`: 数据库操作与模型定义
  - `main.py`: 采集任务入口
  - `scheduler.py`: 任务调度器
- `frontend/`: Vue 3 + TypeScript 前端。
  - `src/views/`: 页面视图 (`Dashboard`, `History`, `Statistics`, `VesselMap`, `AcquisitionProcess`)
  - `src/components/`: 公共组件 (`NavBar` 等)
  - `src/stores/`: Pinia 状态管理
  - `src/router/`: 路由配置
- `docker-compose.yml`: Docker 编排文件
- `Dockerfile`: 后端容器构建文件
- `nginx.conf`: Nginx 反向代理配置
- `AGENTS.md`: AI Agent 开发指南（基于 Harness Engineering）

### 技术栈
- **前端**:
  - 核心: Vue 3.4+, TypeScript 5.4+, Vite 5.2+
  - UI: Ant Design Vue 4.x, Tailwind CSS (样式工具)
  - 状态/路由: Pinia, Vue Router 4.x
  - 可视化/地图: Chart.js, Leaflet (支持天地图与ArcGIS切换)
  - 工具: Axios, Day.js, Marked
- **后端**:
  - 核心: Python 3.11+
  - Web: FastAPI, Uvicorn
  - 爬虫: Playwright 1.44+, Feedparser, Requests, BeautifulSoup4
  - 数据处理: Pandas, OpenPyXL
  - 地理信息: Reverse Geocoder, Pycountry
- **AI/LLM**:
  - 文本: SiliconFlow API (Qwen2.5-7B-Instruct)
  - 视觉: Aliyun DashScope (Qwen-VL)
- **数据库**: SQLite

## 3. 开发指南

### 前置要求
- Node.js >= 20.13.0, pnpm >= 7.0.0
- Python 3.11+
- Chrome/Chromium (用于 Playwright)

### 安装设置
1. **前端**:
   ```bash
   cd frontend
   pnpm install
   ```
2. **后端**:
   ```bash
   cd backend
   pip install -r requirements.txt
   playwright install chromium
   ```
3. **环境变量**:
   在项目根目录创建 `.env` 文件，配置 API 密钥（参考 `backend/config.py` 中的环境变量定义）。

### 运行项目
*   **本地开发（推荐）**:
   在项目根目录运行 `run_dev.bat`。这将分别在独立的窗口中启动前端、后端服务器和调度器。

*   **Docker 部署**:
   ```bash
   docker-compose up -d --build
   ```

*   **手动执行后端任务**:
   ```bash
   cd backend
   python run_tasks_manually.py
   # 测试模式:
   python run_tasks_manually.py --test
   ```

### 关键配置文件
- `backend/config.py`: 加载 `.env` 并定义全局常量。
- `backend/static/sources.json`: 生产环境新闻源配置。
- `frontend/vite.config.ts`: 前端构建配置。

## 4. AI 助手注意事项

### 代码规范
- **Python**:
  - 遵循 PEP 8 风格指南。
  - 使用 `snake_case` 命名变量和函数，`PascalCase` 命名类。
  - **必须**添加函数级文档字符串（Docstrings），描述功能、参数和返回值。
  - 函数外（上方）需增加一句话注释，说明函数的作用。
  - 推荐使用类型提示（Type Hints）。
  - 异步函数使用 `async/await` 模式。
- **Vue / TypeScript**:
  - 使用 Composition API (`<script setup lang="ts">`)。
  - 优先使用 Tailwind CSS 类进行样式编写，减少自定义 CSS/Less。
  - 组件命名使用 `PascalCase`（如 `NavBar.vue`）。
  - 变量和函数使用 `camelCase`。
  - 显式定义 props 和 emits 的类型。

### 文件定位指南
- **新增功能**：优先检查 `backend/acquisition`（采集）或 `frontend/src/views`（展示）。
- **修改配置**：查看 `backend/config.py` 或 `backend/static/sources.json`。
- **数据库变更**：检查 `backend/database.py` 中的模型定义。
- **采集源问题**：检查 `backend/acquisition/sources/base.py` 和 `backend/static/sources.json`。

### 其他
- **语言**: 所有用户交互和注释请使用中文。
- **路径处理**: 使用 `os.path.join` 或绝对路径。
- **Playwright**: 处理动态网页时，注意等待选择器加载 (`page.wait_for_selector`)。
- **数据库**: 注意 SQLite 的并发限制，写入操作需谨慎。
- **测试文件**: 放到 `/tests` 目录下，其他地方不要放。
- **健康监控**: 采集操作会自动记录健康状态，使用 `database.record_source_health()` 函数。

## 5. 采集源配置说明

### sources.json 配置项
```json
{
    "name": "Van Oord News",
    "url": "https://www.vanoord.com/en/updates/",
    "type": "web",
    "selector": "article, .news-item, .update-item",
    "url_patterns": ["/updates/", "/news/", "/projects/"],
    "blacklist": ["/user/", "/login", "/search"],
    "max_links": 15
}
```

配置项说明：
- `type`: `rss` | `web` | `wechat`
- `selector`: CSS 选择器，用于定位新闻列表容器
- `url_patterns`: URL 白名单模式（链接必须包含这些路径片段之一）
- `blacklist`: URL 黑名单模式（链接包含这些路径则排除）
- `max_links`: 单次最大抓取链接数

### 采集时间窗口
- RSS 源默认获取最近 72 小时的新闻（可在 `main.py` 中调整）
- 入库时会进行 5 天时效过滤

## 6. 健康监控

### 数据库表结构
`source_health` 表记录每次采集的状态：
- `source_name`: 采集源名称
- `source_type`: 采集源类型 (rss/web/wechat)
- `fetch_time`: 采集时间
- `items_fetched`: 获取到的条目数
- `items_new`: 新增条目数
- `status`: 状态 (success/failed/timeout)
- `error_message`: 错误信息
- `response_time_ms`: 响应时间(毫秒)

### 查询函数
- `get_source_health_summary(days=7)`: 获取健康状态摘要
- `get_source_health_alerts(hours=24, threshold=3)`: 获取告警列表
- `get_source_health_history(source_name, days=7)`: 获取历史记录

## 7. 常见问题排查

### 采集数量异常
1. 检查 `sources.json` 中的 `selector` 和 `url_patterns` 配置
2. 查看健康监控数据，确认采集源是否正常工作
3. 检查网站是否有反爬虫机制或结构变化

### 外国网站新闻少
1. 确认时间窗口设置（默认 72 小时）
2. 检查网站是否需要特殊处理（如 JavaScript 渲染）
3. 验证选择器是否正确匹配新闻列表

### 数据库写入失败
1. 检查 SQLite 并发限制
2. 确认数据库文件权限
3. 查看错误日志定位具体问题
