"""② 나레이션 — TTS + 해시 캐싱.

엔진(provider):
  edge        무료. Microsoft Edge 읽어주기 음성(edge-tts). API 키 불필요. 기본값.
  elevenlabs  유료(무료 티어 있음). .env 의 ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID 사용.
  silent      무음(dry-run). 문장 길이로 추정한 길이만큼 — 네트워크 없이 파이프라인만 검증.

같은 (엔진, 문장, 보이스, 속도) 조합이면 다시 합성하지 않고 캐시된 mp3를 쓴다.
"""
import asyncio
import hashlib
import json
import os

import requests

from . import ff
from .config import CACHE_DIR, ELEVENLABS_API_KEY, ELEVENLABS_MODEL_ID, ELEVENLABS_VOICE_ID

TTS_CACHE = CACHE_DIR / "tts"
EDGE_DEFAULT_VOICE = "ko-KR-SunHiNeural"  # 여성. 남성: ko-KR-InJoonNeural, ko-KR-HyunsuMultilingualNeural
_ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def default_provider() -> str:
    return os.getenv("TTS_PROVIDER") or ("elevenlabs" if ELEVENLABS_API_KEY else "edge")


def _key(*parts) -> str:
    raw = json.dumps(parts, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _estimate_seconds(text: str) -> float:
    # 한국어 나레이션은 대략 초당 6~7자. dry-run 용 추정치.
    return max(1.2, len(text.replace(" ", "")) / 6.5 + 0.3)


def _edge(text, voice, speed, out):
    try:
        import edge_tts
    except ImportError as e:
        raise RuntimeError("무료 음성(edge-tts)을 쓰려면 `pip install edge-tts` 하세요.") from e
    rate = f"{round((speed - 1) * 100):+d}%"  # 1.1 -> "+10%"
    comm = edge_tts.Communicate(text, voice, rate=rate, proxy=os.getenv("HTTPS_PROXY") or None)
    asyncio.run(comm.save(str(out)))


def _elevenlabs(text, voice_id, model_id, speed, out):
    if not (ELEVENLABS_API_KEY and voice_id):
        raise RuntimeError(".env 에 ELEVENLABS_API_KEY 와 ELEVENLABS_VOICE_ID 가 필요합니다.")
    resp = requests.post(
        _ELEVEN_URL.format(voice_id=voice_id),
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
    out.write_bytes(resp.content)


def narrate(text: str, provider: str = "", voice: str = "", speed: float = 1.0) -> tuple:
    """문장을 mp3로 만들고 (경로, 실제 음성 여부)를 돌려준다."""
    provider = provider or default_provider()
    text = text.strip()
    TTS_CACHE.mkdir(parents=True, exist_ok=True)

    if provider == "silent":
        out = TTS_CACHE / f"silent_{_key(text, speed)}.mp3"
        if not out.exists():
            ff.silence(out, _estimate_seconds(text) / speed)
        return out, False

    if provider == "edge":
        voice = voice or os.getenv("EDGE_VOICE") or EDGE_DEFAULT_VOICE
        synth = lambda tmp: _edge(text, voice, speed, tmp)
        key = _key("edge", text, voice, round(speed, 3))
    elif provider == "elevenlabs":
        voice = voice or ELEVENLABS_VOICE_ID
        synth = lambda tmp: _elevenlabs(text, voice, ELEVENLABS_MODEL_ID, speed, tmp)
        # 기존 캐시와 호환되도록 엔진 이름 없이 키를 만든다
        key = _key(text, voice, ELEVENLABS_MODEL_ID, round(speed, 3))
    else:
        raise ValueError(f"알 수 없는 TTS 엔진: {provider} (edge | elevenlabs | silent)")

    out = TTS_CACHE / f"{key}.mp3"
    if not out.exists():
        tmp = out.with_suffix(".part")
        synth(tmp)
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise RuntimeError(f"TTS 결과가 비어 있습니다 ({provider}): {text[:40]}")
        tmp.rename(out)
    return out, True
