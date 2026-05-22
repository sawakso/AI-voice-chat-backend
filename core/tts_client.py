## TTS文本转语音服务，调用GPT-SoVite　API
import requests
import os
from config.settings import TTS_API_URL, TTS_OUTPUT_DIR

os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

def text_to_speech(
    text: str,
    ref_audio_path: str,
    prompt_text: str,
    prompt_lang: str = "zh",
    text_lang: str = "zh",
    filename: str = "reply.wav"
) -> str:
    """调用 GPT-SoVITS API，文字转语音"""
    params = {
        "text": text,
        "text_lang": text_lang,
        "ref_audio_path": ref_audio_path,
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang,
        "media_type": "wav",
        "streaming_mode": False,
    }

    resp = requests.post(f"{TTS_API_URL}/tts", json=params, timeout=180)

    if resp.status_code != 200:
        raise Exception(f"TTS 失败: {resp.text}")

    filepath = os.path.join(TTS_OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)

    return filepath