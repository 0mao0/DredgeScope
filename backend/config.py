import os
from dotenv import load_dotenv

# Load .env from project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(ROOT_DIR, '.env')
loaded = load_dotenv(env_path, override=True)
print(f"[Config] Loading .env from {env_path}, Success: {loaded}")

# API Keys
# SiliconFlow (Text Model)
TEXT_LLM_API_KEY = os.getenv("TEXT_LLM_API_KEY") 
TEXT_LLM_API_BASE = os.getenv("TEXT_LLM_API_BASE", "https://api.siliconflow.cn/v1")
TEXT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

# BIM-ACE (VL Model)
# Debug: Print relevant keys
keys = [k for k in os.environ.keys() if "ALIYUN" in k]
print(f"[Config] Found keys with 'ALIYUN': {keys}")

VL_LLM_API_KEY = os.getenv("Public_ALIYUN_API_KEY") 
if VL_LLM_API_KEY:
    print(f"[Config] VL_LLM_API_KEY: {VL_LLM_API_KEY[:5]}...")
else:
    print("[Config] VL_LLM_API_KEY is None!")
VL_LLM_API_BASE = os.getenv("Public_ALIYUN_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
VL_MODEL = os.getenv("Public_ALIYUN_MODEL2", "qwen3.5-397b-a17b")

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
