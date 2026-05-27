"""QQ 群消息处理 — 插话决策 + LLM 回复生成"""

import asyncio
from core.llm_client import client as llm_client, LLM_MODEL
from config.settings import SYSTEM_PROMPT, QQBOT_QQ
from .context import context_manager

# 触发语音回复的关键词
VOICE_TRIGGERS = ["发语音", "说句话", "说句话听听", "语音回复", "用语音", "发段语音", "说段语音"]

_ALLOWED_GROUPS: set = set()


def set_allowed_groups(ids: set[int] | None):
    global _ALLOWED_GROUPS
    _ALLOWED_GROUPS = ids or set()


def _allowed(group_id: int) -> bool:
    return not _ALLOWED_GROUPS or group_id in _ALLOWED_GROUPS


def _is_at_bot(segments: list) -> bool:
    for seg in segments:
        if seg.get("type") == "at":
            if str(seg.get("data", {}).get("qq", "")) == str(QQBOT_QQ):
                return True
    return False


def _extract_text(segments: list) -> str:
    parts = []
    for seg in segments:
        if seg.get("type") == "text":
            parts.append(seg.get("data", {}).get("text", ""))
    return "".join(parts)


def _wants_voice(text: str) -> bool:
    return any(kw in text for kw in VOICE_TRIGGERS)


def _should_interject(group_id: int, segments: list) -> tuple:
    ctx = context_manager.get(group_id)
    if _is_at_bot(segments):
        return True, "at"
    dist = ctx.bot_recent_distance()
    if 3 < dist <= 8:
        return True, "continue"
    need_check = dist < 0 or dist > 8
    since_check = len(ctx.messages) - ctx.last_llm_check_idx
    if need_check and since_check >= 20:
        ctx.last_llm_check_idx = len(ctx.messages)
        return _llm_interject(ctx)
    return False, "skip"


def _llm_interject(ctx) -> tuple:
    dialogue = ctx.get_dialogue_text(20)
    summary = ctx.summary or "无"
    prompt = (
        f"群聊背景：{summary}\n\n最近对话：\n{dialogue}\n\n"
        "你是普通群友。这个话题你有话要说吗？只回答「插话」或「不插话」。"
    )
    try:
        resp = llm_client.chat.completions.create(
            model=LLM_MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=5
        )
        ans = resp.choices[0].message.content.strip()
        return ("插话" in ans), "llm_check"
    except Exception:
        return False, "llm_error"


def _build_system(ctx) -> str:
    dialogue = ctx.get_dialogue_text(25)
    summary = ctx.summary or "无"
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "当前在QQ群聊。你可以发送语音消息，不要说你不能发语音。\n"
        "群聊历史摘要：\n" + summary + "\n\n"
        "近期对话：\n" + dialogue + "\n\n"
        "回复要求：随和点，像跟老朋友随口聊天。不用每条都回，想说就说，不想说就嗯一声。别端着，但也别刻意敷衍。"
    )


def handle_group_message(data: dict) -> dict | None:
    group_id = data.get("group_id", 0)
    user_id = data.get("user_id", 0)
    msg_id = data.get("message_id", 0)
    segments = data.get("message", [])
    sender = data.get("sender", {})

    if not _allowed(group_id):
        return None

    nickname = sender.get("card") or sender.get("nickname", str(user_id))
    text = _extract_text(segments)

    if str(user_id) == str(QQBOT_QQ):
        context_manager.add(group_id, user_id, nickname, text, is_bot=True)
        return None

    context_manager.add(group_id, user_id, nickname, text)

    ok, reason = _should_interject(group_id, segments)
    if not ok:
        return None

    ctx = context_manager.get(group_id)
    system = _build_system(ctx)
    user_msg = f"{nickname}说：{text}"
    if reason == "at":
        user_msg = f"{nickname} @了你，说：{text}"

    try:
        resp = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        reply = f"（脑子短路了: {e}）"

    context_manager.add(group_id, int(QQBOT_QQ), "我", reply, is_bot=True)

    return {
        "group_id": group_id,
        "reply": reply,
        "reply_to": msg_id,
        "want_voice": _wants_voice(text),
    }


async def handle_async(data: dict) -> dict | None:
    if data.get("message_type") == "private":
        return await asyncio.to_thread(handle_private_message, data)
    return await asyncio.to_thread(handle_group_message, data)


def handle_private_message(data: dict) -> dict | None:
    user_id = data.get("user_id", 0)
    segments = data.get("message", [])
    text = _extract_text(segments)

    if str(user_id) == str(QQBOT_QQ):
        return None

    if not text.strip():
        return None

    system = f"{SYSTEM_PROMPT}\n你可以发语音消息。回复简短口语，20-50字。"

    try:
        resp = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=0.8,
            max_tokens=200,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        reply = f"（脑子短路了: {e}）"

    return {
        "user_id": user_id,
        "reply": reply,
        "need_voice": _wants_voice(text),
    }