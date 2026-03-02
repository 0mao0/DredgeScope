# DredgeScope 项目文档

## 1. 项目概览
DredgeScope 是一个面向疏浚和海洋基础设施行业的综合情报系统。它自动完成行业新闻和船舶追踪数据的采集、分析与分发。

### 核心功能
- **自动采集**：从 RSS 源、网站（使用 Playwright）和微信公众号抓取新闻。
- **智能分析**：使用大模型（Qwen/Aliyun）进行文本分类、翻译和摘要生成。
- **船舶追踪**：使用 Fleet API 追踪疏浚船舶并在地图上可视化。
- **仪表盘**：基于 Vue 3 的前端界面，用于查看新闻、报告和船舶状态。
- **消息推送**：发送每日早报/晚报到企业微信（WeCom）。

## 2. 架构

### 目录结构
- `backend/`: Python 后端服务。
  - `acquisition/`: 数据采集模块。
    - `info_acquisition.py`: 新闻采集（RSS, Web）。
    - `wechat_acquisition.py`: 微信公众号采集。
    - `ship_status_fetcher.py`: 船舶状态抓取。
  - `analysis/`: 数据分析模块。
    - `info_analysis.py`: 新闻内容分析（LLM）。
    - `ships_status.py`: 船舶数据处理。
  - `reporting/`: 报告与服务模块。
    - `dashboard_server.py`: FastAPI 后端服务。
    - `report_generation.py`: 报告生成逻辑。
    - `wecom_push.py`: 企业微信推送。
  - `data/`: 数据存储。
    - `dredge_intel.db`: 主数据库 (SQLite)。
    - `ship_tracks.db`: 船舶轨迹数据库。
  - `scripts/`: 实用脚本（如初始化数据）。
  - `static/`: 静态资源与配置。
    - `sources.json`: 新闻源配置。
    - `continents.geojson`: 地图数据。
  - `config.py`: 全局配置管理。
    - 包含 API 密钥、路径配置、环境变量加载。
  - `main.py`: 采集任务入口。
  - `scheduler.py`: 任务调度器。
- `frontend/`: Vue 3 + TypeScript 前端。
  - `src/views/`: 页面视图 (`Dashboard`, `History`, `Statistics`, `VesselMap`)。
  - `src/components/`: 公共组件 (`NavBar` 等)。
  - `src/stores/`: Pinia 状态管理。
  - `src/router/`: 路由配置。
- `docker-compose.yml`: Docker 编排文件。
- `Dockerfile`: 后端容器构建文件。
- `nginx.conf`: Nginx 反向代理配置。

### 技术栈
- **前端**:
  - 核心: Vue 3.4+, TypeScript 5.4+, Vite 5.2+
  - UI: Ant Design Vue 4.x, Tailwind CSS (样式工具)
  - 状态/路由: Pinia, Vue Router 4.x
  - 可视化/地图: Chart.js, Leaflet
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
- Node.js >= 18.12.0, pnpm >= 7.0.0
- Python 3.11+
- Chrome/Chromium (用于 Playwright)

### 安装设置
1.  **前端**:
    ```bash
    cd frontend
    pnpm install
    ```
2.  **后端**:
    ```bash
    cd backend
    pip install -r requirements.txt
    playwright install chromium
    ```
3.  **环境变量**:
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

### 其他
- **语言**: 所有用户交互和注释请使用中文。
- **路径处理**: 使用 `os.path.join` 或绝对路径。
- **Playwright**: 处理动态网页时，注意等待选择器加载 (`page.wait_for_selector`)。
- **数据库**: 注意 SQLite 的并发限制，写入操作需谨慎。
