"""OneBot v11 HTTP API 封装"""

import subprocess
import os
import requests
from config.settings import QQBOT_HTTP_API


def _call(action: str, params: dict) -> dict:
    r = requests.post(f"{QQBOT_HTTP_API}/{action}", json=params, timeout=10)
    return r.json()


def send_group_msg(group_id: int, text: str, reply_to: int = None) -> dict:
    """发送群文本消息，可选引用回复"""
    chain = []
    if reply_to:
        chain.append({"type": "reply", "data": {"id": str(reply_to)}})
    chain.append({"type": "text", "data": {"text": text}})
    return _call("send_group_msg", {"group_id": group_id, "message": chain})


def send_group_voice(group_id: int, wav_path: str) -> dict:
    """将 WAV 转为 AMR 后发送群语音"""
    amr = wav_path.rsplit(".", 1)[0] + ".amr"
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-ar", "8000", "-ac", "1", amr],
        capture_output=True,
    )
    if not os.path.exists(amr):
        return {"status": "failed", "msg": "AMR 转换失败"}

    chain = [{"type": "record", "data": {"file": f"file:///{amr.replace(os.sep, '/')}"}}]
    return _call("send_group_msg", {"group_id": group_id, "message": chain})


def send_private_msg(user_id: int, text: str) -> dict:
    chain = [{"type": "text", "data": {"text": text}}]
    return _call("send_private_msg", {"user_id": user_id, "message": chain})


def get_group_member_info(group_id: int, user_id: int) -> dict:
    return _call("get_group_member_info", {"group_id": group_id, "user_id": user_id})
