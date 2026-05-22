import pygame

def play_audio(filepath: str):
    """播放 WAV 音频文件，阻塞直到播放结束"""
    pygame.mixer.init()
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)


def play_audio_async(filepath: str):
    """播放 WAV 音频文件，不阻塞（后台播放）"""
    import threading
    t = threading.Thread(target=play_audio, args=(filepath,), daemon=True)
    t.start()