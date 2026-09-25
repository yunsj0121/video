"""④ BGM — ElevenLabs Music API 로 무드별 곡을 한 번 만들어 assets/bgm 에 쌓아두고 재사용."""
import requests

from .config import ASSETS_DIR, ELEVENLABS_API_KEY

_URL = "https://api.elevenlabs.io/v1/music"

PRESETS = {
    "tech": "Modern minimal tech background music, clean electronic beat, uplifting, "
            "no vocals, loopable instrumental for a short social media reel",
    "calm": "Calm minimal ambient background music, soft piano and pads, relaxed, "
            "no vocals, loopable instrumental for a short social media reel",
    "bright": "Bright cheerful upbeat background music, playful ukulele and claps, happy, "
              "no vocals, loopable instrumental for a short social media reel",
}


def generate(mood: str, prompt: str = "", seconds: int = 20) -> str:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError(".env 에 ELEVENLABS_API_KEY 가 필요합니다.")
    prompt = prompt or PRESETS[mood]
    out = ASSETS_DIR / "bgm" / f"{mood}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.post(
        _URL,
        headers={"xi-api-key": ELEVENLABS_API_KEY},
        json={"prompt": prompt, "music_length_ms": seconds * 1000},
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs Music 실패 ({resp.status_code}): {resp.text[:500]}")
    out.write_bytes(resp.content)
    return str(out)
