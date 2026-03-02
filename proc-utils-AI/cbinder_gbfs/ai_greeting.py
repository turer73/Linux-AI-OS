import subprocess
import os
import time
from datetime import datetime

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

TMP_AUDIO_PATH = "/tmp/ai-greeting.wav"

def get_greeting():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "Hello, good morning."
    elif 12 <= hour < 18:
        return "Hello, good afternoon."
    else:
        return "Hello tonight. The night is here."

def init_robot_voice():
    if pyttsx3 is None:
        raise ImportError("pyttsx3 required: pip install pyttsx3")
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.85)

    voices = engine.getProperty('voices')
    for voice in voices:
        if "robot" in voice.name.lower() or "klatt" in voice.id.lower():
            engine.setProperty('voice', voice.id)
            break
    else:
        if len(voices) >= 2:
            engine.setProperty('voice', voices[1].id)
    return engine

def generate_temp_audio(text, path):
    engine = init_robot_voice()
    engine.save_to_file(text, path)
    engine.runAndWait()

def play_temp_audio(path):
    """Play audio file using platform-appropriate player (no shell injection)."""
    if not os.path.isfile(path):
        print(f"Ses dosyasi bulunamadi: {path}")
        return
    if os.name == "posix":
        result = subprocess.run(
            ["aplay", path], capture_output=True, timeout=10, check=False
        )
        if result.returncode != 0:
            subprocess.run(
                ["paplay", path], capture_output=True, timeout=10, check=False
            )
    elif os.name == "nt":
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             f'(New-Object Media.SoundPlayer "{path}").PlaySync()'],
            capture_output=True, timeout=10, check=False
        )
    else:
        print("Ses calma yontemi tanimlanmadi.")

def main():
    greeting = get_greeting()
    print(f"[GREETING] ➤ {greeting}")
    generate_temp_audio(greeting, TMP_AUDIO_PATH)
    play_temp_audio(TMP_AUDIO_PATH)
    time.sleep(2)
    if os.path.exists(TMP_AUDIO_PATH):
        os.remove(TMP_AUDIO_PATH)

if __name__ == "__main__":
    main()
