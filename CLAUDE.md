# DredgeScope 项目文档

## 1. 项目概览
DredgeScope 是一个面向疏浚和海洋基础设施行业的综合情报系统。它自动完成行业新闻和船舶追踪数据的采集、分析与分发。

### 核心功能
- **自动采集**：从 RSS 源、网站（使用 Playwright）和微信公众号抓取新闻。
- **智能分析**：使用大模型（Qwen/Aliyun）进行文本分类、翻译和摘要生成。
- **船舶追踪**：使用 Fleet API 追踪疏浚船舶并在地图上可视化。
- **仪表盘**：基于 Vue 3 的前端界面，用于查看新闻、报告和船舶状态。
- **消息推送**：发送每日日报到企业微信（WeCom）。

## 2. 架构

### 目录结构
- `backend/`: Python 后端服务。
  - `acquisition/`: 新闻（RSS, Web, 微信）和船舶数据采集模块。
  - `analysis/`: 集成 LLM 进行内容分析。
  - `reporting/`: 仪表盘服务器 (FastAPI) 和企业微信推送逻辑。
  - `data/`: SQLite 数据库 (`dredge_intel.db`, `ship_tracks.db`) 和资源文件。
  - `static/`: 配置文件 (`sources.json`) 和静态资源。
  - `scheduler.py`: 主调度循环。
  - `main.py`: 采集任务入口。
  - `run_tasks_manually.py`: 手动执行任务的工具。
- `frontend/`: Vue 3 + TypeScript 前端。
  - `src/views/`: 仪表盘页面。
- `tests/`: 测试脚本和调试工具。

### 技术栈
- **前端**: Vue 3, TypeScript, Vite, Pinia, Vue Router, Ant Design Vue 4.x, Less。
- **后端**: Python 3.11+, FastAPI (Dashboard), Uvicorn。
- **数据库**: SQLite。
- **爬虫**: Playwright, Feedparser, Requests。
- **AI/LLM**: SiliconFlow (Qwen2.5-7B) 用于文本, Aliyun (Qwen-VL) 用于视觉。

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
    在项目根目录创建 `.env` 文件，配置 API 密钥（参考 `backend/config.py` 中的必需键）。

### 运行项目
*   **一键启动（推荐）**:
    在项目根目录运行 `run_dev.bat`。这将分别在独立的窗口中启动前端、后端服务器和调度器。

*   **手动执行任务**:
    ```bash
    cd backend
    python run_tasks_manually.py
    # 使用测试源进行测试:
    python run_tasks_manually.py --test
    ```

### 关键配置文件
- `backend/config.py`: 中心配置，加载 `.env`。
- `backend/static/sources.json`: 生产环境新闻源。
- `backend/static/sources_test.json`: 测试环境新闻源。

## 4. AI 助手注意事项
- **语言**: 所有用户交互和注释请使用中文。
- **操作系统**: Windows 环境。
- **路径处理**: 使用 `os.path.join` 或绝对路径。`tests/` 中的 Python 脚本需要调整 `sys.path` 以导入 `backend` 模块。
- **Playwright**: 用于复杂网站（如 DredgeWire）。支持分页（`next_selector`, `max_pages`）。
- **数据库**: `articles` 表在 `url` 字段上有 UNIQUE 约束。
