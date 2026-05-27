"""QQ Bot 主入口 — WebSocket 收发 + TTS 语音 + 角色切换 + 群隔离 + 异常处理"""

import asyncio
import json
import os
import re
import traceback
import websockets
import requests
from config.settings import (
    QQBOT_QQ, TTS_API_URL, TTS_OUTPUT_DIR,
    GPT_WEIGHTS_DIR, SOVITS_WEIGHTS_DIR,
)

NAPCAT_WS = "ws://127.0.0.1:3001"

# ========== 语音配置 ==========
VOICES_FILE = os.path.join(os.path.dirname(__file__), "voices.json")
with open(VOICES_FILE, "r", encoding="utf-8-sig") as f:
    VOICES = json.load(f)

DEFAULT_VOICE = os.getenv("QQBOT_DEFAULT_VOICE", "小特")

# 每个群的当前语音（群隔离），私聊用 None
group_voice: dict[int, str] = {}

VOICE_TRIGGERS = ["发语音", "说句话", "说句话听听", "语音回复", "用语音", "发段语音", "说段语音"]


# ========== 工具函数 ==========
def get_voice_name(group_id: int | None) -> str:
    if group_id is None:
        return group_voice.get(0, DEFAULT_VOICE)
    return group_voice.get(group_id, DEFAULT_VOICE)


def extract_text(payload: dict) -> str:
    parts = []
    for seg in payload.get("message", []):
        if seg.get("type") == "text":
            parts.append(seg.get("data", {}).get("text", ""))
    return "".join(parts)


def safe_reply(msg: str) -> str:
    """统一异常包装，永远不报错"""
    try:
        return msg
    except Exception:
        return "出了一点小问题，稍后再试~"


# ========== 命令处理 ==========
def handle_command(text: str, group_id: int | None = None) -> str | None:
    text = text.strip()

    # ---- 语音列表 ----
    if text in ("语音列表", "角色列表", "有哪些语音"):
        return "可用语音：" + "、".join(VOICES.keys())

    # ---- 切换语音 ----
    if text in ("切换语音", "切换角色", "切换"):
        v = get_voice_name(group_id)
        return f"当前语音：【{v}】。请加上角色名，比如：切换语音 丁真"

    m = re.match(r"切换(语音|角色)?\s*[，,、。.\s]*\s*(.+)", text)
    if m:
        name = m.group(2).strip().lstrip("，,、。. !！")
        # 模糊匹配：找名字包含输入的角色
        match = None
        if name in VOICES:
            match = name
        else:
            for k in VOICES:
                if name in k:
                    match = k
                    break
        if match:
            if group_id:
                group_voice[group_id] = match
            else:
                group_voice[0] = match
            return f"已切换语音为【{match}】"
        else:
            return f"没找到「{name}」这个语音。发送「语音列表」查看可用的哦~"

    # ---- 当前语音 ----
    if text in ("当前语音", "当前角色", "什么语音"):
        v = get_voice_name(group_id)
        return f"当前语音：【{v}】"

    # ---- 帮助 ----
    if text in ("帮助", "命令", "功能", "菜单"):
        return (
            "可用命令：\n"
            "  语音列表 — 查看可用语音\n"
            "  切换语音 <名字> — 切换 TTS 音色\n"
            "  当前语音 — 查看当前音色\n"
            "  发语音 — 用语音回复\n"
            "  帮助 — 显示此菜单"
        )

    return None

# ========== TTS ==========
def generate_voice(text: str, group_id: int | None = None, filename: str = "reply.wav") -> str | None:
    voice_name = get_voice_name(group_id)
    cfg = VOICES.get(voice_name, VOICES[DEFAULT_VOICE])
    lang = cfg.get("prompt_lang", "zh")

    # 日语角色：先翻译
    if lang == "ja":
        try:
            from core.llm_client import client as llm_client, LLM_MODEL
            resp = llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": f"把这句话翻译成日语，只输出翻译结果，不要解释：\n{text}"}],
                max_tokens=200,
                temperature=0.3,
            )
            translated = resp.choices[0].message.content.strip()
            print(f"[TTS] 翻译: {text[:50]}... -> {translated[:50]}...")
            text = translated
        except Exception as e:
            print(f"[TTS] 翻译失败，用原文: {e}")

    # 去掉括号内的动作描写，不转语音
    import re
    text = re.sub(r'[（(][^）)]*[）)]', '', text)
    text = text.strip()

    try:
        params = {
            "text": text,
            "text_lang": lang,
            "ref_audio_path": cfg["ref_audio"],
            "prompt_text": cfg["prompt_text"],
            "prompt_lang": lang,
            "media_type": "wav",
            "streaming_mode": False,
            "gpt_weights_path": os.path.join(GPT_WEIGHTS_DIR, cfg["gpt_weight"]),
            "sovits_weights_path": os.path.join(SOVITS_WEIGHTS_DIR, cfg["sovits_weight"]),
            "sample_steps": 16,
        }
        resp = requests.post(f"{TTS_API_URL}/tts", json=params, timeout=60)
        if resp.status_code != 200:
            print(f"[TTS] 失败: {resp.text[:200]}")
            return None
        os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(TTS_OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"[TTS] 生成语音 ({voice_name}, {lang}): {filepath}")
        return filepath
    except Exception as e:
        print(f"[TTS] 异常: {e}")
        return None


