import os
from dotenv import load_dotenv

# Calculate path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(ROOT_DIR, '.env')

print(f"Loading from: {env_path}")
print(f"File exists: {os.path.exists(env_path)}")

# Read file content manually
with open(env_path, 'r', encoding='utf-8') as f:
    print(f"First 5 lines: {f.readlines()[:5]}")

# Load
loaded = load_dotenv(env_path, override=True)
print(f"Loaded: {loaded}")

# Check keys
print(f"TEXT_LLM_API_KEY: {os.getenv('TEXT_LLM_API_KEY')}")
print(f"Public_ALIYUN_API_KEY: {os.getenv('Public_ALIYUN_API_KEY')}")

# Check all keys
print("Keys in os.environ:")
for k in os.environ:
    if "ALIYUN" in k or "TEXT" in k:
        print(f"  {k}")
