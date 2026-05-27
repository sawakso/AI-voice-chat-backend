import os
from dotenv import load_dotenv

load_dotenv()

# ========== LLM 配置 ==========
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")  # deepseek / openai / qwen / glm / ollama

# ========== GPT-SoVite 文件配置 ==========
GPT_WEIGHTS_DIR = os.getenv("GPT_WEIGHTS_DIR", "")
SOVITS_WEIGHTS_DIR = os.getenv("SOVITS_WEIGHTS_DIR", "")
REF_AUDIO_DIR = os.getenv("REF_AUDIO_DIR", "")
GENIE_REF_AUDIO_DIR = os.getenv("GENIE_REF_AUDIO_DIR", "")

# 通用 OpenAI 兼容接口
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# ========== TTS 配置 ==========
TTS_API_URL = os.getenv("TTS_API_URL", "http://127.0.0.1:9880")
GENIE_TTS_API_URL = os.getenv("GENIE_TTS_API_URL", "http://127.0.0.1:8001")
TTS_OUTPUT_DIR = "output"

# ========== 角色设定 ==========
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "你是一个友好的助手，回复简洁自然，不超过100字。")

# ========== QQ Bot 配置 ==========
QQBOT_HTTP_API = os.getenv("QQBOT_HTTP_API", "http://127.0.0.1:3000")
QQBOT_QQ = os.getenv("QQBOT_QQ", "")
QQBOT_GROUP_IDS = os.getenv("QQBOT_GROUP_IDS", "")  # 逗号分隔，如 "123456,789012"
QQBOT_WS_TOKEN = os.getenv("QQBOT_WS_TOKEN", "")
QQBOT_REF_AUDIO = os.getenv("QQBOT_REF_AUDIO", "")
QQBOT_PROMPT_TEXT = os.getenv("QQBOT_PROMPT_TEXT", "")
QQBOT_PROMPT_LANG = os.getenv("QQBOT_PROMPT_LANG", "zh")