# ========== 事件处理 ==========
async def handle_event(ws, payload: dict):
    try:
        post_type = payload.get("post_type", "")
        message_type = payload.get("message_type", "")
        user_id = payload.get("user_id", 0)
        group_id = payload.get("group_id") if message_type == "group" else None

        if post_type == "meta_event":
            return

        text = extract_text(payload)

        if str(user_id) == str(QQBOT_QQ):
            return

        # 命令优先
        cmd_reply = handle_command(text, group_id)
        if cmd_reply:
            if message_type == "group" and group_id:
                await send_group_msg_ws(ws, group_id, safe_reply(cmd_reply))
            else:
                await send_private_msg_ws(ws, user_id, safe_reply(cmd_reply))
            return

        # LLM 回复
        if message_type == "group" and group_id:
            from .handler import handle_group_message
            result = handle_group_message(payload)
            if result:
                await send_group_msg_ws(ws, group_id, safe_reply(result["reply"]), result.get("reply_to"))
                if result.get("want_voice") or any(kw in text for kw in VOICE_TRIGGERS):
                    wav = await asyncio.to_thread(generate_voice, result["reply"], group_id)
                    if wav:
                        await send_group_voice_ws(ws, group_id, wav)

        elif message_type == "private":
            from .handler import handle_private_message
            result = handle_private_message(payload)
            if result:
                await send_private_msg_ws(ws, user_id, safe_reply(result["reply"]))
                if result.get("need_voice"):
                    wav = await asyncio.to_thread(generate_voice, result["reply"])
                    if wav:
                        await send_private_voice_ws(ws, user_id, wav)

    except Exception:
        print(f"[QQ Bot] 处理消息异常:\n{traceback.format_exc()}")
        # 不崩溃，静默处理


# ========== WebSocket 发送 ==========
async def send_group_msg_ws(ws, group_id: int, text: str, reply_to: int = None):
    message = []
    if reply_to:
        message.append({"type": "reply", "data": {"id": str(reply_to)}})
    message.append({"type": "text", "data": {"text": text}})
    await ws.send(json.dumps({
        "action": "send_group_msg",
        "params": {"group_id": group_id, "message": message},
    }))


async def send_private_msg_ws(ws, user_id: int, text: str):
    await ws.send(json.dumps({
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": [{"type": "text", "data": {"text": text}}],
        },
    }))


async def send_group_voice_ws(ws, group_id: int, wav_path: str):
    filename = os.path.basename(wav_path)
    file_url = f"http://host.docker.internal:8000/output/{filename}"
    await ws.send(json.dumps({
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": [{"type": "record", "data": {"file": file_url}}],
        },
    }))


async def send_private_voice_ws(ws, user_id: int, wav_path: str):
    filename = os.path.basename(wav_path)
    file_url = f"http://host.docker.internal:8000/output/{filename}"
    await ws.send(json.dumps({
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": [{"type": "record", "data": {"file": file_url}}],
        },
    }))


# ========== 主入口 ==========
async def main():
    print(f"[QQ Bot] 连接 {NAPCAT_WS} ...")
    async with websockets.connect(NAPCAT_WS) as ws:
        print(f"[QQ Bot] 已连接，默认语音: {DEFAULT_VOICE}")
        print("[QQ Bot] 等待消息...")
        async for raw in ws:
            try:
                payload = json.loads(raw)
                if payload.get("post_type"):
                    asyncio.create_task(handle_event(ws, payload))
            except json.JSONDecodeError:
                pass
            except Exception:
                print(f"[QQ Bot] 主循环异常:\n{traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())