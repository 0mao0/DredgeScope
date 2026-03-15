import os
from dotenv import load_dotenv

# Load .env from project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(ROOT_DIR, '.env')
loaded = load_dotenv(env_path, override=True)
print(f"[Config] Loading .env from {env_path}, Success: {loaded}")

# API Keys
# 阿里云 DashScope (优先使用 Qwen3.5)
# Debug: Print relevant keys
keys = [k for k in os.environ.keys() if "ALIYUN" in k]
print(f"[Config] Found keys with 'ALIYUN': {keys}")

ALIYUN_API_KEY = os.getenv("Public_ALIYUN_API_KEY")
if ALIYUN_API_KEY:
    print(f"[Config] ALIYUN_API_KEY: {ALIYUN_API_KEY[:5]}...")
else:
    print("[Config] ALIYUN_API_KEY is None!")
ALIYUN_API_BASE = os.getenv("Public_ALIYUN_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
ALIYUN_MODEL = os.getenv("Public_ALIYUN_MODEL2", "Qwen3.5-35B-A3B-FP8")

# TEXT LLM 配置（优先阿里云，备选 SiliconFlow）
TEXT_LLM_API_KEY = ALIYUN_API_KEY or os.getenv("TEXT_LLM_API_KEY")
TEXT_LLM_API_BASE = ALIYUN_API_BASE or os.getenv("TEXT_LLM_API_BASE", "https://api.siliconflow.cn/v1")
# 如果使用阿里云，模型为 Qwen3.5；否则使用 SiliconFlow 的模型
TEXT_MODEL = ALIYUN_MODEL if ALIYUN_API_KEY else "Qwen/Qwen2.5-7B-Instruct"

# VL Model 配置（与 TEXT LLM 使用相同配置）
VL_LLM_API_KEY = ALIYUN_API_KEY
VL_LLM_API_BASE = ALIYUN_API_BASE
VL_MODEL = ALIYUN_MODEL

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SOURCES_FILE = os.path.join(os.path.dirname(__file__), 'static', 'sources.json')
TEMPLATES_DIR = os.path.join(ROOT_DIR, 'frontend')
REPORT_FILE = os.path.join(DATA_DIR, 'report.md')
HISTORY_FILE = os.path.join(DATA_DIR, 'history.jsonl')
ASSETS_DIR = os.path.join(DATA_DIR, 'assets')

# Ensure assets directory exists
os.makedirs(ASSETS_DIR, exist_ok=True)

# Webhook & Server
WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL")
BACKEND_URL = os.getenv("WISEFLOW_BACKEND_URL", "http://127.0.0.1:8000")
RSSHUB_BASES = [
    v.strip()
    for v in os.getenv("RSSHUB_BASES", os.getenv("RSSHUB_BASE", "https://rsshub.app")).split(",")
    if v.strip()
]

# Fleet API (船舶追踪)
FLEET_API_URL = os.getenv("FLEET_API_URL")
