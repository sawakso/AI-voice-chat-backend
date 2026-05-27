from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.llm_client import get_ai_reply
from core.tts_client import text_to_speech
from qq_bot.handler import handle_async, set_allowed_groups
from qq_bot.sender import send_group_msg, send_group_voice, send_private_msg
from config.settings import QQBOT_WS_TOKEN, QQBOT_GROUP_IDS, QQBOT_REF_AUDIO, QQBOT_PROMPT_TEXT
import os
import glob
import requests
import threading
import time
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 配置（从环境变量读取） ==========
from config.settings import GPT_WEIGHTS_DIR, SOVITS_WEIGHTS_DIR, REF_AUDIO_DIR, GENIE_REF_AUDIO_DIR, GENIE_TTS_API_URL

# QQ Bot 群号白名单
if QQBOT_GROUP_IDS.strip():
    set_allowed_groups({int(x.strip()) for x in QQBOT_GROUP_IDS.split(",") if x.strip()})

TTS_BACKEND = os.getenv("TTS_API_URL", "http://127.0.0.1:9880")

def get_tts_url(engine: str) -> str:
    """根据引擎选择 TTS 后端地址"""
    if engine == "genie":
        return GENIE_TTS_API_URL
    return TTS_BACKEND

def check_genie_available() -> bool:
    """检测 GENIE 服务是否可用"""
    try:
        r = requests.get(f"{GENIE_TTS_API_URL}/set_gpt_weights", params={"weights_path": "__ping__"}, timeout=2)
        return True
    except Exception:
        return False


def get_genie_characters() -> list:
    """从 GENIE 服务获取可用角色列表"""
    try:
        r = requests.get(f"{GENIE_TTS_API_URL}/characters", timeout=3)
        if r.status_code == 200:
            data = r.json()
            return data.get("characters", [])
    except Exception:
        pass
    return []

GPT_WEIGHTS_DIRS = [d.strip() for d in GPT_WEIGHTS_DIR.split(",") if d.strip()] if GPT_WEIGHTS_DIR else []
SOVITS_WEIGHTS_DIRS = [d.strip() for d in SOVITS_WEIGHTS_DIR.split(",") if d.strip()] if SOVITS_WEIGHTS_DIR else []


# ========== 音频文件自动清理 ==========
def cleanup_old_audio_files():
    """定期清理 output 目录中超过 1 小时的音频文件"""
    output_dir = "output"

    # 确保目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        return

    while True:
        try:
            now = time.time()
            deleted_count = 0

            for filename in os.listdir(output_dir):
                filepath = os.path.join(output_dir, filename)
                if os.path.isfile(filepath) and filename.endswith('.wav'):
                    # 删除超过 1 小时的文件
                    if now - os.path.getmtime(filepath) > 3600:
                        os.remove(filepath)
                        deleted_count += 1
                        print(f"🧹 已清理: {filename}")

            if deleted_count > 0:
                print(f"✅ 共清理 {deleted_count} 个过期音频文件")

            # 每小时检查一次
            time.sleep(3600)

        except Exception as e:
            print(f"清理失败: {e}")
            time.sleep(3600)


def start_cleanup_thread():
    """启动清理线程"""
    thread = threading.Thread(target=cleanup_old_audio_files, daemon=True)
    thread.start()
    print("✅ 音频文件自动清理已启动（保留1小时）")


