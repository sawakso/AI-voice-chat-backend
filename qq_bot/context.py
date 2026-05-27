"""群聊记忆管理 — 滑动窗口 + 摘要压缩"""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Msg:
    user_id: int
    nickname: str
    content: str
    timestamp: float


@dataclass
class GroupContext:
    group_id: int
    messages: deque = field(default_factory=lambda: deque(maxlen=50))
    summary: str = ""
    bot_last_msg_idx: int = -1
    last_llm_check_idx: int = 0

    def add_message(self, user_id, nickname, content, is_bot=False):
        self.messages.append(_Msg(user_id, nickname, content, time.time()))
        if is_bot:
            self.bot_last_msg_idx = len(self.messages) - 1

    def get_recent(self, n=30):
        return list(self.messages)[-n:]

    def get_dialogue_text(self, n=30):
        msgs = self.get_recent(n)
        return "\n".join(f"{m.nickname}: {m.content}" for m in msgs)

    def bot_recent_distance(self):
        """机器人最近发言距离现在的消息数，-1 表示从未发言"""
        if self.bot_last_msg_idx < 0:
            return -1
        return len(self.messages) - self.bot_last_msg_idx


class ContextManager:
    def __init__(self, max_messages=50, compress_every=25, keep_recent=15, max_summary=800):
        self._ctx = {}          # group_id → GroupContext
        self.max_messages = max_messages
        self.compress_every = compress_every
        self.keep_recent = keep_recent
        self.max_summary = max_summary

    def get(self, group_id) -> GroupContext:
        if group_id not in self._ctx:
            self._ctx[group_id] = GroupContext(group_id=group_id)
        return self._ctx[group_id]

    def add(self, group_id, user_id, nickname, content, *, is_bot=False):
        ctx = self.get(group_id)
        ctx.add_message(user_id, nickname, content, is_bot=is_bot)
        if len(ctx.messages) >= self.max_messages:
            self._compress(ctx)

    def _compress(self, ctx):
        """把最早的 compress_every 条消息从窗口移除，追加到 summary"""
        n = min(self.compress_every, len(ctx.messages) - self.keep_recent)
        if n <= 0:
            return
        removed = []
        for _ in range(n):
            removed.append(ctx.messages.popleft())
        lines = []
        if ctx.summary:
            lines.append(ctx.summary)
        lines.append("--- 更早 ---")
        for m in removed:
            lines.append(f"{m.nickname}: {m.content}")
        ctx.summary = "\n".join(lines)
        if len(ctx.summary) > self.max_summary:
            ctx.summary = ctx.summary[-self.max_summary:]
        # 修正索引
        ctx.bot_last_msg_idx = max(-1, ctx.bot_last_msg_idx - n)
        ctx.last_llm_check_idx = max(0, ctx.last_llm_check_idx - n)


context_manager = ContextManager()
