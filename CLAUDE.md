# DredgeScope 项目导航

> 本文档为项目结构导航，帮助快速定位功能模块与配置文件。

## 1. 项目概览

DredgeScope 是面向疏浚和海洋基础设施行业的情报系统，实现：
- **多源采集**：RSS + Web + 微信公众号
- **AI 分析**：LLM 分类、翻译、摘要
- **可视化**：Dashboard + 船舶地图
- **自动推送**：企业微信早报/晚报

## 2. 目录结构

```
dredgescope/
├── backend/                 # Python 后端
│   ├── acquisition/         # 采集模块
│   │   ├── sources/         # 采集源实现
│   │   │   ├── base.py      # RSS/Web 基类
│   │   │   ├── rss/         # RSS 源
│   │   │   ├── web/         # Web 源
│   │   │   └── wechat/      # 微信公众号 (WeWe RSS)
│   │   └── source_manager.py # 采集管理器
│   ├── analysis/            # 分析模块
│   │   ├── info_analysis.py # LLM 分析入口
│   │   └── ships_status.py  # 船舶数据处理
│   ├── reporting/           # 报告与推送
│   │   ├── dashboard_server.py # FastAPI 服务
│   │   ├── wecom_push.py    # 企业微信推送
│   │   └── report_generation.py
│   ├── static/              # 静态配置
│   │   ├── sources.json     # 采集源配置
│   │   └── constants.py     # 常量定义
│   ├── data/                # 数据存储
│   ├── config.py            # 全局配置
│   ├── database.py          # 数据库模型
│   ├── main.py              # 采集入口
│   └── scheduler.py         # 任务调度
├── frontend/                # Vue 3 前端
│   └── src/
│       ├── views/           # 页面
│       ├── components/      # 组件
│       └── stores/          # Pinia 状态
├── docker-compose.yml       # Docker 编排 (含 WeWe RSS)
└── .env                     # 环境变量
```

## 3. 快速定位

| 任务 | 文件 | 说明 |
|------|------|------|
| 添加采集源 | `backend/static/sources.json` | RSS/Web/WeChat 配置 |
| 修改 API 密钥 | `.env` 或 `backend/config.py` | 环境变量 |
| 修改数据库表 | `backend/database.py` | SQLite 模型 |
| 修改采集逻辑 | `backend/acquisition/sources/base.py` | RSS/Web 基类 |
| 修改微信采集 | `backend/acquisition/sources/wechat/` | WeWe RSS 集成 |
| 修改 LLM 分析 | `backend/analysis/info_analysis.py` | Prompt 模板 |
| 修改 API 接口 | `backend/reporting/dashboard_server.py` | FastAPI 路由 |
| 修改推送逻辑 | `backend/reporting/wecom_push.py` | 企业微信 |
| 修改前端页面 | `frontend/src/views/` | Dashboard/Map 等 |

## 4. 配置说明

### 采集源配置 (`sources.json`)

```json
// RSS 源
{
    "name": "Dredging Today",
    "url": "https://dredgingtoday.com/feed/",
    "type": "rss"
}

// Web 源
{
    "name": "Van Oord News",
    "url": "https://www.vanoord.com/en/updates/",
    "type": "web",
    "selector": "article, .news-item",
    "url_patterns": ["/updates/", "/news/"],
    "blacklist": ["/user/", "/login"],
    "max_links": 15
}

// 微信公众号 (需 WeWe RSS)
{
    "name": "中交疏浚",
    "type": "wechat",
    "wechat": {
        "feed_id": "MP_WXS_xxxxx"
    }
}
```

### 环境变量 (`.env`)

| 变量 | 说明 |
|------|------|
| `Public_ALIYUN_API_KEY` | 阿里云 API (Qwen) |
| `TEXT_LLM_API_KEY` | SiliconFlow API |
| `WECOM_WEBHOOK_URL` | 企业微信 Webhook |
| `FLEET_API_URL` | 船舶追踪 API |
| `WEWE_RSS_URL` | WeWe RSS 服务地址 |
| `WEWE_RSS_AUTH_CODE` | WeWe RSS 授权码 |

## 5. 常用命令

```bash
# 本地开发
run_dev.bat

# Docker 部署
docker-compose up -d

# 手动采集
cd backend && python run_tasks_manually.py

# 测试模式
cd backend && python run_tasks_manually.py --test

# 代码检查
ruff check backend/
pnpm run lint --prefix frontend/
```

## 6. 数据库表

| 表名 | 说明 |
|------|------|
| `articles` | 新闻文章 |
| `source_health` | 采集源健康状态 |
| `ships` | 船舶信息 |
| `ship_tracks` | 船舶轨迹 |

## 7. 微信公众号采集

基于 [WeWe RSS](https://github.com/cooderl/wewe-rss) 实现：
1. 访问 WeWe RSS 管理后台
2. 微信读书扫码登录
3. 添加公众号（提交文章链接）
4. 获取 `feed_id` 配置到 `sources.json`

## 8. 相关文档

- [AGENTS.md](./AGENTS.md) - AI Agent 代码规范
- [README.md](./README.md) - 项目完整说明
