from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from core.llm_client import get_ai_reply
from core.tts_client import text_to_speech
import os
import glob
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 配置 ==========
TTS_BACKEND = "http://127.0.0.1:9880"
TTS_PROJECT_DIR = "D:/Adobe/GPT-SoVTIS-V2/GPT-So-V2-Batch"

GPT_WEIGHTS_DIRS = [
    f"{TTS_PROJECT_DIR}/GPT_weights_v2",
    f"{TTS_PROJECT_DIR}/GPT_weights",
]
SOVITS_WEIGHTS_DIRS = [
    f"{TTS_PROJECT_DIR}/SoVITS_weights_v2",
    f"{TTS_PROJECT_DIR}/SoVITS_weights",
]
REF_AUDIO_DIR = "D:/Adobe/GPT-SoVTIS-V2/推理"


# ========== 请求模型 ==========

class ChatRequest(BaseModel):
    message: str
    ref_audio_path: str
    prompt_text: str
    prompt_lang: str = "zh"
    text_lang: str = "zh"

class VoiceConfig(BaseModel):
    ref_audio_path: str
    prompt_text: str
    prompt_lang: str = "zh"
    text_lang: str = "zh"

class SwitchModelRequest(BaseModel):
    gpt_model: str = ""
    sovits_model: str = ""


# ========== 工具函数 ==========

def scan_files(dirs, extensions):
    """扫描目录下的模型文件，返回文件名列表"""
    files = []
    for d in dirs:
        if os.path.exists(d):
            for ext in extensions:
                for f in glob.glob(f"{d}/*{ext}"):
                    name = os.path.basename(f)
                    if name not in files:
                        files.append(name)
    return files

def scan_ref_audios(base_dir):
    """递归扫描参考音频"""
    files = []
    if os.path.exists(base_dir):
        for f in glob.glob(f"{base_dir}/**/*.wav", recursive=True):
            # 返回完整路径，前端直接用
            files.append(f.replace("\\", "/"))
    return files


# ========== API ==========

@app.get("/api/models")
async def get_models():
    """获取可用模型列表和参考音频列表"""
    gpt_models = scan_files(GPT_WEIGHTS_DIRS, [".ckpt", ".pth"])
    sovits_models = scan_files(SOVITS_WEIGHTS_DIRS, [".ckpt", ".pth"])
    ref_audios = scan_ref_audios(REF_AUDIO_DIR)

    return {
        "gpt_models": sorted(gpt_models),
        "sovits_models": sorted(sovits_models),
        "ref_audios": sorted(ref_audios)
    }


@app.post("/api/model/switch")
async def switch_model(req: SwitchModelRequest):
    """切换模型"""
    results = []

    if req.gpt_model:
        gpt_path = f"{TTS_PROJECT_DIR}/GPT_weights_v2/{req.gpt_model}"
        if not os.path.exists(gpt_path):
            gpt_path = f"{TTS_PROJECT_DIR}/GPT_weights/{req.gpt_model}"
        r = requests.get(f"{TTS_BACKEND}/set_gpt_weights", params={"weights_path": gpt_path})
        results.append(f"GPT: {r.text}")

    if req.sovits_model:
        sovits_path = f"{TTS_PROJECT_DIR}/SoVITS_weights_v2/{req.sovits_model}"
        if not os.path.exists(sovits_path):
            sovits_path = f"{TTS_PROJECT_DIR}/SoVITS_weights/{req.sovits_model}"
        r = requests.get(f"{TTS_BACKEND}/set_sovits_weights", params={"weights_path": sovits_path})
        results.append(f"SoVITS: {r.text}")

    return {"success": True, "results": results}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """对话"""
    try:
        reply_text = get_ai_reply(req.message)
        audio_path = text_to_speech(
            text=reply_text,
            ref_audio_path=req.ref_audio_path,
            prompt_text=req.prompt_text,
            prompt_lang=req.prompt_lang,
            text_lang=req.text_lang,
            filename=f"reply_{abs(hash(reply_text))}.wav"
        )
        return {"reply": reply_text, "audio_file": os.path.basename(audio_path)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"reply": f"错误: {str(e)}", "audio_file": ""}


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    """获取音频文件"""
    filepath = os.path.join("output", filename)
    if not os.path.exists(filepath):
        return FileResponse(os.path.join("output", "test.wav"), media_type="audio/wav")
    return FileResponse(filepath, media_type="audio/wav")


@app.post("/api/voice/test")
async def test_voice(req: VoiceConfig):
    """测试音色"""
    try:
        audio_path = text_to_speech(
            text="你好，这是音色测试",
            ref_audio_path=req.ref_audio_path,
            prompt_text=req.prompt_text,
            prompt_lang=req.prompt_lang,
            text_lang=req.text_lang,
            filename="test.wav"
        )
        return {"audio_file": "test.wav"}
    except Exception as e:
        return {"audio_file": "", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()

    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)