# ========== 确保 output 目录存在并挂载静态文件 ==========
os.makedirs("output", exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")

# ========== 启动清理线程 ==========
start_cleanup_thread()
# ========== 请求模型 ==========

class TTSAdvancedParams(BaseModel):
    top_k: int = 15
    top_p: float = 1
    temperature: float = 1
    repetition_penalty: float = 1.35
    speed_factor: float = 1.0
    sample_steps: int = 32
    fragment_interval: float = 0.3
    seed: int = -1
    parallel_infer: bool = True
    split_bucket: bool = True
    super_sampling: bool = False

class ChatRequest(BaseModel):
    message: str
    engine: str = "gpt-sovits"
    ref_audio_path: str
    aux_ref_audio_paths: list[str] = []
    prompt_text: str
    prompt_lang: str = "zh"
    text_lang: str = "zh"
    tts_params: TTSAdvancedParams = TTSAdvancedParams()

class VoiceConfig(BaseModel):
    engine: str = "gpt-sovits"
    ref_audio_path: str
    aux_ref_audio_paths: list[str] = []
    prompt_text: str
    prompt_lang: str = "zh"
    text_lang: str = "zh"
    tts_params: TTSAdvancedParams = TTSAdvancedParams()

class SwitchModelRequest(BaseModel):
    engine: str = "gpt-sovits"
    gpt_model: str = ""
    sovits_model: str = ""
    genie_character: str = ""


# ========== 工具函数 ==========

def scan_files(dirs, extensions):
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
    """扫描参考音频，优先读 *.list 文件"""
    characters = []
    if not os.path.exists(base_dir):
        return characters

    # 1. 扫描所有 .list 文件
    list_files = glob.glob(f"{base_dir}/*.list")
    if list_files:
        for list_file in sorted(list_files):
            char_name = os.path.splitext(os.path.basename(list_file))[0]
            files = []
            with open(list_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 4:
                        path, _, lang, prompt_text = parts[0], parts[1], parts[2], parts[3]
                        files.append({
                            "name": os.path.basename(path),
                            "path": path.replace("\\", "/"),
                            "lang": lang,
                            "prompt_text": prompt_text
                        })
            if files:
                characters.append({"character": char_name, "files": files})
        return characters

    # 2. 兜底：按文件夹递归扫描
    for char_name in sorted(os.listdir(base_dir)):
        char_dir = os.path.join(base_dir, char_name)
        if not os.path.isdir(char_dir):
            continue
        files = []
        for root, _, filenames in os.walk(char_dir):
            for fn in sorted(filenames):
                if fn.lower().endswith(('.wav', '.mp3')):
                    full_path = os.path.join(root, fn).replace("\\", "/")
                    file_info = {"name": fn, "path": full_path}
                    txt_path = full_path.rsplit('.', 1)[0] + '.txt'
                    if os.path.exists(txt_path):
                        with open(txt_path, "r", encoding="utf-8") as tf:
                            file_info["prompt_text"] = tf.read().strip()
                    files.append(file_info)
        if files:
            characters.append({"character": char_name, "files": files})
    return characters

def find_model_path(dirs, filename):
    for d in dirs:
        path = f"{d}/{filename}"
        if os.path.exists(path):
            return path
    return ""


# ========== API ==========

@app.get("/api/models")
async def get_models():
    engines = [{"id": "gpt-sovits", "name": "GPT-SoVITS (原版)", "available": True}]
    if check_genie_available():
        engines.append({"id": "genie", "name": "GENIE (ONNX 加速)", "available": True})
    else:
        engines.append({"id": "genie", "name": "GENIE (ONNX 加速)", "available": False})

    return {
        "gpt_models": sorted(scan_files(GPT_WEIGHTS_DIRS, [".ckpt", ".pth"])),
        "sovits_models": sorted(scan_files(SOVITS_WEIGHTS_DIRS, [".ckpt", ".pth"])),
        "ref_audios": scan_ref_audios(REF_AUDIO_DIR) if REF_AUDIO_DIR else [],
        "genie_ref_audios": scan_ref_audios(GENIE_REF_AUDIO_DIR) if GENIE_REF_AUDIO_DIR else [],
        "engines": engines,
        "genie_characters": get_genie_characters() if check_genie_available() else [],
    }


@app.post("/api/model/switch")
async def switch_model(req: SwitchModelRequest):
    tts_url = get_tts_url(req.engine)
    results = []

    if req.engine == "genie" and req.genie_character:
        r = requests.get(f"{tts_url}/switch_character", params={"name": req.genie_character})
        results.append(f"GENIE: {r.json().get('message', 'OK')}")
        return {"success": True, "results": results}

    if req.gpt_model:
        gpt_path = find_model_path(GPT_WEIGHTS_DIRS, req.gpt_model)
        if gpt_path:
            r = requests.get(f"{tts_url}/set_gpt_weights", params={"weights_path": gpt_path})
            results.append(f"GPT: {r.text}")
        else:
            results.append("GPT: 找不到模型文件")
    if req.sovits_model:
        sovits_path = find_model_path(SOVITS_WEIGHTS_DIRS, req.sovits_model)
        if sovits_path:
            r = requests.get(f"{tts_url}/set_sovits_weights", params={"weights_path": sovits_path})
            results.append(f"SoVITS: {r.text}")
        else:
            results.append("SoVITS: 找不到模型文件")
    return {"success": True, "results": results}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    tts_url = get_tts_url(req.engine)
    try:
        reply_text = get_ai_reply(req.message)
        audio_path = text_to_speech(
            text=reply_text,
            ref_audio_path=req.ref_audio_path,
            aux_ref_audio_paths=req.aux_ref_audio_paths,
            prompt_text=req.prompt_text,
            prompt_lang=req.prompt_lang,
            text_lang=req.text_lang,
            filename=f"reply_{abs(hash(reply_text))}.wav",
            tts_params=req.tts_params.model_dump(),
            tts_api_url=tts_url,
        )
        return {"reply": reply_text, "audio_file": os.path.basename(audio_path)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"reply": f"错误: {str(e)}", "audio_file": ""}


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    filepath = os.path.join("output", filename)
    if not os.path.exists(filepath):
        filepath = os.path.join("output", "test.wav")
    return FileResponse(filepath, media_type="audio/wav")


@app.get("/api/ref-audio-preview")
async def preview_ref_audio(path: str):
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, media_type="audio/wav")


@app.post("/api/voice/test")
async def test_voice(req: VoiceConfig):
    tts_url = get_tts_url(req.engine)
    try:
        audio_path = text_to_speech(
            text="你好，这是音色测试",
            ref_audio_path=req.ref_audio_path,
            aux_ref_audio_paths=req.aux_ref_audio_paths,
            prompt_text=req.prompt_text,
            prompt_lang=req.prompt_lang,
            text_lang=req.text_lang,
            filename="test.wav",
            tts_params=req.tts_params.model_dump(),
            tts_api_url=tts_url,
        )
        return {"audio_file": "test.wav"}
    except Exception as e:
        return {"audio_file": "", "error": str(e)}


# ========== QQ Bot WebSocket ==========

@app.websocket("/ws/qq")
async def qq_websocket(ws: WebSocket):
    """接收 NapCatQQ 反向 WebSocket 连接，处理群消息事件"""
    await ws.accept()

    # 鉴权（OneBot 在 HTTP header 里传 access_token）
    token = ws.headers.get("authorization", "").replace("Bearer ", "")
    if QQBOT_WS_TOKEN and token != QQBOT_WS_TOKEN:
        await ws.close(code=4001, reason="invalid token")
        return

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # 处理消息事件
            if data.get("post_type") != "message":
                continue
            msg_type = data.get("message_type")
            if msg_type not in ("group", "private"):
                continue

            result = await handle_async(data)
            if result is None:
                continue

            if msg_type == "private":
                send_private_msg(result["user_id"], result["reply"])
                continue

            # 发送文本回复
            send_group_msg(result["group_id"], result["reply"], result["reply_to"])

            # 如果需要发语音
            if result.get("want_voice"):
                from core.tts_client import text_to_speech
                if QQBOT_REF_AUDIO and QQBOT_PROMPT_TEXT:
                    try:
                        wav = text_to_speech(
                            text=result["reply"],
                            ref_audio_path=QQBOT_REF_AUDIO,
                            prompt_text=QQBOT_PROMPT_TEXT,
                            filename=f"qq_voice_{abs(hash(result['reply']))}.wav",
                        )
                        send_group_voice(result["group_id"], wav)
                    except Exception:
                        pass  # 语音失败就算了，文字已经发了
                else:
                    send_group_msg(result["group_id"], "（没配参考音频，发不了语音，去 .env 填一下 QQBOT_REF_AUDIO 和 QQBOT_PROMPT_TEXT）")

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)