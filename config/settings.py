import os
from dotenv import load_dotenv

load_dotenv()

# ========== LLM 配置 ==========
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")  # deepseek / openai / qwen / glm / ollama

# 通用 OpenAI 兼容接口
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# ========== TTS 配置 ==========
TTS_API_URL = os.getenv("TTS_API_URL", "http://127.0.0.1:9880")
TTS_OUTPUT_DIR = "output"

# ========== 角色设定 ==========
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "你是一个友好的助手，回复简洁自然，不超过100字。")