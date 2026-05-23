import requests
import os
import json
from config.settings import TTS_API_URL, TTS_OUTPUT_DIR

os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

def text_to_speech(
    text: str,
    ref_audio_path: str,
    prompt_text: str,
    aux_ref_audio_paths: list = None,
    prompt_lang: str = "zh",
    text_lang: str = "zh",
    filename: str = "reply.wav",
    tts_params: dict = None
) -> str:
    params = {
        "text": text,
        "text_lang": text_lang,
        "ref_audio_path": ref_audio_path,
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang,
        "media_type": "wav",
        "streaming_mode": False,
    }

    if aux_ref_audio_paths:
        aux = [p for p in aux_ref_audio_paths if p]
        if aux:
            params["aux_ref_audio_paths"] = aux

    # 合并 TTS 参数
    if tts_params:
        for key in ["top_k", "top_p", "temperature", "repetition_penalty",
                     "speed_factor", "sample_steps", "fragment_interval",
                     "seed", "parallel_infer", "split_bucket", "super_sampling"]:
            if key in tts_params:
                params[key] = tts_params[key]

    print("=" * 40)
    print("TTS 请求参数:")
    print(json.dumps(params, indent=2, ensure_ascii=False))
    print("=" * 40)

    resp = requests.post(f"{TTS_API_URL}/tts", json=params, timeout=180)

    if resp.status_code != 200:
        raise Exception(f"TTS 失败: {resp.text}")

    filepath = os.path.join(TTS_OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)

    return filepath