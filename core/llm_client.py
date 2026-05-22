## LLM对话服务
from openai import OpenAI
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, SYSTEM_PROMPT

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

def get_ai_reply(user_text: str) -> str:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7,
        max_tokens=200
    )
    return response.choices[0].message.content.strip()