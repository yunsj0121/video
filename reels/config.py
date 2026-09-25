"""경로, 환경변수, ffmpeg 위치 등 공통 설정."""
import os
import shutil
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv가 없어도 동작
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(ROOT / ".env")

CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"

# 세로 숏폼(릴스/쇼츠) 기본 규격
WIDTH, HEIGHT, FPS = 1080, 1920, 30

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")


def ffmpeg_bin() -> str:
    """PATH의 ffmpeg을 우선 쓰고, 없으면 imageio-ffmpeg 번들 바이너리를 쓴다."""
    exe = os.getenv("FFMPEG_BIN") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise RuntimeError("ffmpeg을 찾을 수 없습니다. ffmpeg을 설치하거나 `pip install imageio-ffmpeg` 하세요.") from e


# 한글 폰트 후보. assets/fonts 에 Pretendard / Noto Sans KR 등을 넣어두면 그걸 우선 사용.
_FONT_CANDIDATES = {
    "bold": [
        "assets/fonts/Pretendard-Bold.otf",
        "assets/fonts/NotoSansKR-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "C:/Windows/Fonts/malgunbd.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
    "regular": [
        "assets/fonts/Pretendard-Regular.otf",
        "assets/fonts/NotoSansKR-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
}


def font_path(weight: str = "bold") -> str:
    env = os.getenv("FONT_BOLD" if weight == "bold" else "FONT_REGULAR")
    for cand in ([env] if env else []) + _FONT_CANDIDATES[weight]:
        p = Path(cand) if Path(cand).is_absolute() else ROOT / cand
        if p.exists():
            return str(p)
    raise RuntimeError("한글 폰트를 찾을 수 없습니다. assets/fonts 에 폰트를 넣거나 FONT_BOLD/FONT_REGULAR 를 지정하세요.")
