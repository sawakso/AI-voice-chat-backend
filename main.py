import os
from core.llm_client import get_ai_reply
from core.tts_client import text_to_speech
from core.audio_player import play_audio

# ========== 配置你的参考音频 ==========
REF_AUDIO_PATH = "D:/Adobe/GPT-SoVTIS-V2/推理/丁真/我最近一直在努力学习.wav"
PROMPT_TEXT = "我最近一直在努力学习"
PROMPT_LANG = "zh"
TEXT_LANG = "zh"
# =====================================

def main():
    print("=" * 50)
    print("  AI 语音对话系统")
    print("  输入 'q' 退出")
    print("=" * 50)
    print()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_input.lower() == 'q':
            print("再见！")
            break
        if not user_input:
            continue

        # 1. 调 AI 大模型，获取回复文字
        print("思考中...", end=" ", flush=True)
        try:
            reply_text = get_ai_reply(user_input)
            print(f"\nAI: {reply_text}")
        except Exception as e:
            print(f"\n[错误] AI 调用失败: {e}")
            continue

        # 2. 文字 → 语音
        print("生成语音中...", end=" ", flush=True)
        try:
            audio_path = text_to_speech(
                text=reply_text,
                ref_audio_path=REF_AUDIO_PATH,
                prompt_text=PROMPT_TEXT,
                prompt_lang=PROMPT_LANG,
                text_lang=TEXT_LANG,
                filename="reply.wav"
            )
            print("完成")
        except Exception as e:
            print(f"\n[错误] TTS 失败: {e}")
            continue

        # 3. 播放语音
        print("播放中...", flush=True)
        play_audio(audio_path)
        print()

if __name__ == "__main__":
    main()