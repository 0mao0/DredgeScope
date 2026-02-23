import os
from dotenv import load_dotenv

# Load .env from project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'))

# API Keys
# SiliconFlow (Text Model)
TEXT_LLM_API_KEY = os.getenv("TEXT_LLM_API_KEY") 
TEXT_LLM_API_BASE = os.getenv("TEXT_LLM_API_BASE", "https://api.siliconflow.cn/v1")
TEXT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

# BIM-ACE (VL Model)
VL_LLM_API_KEY = os.getenv("AI_API_KEY") 
# Remove /chat/completions suffix if present, as AsyncOpenAI appends it
base = os.getenv("AI_API_URL", "https://ai.bim-ace.com/chat/v1")
if base.endswith("/chat/completions"):
    base = base.replace("/chat/completions", "")
VL_LLM_API_BASE = base
VL_MODEL = os.getenv("AI_MODEL", "Qwen3-VL-30B-A3B-Instruct-FP8")

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SOURCES_FILE = os.path.join(os.path.dirname(__file__), 'acquisition', 'sources.json')
TEMPLATES_DIR = os.path.join(ROOT_DIR, 'frontend')
REPORT_FILE = os.path.join(DATA_DIR, 'report.md')
HISTORY_FILE = os.path.join(DATA_DIR, 'history.jsonl')
ASSETS_DIR = os.path.join(DATA_DIR, 'assets')

# Ensure assets directory exists
os.makedirs(ASSETS_DIR, exist_ok=True)

# Webhook & Server
WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL")
BACKEND_URL = os.getenv("WISEFLOW_BACKEND_URL", "http://127.0.0.1:8000")

# Fleet API (船舶追踪)
FLEET_API_URL = os.getenv("FLEET_API_URL", "http://101.200.125.6:8234/fleets/group/shipposition?usertoken=H2UbIXn52rXHndFrfxWm6i9xthSBK5b4C%2BDcmOwmUbEVu%2FLdfN5ZwQR%2BIP4N%2FxTI&group=group1")
