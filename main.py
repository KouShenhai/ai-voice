import json
import os
import re
import sys
import uuid
import wave
from collections import deque

import pyaudio
from pathlib import Path
import winsound
from vosk import KaldiRecognizer, Model

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 4000
VOSK_MODEL_DIR = Path("models/vosk-model-small-cn-0.22")
TEMP_VOICE_PATH = "temp/temp_" + f"{uuid.uuid4().hex}.wav"
LAST_AUDIO_TEXT = ""
BUFFER_SECONDS = 5  # 环形缓冲 5 秒

def mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def load_vosk_model() -> Model:
    if not VOSK_MODEL_DIR.exists():
        print(
            f"未找到 Vosk 中文模型目录: {VOSK_MODEL_DIR}\n"
            "请先下载模型并解压到该目录，例如 vosk-model-small-cn-0.22",
            file=sys.stderr,
        )
        raise FileNotFoundError(str(VOSK_MODEL_DIR))
    return Model(str(VOSK_MODEL_DIR))

def open_audio_stream(p: pyaudio.PyAudio):
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        return stream
    except OSError as exc:
        print(f"无法打开麦克风设备: {exc}", file=sys.stderr)
        raise

def play_audio(path):
    winsound.PlaySound(path, winsound.SND_FILENAME)

def admin_wake_up():
    play_audio(os.path.join("voice", "init.wav"))

def delete_file():
    if VOSK_MODEL_DIR.exists():
        os.remove(TEMP_VOICE_PATH)

def is_wakeup(text):
    return "你好世界" == text

def get_audio_text(data : bytes, recognizer : KaldiRecognizer):
    global LAST_AUDIO_TEXT
    if recognizer.AcceptWaveform(data):
        result = json.loads(recognizer.Result())
        text = result.get("text", "").strip()
        if text and text != LAST_AUDIO_TEXT:
            print(f"识别结果【text】: {text}")
            LAST_AUDIO_TEXT  =""
            # 去掉特殊符
            return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text)
        else:
            return ""
    else:
        partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
        if partial and partial != LAST_AUDIO_TEXT:
            print(f"实时识别【partial】: {partial}", end="\r", flush=True)
            LAST_AUDIO_TEXT = partial
            return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", partial)
        else:
            return ""

if __name__ == '__main__':
    # 创建文件夹
    mkdir("temp")
    pa = pyaudio.PyAudio()
    stream = open_audio_stream(pa)
    max_chunks = int(SAMPLE_RATE / CHUNK_SIZE * BUFFER_SECONDS)
    buffer = deque(maxlen=max_chunks)
    try:
        # 加载语音模型【VOSK】
        model = load_vosk_model()
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            # 缓存数据
            buffer.append(data)
            audio_text = get_audio_text(data, recognizer)
            if is_wakeup(audio_text):
                wf = wave.open(TEMP_VOICE_PATH, "wb")
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(pa.get_sample_size(FORMAT))
                wf.setframerate(SAMPLE_RATE)
                for frame in buffer:
                    wf.writeframes(frame)
                wf.close()
                admin_wake_up()

    except FileNotFoundError:
        raise SystemExit(1)
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        buffer.clear()
