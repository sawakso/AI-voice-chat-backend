```markdown
# QQ AI 语音机器人 — 启动指南

## 一、启动顺序

1. Docker Desktop
2. NapCat（QQ机器人框架）
3. GPT-SoVITS（TTS 语音生成）
4. AI-Voice-Chat 后端（可选，如果只用 QQ Bot 可跳过）
5. QQ Bot 主程序

---

## 二、详细步骤

### 1. 启动 Docker Desktop

双击桌面 Docker Desktop 图标，等待左下角显示 `Engine running`。

### 2. 启动 NapCat

```powershell
docker start napcat
```

验证：
```powershell
docker ps | findstr napcat
```

浏览器打开 WebUI 确认小号在线（如未自动登录需扫码）：
```
http://localhost:6099/webui?token=808cb6c40419
```

> 如果 Token 变了，用 `docker logs napcat | findstr "Token"` 查看。

### 3. 启动 GPT-SoVITS

双击 `D:\Adobe\GPT-SoVTIS-V2\GPT-So-V2-Batch\启动后端.bat`

验证：浏览器打开 `http://127.0.0.1:9880/docs`

### 4. 启动 AI-Voice-Chat 后端（可选）

双击 `D:\快速访问\软件工程文件\Pycharm文件\AI-Voice-Chat\启动LLM对话服务.bat`

验证：浏览器打开 `http://127.0.0.1:8000/docs`

> 如果只用 QQ Bot，这一步可跳过。QQ Bot 直接调 LLM，不经过此后端。

### 5. 启动 QQ Bot

双击 `D:\快速访问\软件工程文件\Pycharm文件\AI-Voice-Chat\启动QQ机器人.bat`

看到 `[QQ Bot] 已连接，默认语音: 小特` 即启动成功。

---

## 三、核心命令

| 命令              | 作用                         |
| ----------------- | ---------------------------- |
| `语音列表`        | 查看可用语音角色             |
| `切换语音 <名字>` | 切换 TTS 音色                |
| `当前语音`        | 查看当前音色                 |
| `发语音`          | 用语音回复（群聊需 @机器人） |
| `帮助`            | 显示命令菜单                 |

---

## 四、配置修改

### 提示词（人设）
编辑 `.env` 中的 `SYSTEM_PROMPT`，改完重启 QQ Bot 生效。

### 语音角色
编辑 `qq_bot/voices.json`，添加或修改角色的参考音频、提示文本、模型权重。

### 默认语音
编辑 `.env` 中的 `QQBOT_DEFAULT_VOICE`。

---

## 五、停止

- QQ Bot：在窗口按 `Ctrl+C`
- GPT-SoVITS：关闭命令行窗口
- NapCat：`docker stop napcat`（或直接关 Docker Desktop）
- Docker Desktop：右下角右键 → Quit Docker Desktop