"""② 나레이션 — ElevenLabs TTS + 해시 캐싱.

같은 (문장, 보이스, 모델, 속도) 조합이면 API를 다시 부르지 않고 캐시된 mp3를 쓴다.
API 키가 없으면 dry-run: 문장 길이로 추정한 무음 mp3를 만들어 파이프라인만 검증한다.
"""
import hashlib
import json

import requests

from . import ff
from .config import CACHE_DIR, ELEVENLABS_API_KEY, ELEVENLABS_MODEL_ID, ELEVENLABS_VOICE_ID

TTS_CACHE = CACHE_DIR / "tts"
_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def _key(text: str, voice_id: str, model_id: str, speed: float) -> str:
    raw = json.dumps([text.strip(), voice_id, model_id, round(speed, 3)], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _estimate_seconds(text: str) -> float:
    # 한국어 나레이션은 대략 초당 6~7자. dry-run 용 추정치.
    return max(1.2, len(text.replace(" ", "")) / 6.5 + 0.3)


def narrate(text: str, voice_id: str = "", model_id: str = "", speed: float = 1.0) -> tuple:
    """문장을 mp3로 만들고 (경로, 실제 합성 여부)를 돌려준다."""
    voice_id = voice_id or ELEVENLABS_VOICE_ID
    model_id = model_id or ELEVENLABS_MODEL_ID
    TTS_CACHE.mkdir(parents=True, exist_ok=True)

    if not (ELEVENLABS_API_KEY and voice_id):
        out = TTS_CACHE / f"dryrun_{_key(text, 'dry', '', speed)}.mp3"
        if not out.exists():
            ff.silence(out, _estimate_seconds(text) / speed)
        return out, False

    out = TTS_CACHE / f"{_key(text, voice_id, model_id, speed)}.mp3"
    if out.exists():
        return out, True

    resp = requests.post(
        _URL.format(voice_id=voice_id),
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": ELEVENLABS_API_KEY, "accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS 실패 ({resp.status_code}): {resp.text[:500]}")
    tmp = out.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.rename(out)
    return out, True
