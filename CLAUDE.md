# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start the FastAPI backend server
启动LLM对话服务.bat

# Or manually:
.venv\Scripts\python backend_api.py

# Install dependencies
.venv\Scripts\pip install -r requirements.txt
```

## Architecture

This is a FastAPI backend that powers an AI voice chat system. The pipeline is: **user text → LLM generates reply → TTS engine converts to speech → WAV file returned to frontend**.

### Entry points

- **`backend_api.py`** — FastAPI server (default port 8000). Serves a Vue frontend and exposes REST APIs for chat, model switching, and voice testing. The frontend is expected to be a separate Vue app that calls these APIs.
- **`main.py`** — Standalone CLI demo that runs the same pipeline (LLM → TTS → play audio) in a terminal loop. Useful for quick testing without the frontend.

### Core modules

- **`core/llm_client.py`** — Wraps any OpenAI-compatible API (DeepSeek, OpenAI, Qwen, GLM, Ollama). Configured entirely via `.env` variables.
- **`core/tts_client.py`** — Sends text to a GPT-SoVITS or GENIE TTS server via HTTP POST `/tts`, saves the returned WAV binary to `output/`.
- **`core/audio_player.py`** — Plays WAV files using pygame. Has both blocking (`play_audio`) and async/threaded (`play_audio_async`) variants. Only used by `main.py`; the web frontend handles playback client-side.
- **`config/settings.py`** — Loads all configuration from `.env` via `python-dotenv`. Imported by other modules.

### API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/models` | List available TTS engines, GPT/SoVITS model files, reference audio characters |
| `POST /api/model/switch` | Switch TTS model weights on the GPT-SoVITS server |
| `POST /api/chat` | Main endpoint: takes user message + voice config, returns LLM reply text + generated audio filename |
| `POST /api/voice/test` | Generate a test audio clip ("你好，这是音色测试") for previewing voice settings |
| `GET /api/audio/{filename}` | Serve generated WAV files from `output/` |
| `GET /api/ref-audio-preview` | Serve reference audio files for preview |
| `WS /ws/qq` | NapCatQQ reverse WebSocket — receives OneBot v11 events, returns replies via HTTP API |

### TTS engines

Two TTS backends are supported, selected per-request via the `engine` field:
- **`gpt-sovits`** — The original GPT-SoVITS v2 server (default port 9880). Model weights are switched via `/set_gpt_weights` and `/set_sovits_weights`.
- **`genie`** — An ONNX-accelerated variant (default port 8001). Character-based switching via `/switch_character`.

### Configuration (.env)

All settings come from environment variables. Copy `env.example` to `.env` and fill in:

- `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` — LLM backend selection
- `TTS_API_URL` — GPT-SoVITS server (default `http://127.0.0.1:9880`)
- `GENIE_TTS_API_URL` — GENIE server (default `http://127.0.0.1:8001`)
- `GPT_WEIGHTS_DIR` / `SOVITS_WEIGHTS_DIR` — comma-separated directories for model weight scanning
- `REF_AUDIO_DIR` / `GENIE_REF_AUDIO_DIR` — reference audio directories (supports `.list` files for character grouping)
- `BACKEND_PORT` — FastAPI listen port (default 8000)
- `SYSTEM_PROMPT` — LLM system prompt for personality

### Data flow

```
Vue Frontend → POST /api/chat {message, ref_audio_path, prompt_text, ...}
  → core/llm_client.get_ai_reply(message) → LLM text response
  → core/tts_client.text_to_speech(reply_text, ...) → POST to TTS server → WAV saved to output/
  → Response: {reply: "...", audio_file: "reply_xxxx.wav"}
Vue Frontend → GET /api/audio/{filename} → plays audio
```

### QQ Bot (NapCatQQ)

QQ群聊接入通过 NapCatQQ + OneBot v11 反向 WebSocket 实现。

```
QQ群消息 → NapCatQQ (QQNT插件) → WS 反向连接 → /ws/qq → qq_bot/
                                                              ├── handler.py  插话决策 + LLM 回复
                                                              ├── context.py  群聊记忆 (滑动窗口 + 摘要压缩)
                                                              └── sender.py   OneBot HTTP API (发消息/语音)
```

**插话决策**（优先级从高到低）：
1. @机器人 → 一定回复
2. 机器人 3-8 条内有发言 → 继续参与对话
3. 距上次检查超过 20 条 + 机器人沉默 > 8 条 → LLM 判断（低 token 调用）
4. 其余 → 不回复

**群聊记忆**：每个群维护 50 条滑动窗口，超过时把旧消息压缩成摘要追加（不丢大意但省 token）。

**NapCatQQ 部署**：在你的 Windows 电脑安装 QQNT + NapCatQQ 插件，配置反向 WebSocket 到 `ws://127.0.0.1:8000/ws/qq`，无需服务器。

相关 .env 配置：
- `QQBOT_QQ` — 机器人 QQ 号
- `QQBOT_GROUP_IDS` — 允许的群号（逗号分隔）
- `QQBOT_WS_TOKEN` — WebSocket 鉴权 token
- `QQBOT_REF_AUDIO` / `QQBOT_PROMPT_TEXT` — 语音回复用的参考音频

### Output directory

Generated WAV files go to `output/`. A background daemon thread cleans up files older than 1 hour.
