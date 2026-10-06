"""Google Flow/Veo용 이미지→영상 요청 패키지와 공식 Gemini API 제출.

Flow 웹앱은 공개 API를 제공하지 않는다. 이 모듈은 같은 Google 영상 모델인
Veo를 공식 Gemini API로 호출하고, 웹 Flow에 수동 업로드할 때도 그대로 쓸 수
있는 프롬프트·나레이션·SRT 파일을 함께 만든다.
"""
import json
import os
import time
from pathlib import Path

from .config import OUTPUT_DIR, ROOT

ALLOWED_GENERATION_SECONDS = (4, 6, 8)
DEFAULT_MODEL = "veo-3.1-generate-preview"


def _resolve(base: Path, value: str) -> Path:
    for candidate in (base / value, ROOT / value, Path(value)):
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(value)


def _timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _captions(cfg: dict, narration: str) -> list:
    captions = cfg.get("captions") or []
    if not captions:
        return [{"start": 0.0, "end": float(cfg["target_seconds"]), "text": narration}]
    if all(isinstance(item, str) for item in captions):
        step = float(cfg["target_seconds"]) / len(captions)
        return [
            {"start": round(i * step, 3), "end": round((i + 1) * step, 3), "text": text}
            for i, text in enumerate(captions)
        ]
    return captions


def _srt(items: list) -> str:
    blocks = []
    for i, item in enumerate(items, 1):
        blocks.append(
            f"{i}\n{_timestamp(float(item['start']))} --> {_timestamp(float(item['end']))}\n"
            f"{item['text'].strip()}\n"
        )
    return "\n".join(blocks)


def prepare(manifest_path: str) -> dict:
    """manifest를 검증하고 Flow/Veo 요청 파일, 대본, SRT를 만든다."""
    manifest = Path(manifest_path).resolve()
    base = manifest.parent
    cfg = json.loads(manifest.read_text(encoding="utf-8"))

    for key in ("image", "prompt", "narration"):
        if not str(cfg.get(key, "")).strip():
            raise ValueError(f"flow.json에 {key!r} 값이 필요합니다.")

    name = cfg.get("name") or base.name
    target_seconds = int(cfg.get("target_seconds", 10))
    generation_seconds = int(cfg.get("generation_seconds", min(target_seconds, 8)))
    if generation_seconds not in ALLOWED_GENERATION_SECONDS:
        raise ValueError("generation_seconds는 4, 6, 8 중 하나여야 합니다.")
    aspect_ratio = cfg.get("aspect_ratio", "9:16")
    if aspect_ratio not in ("9:16", "16:9"):
        raise ValueError("aspect_ratio는 '9:16' 또는 '16:9'여야 합니다.")

    image = _resolve(base, cfg["image"])
    narration = cfg["narration"].strip()
    caption_items = _captions({**cfg, "target_seconds": target_seconds}, narration)
    out_dir = OUTPUT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    request = {
        "name": name,
        "provider": "google-gemini-api-veo",
        "flow_web_compatible": True,
        "model": cfg.get("model") or os.getenv("GOOGLE_VIDEO_MODEL") or DEFAULT_MODEL,
        "image": str(image),
        "prompt": cfg["prompt"].strip(),
        "aspect_ratio": aspect_ratio,
        "resolution": cfg.get("resolution", "720p"),
        "generation_seconds": generation_seconds,
        "target_seconds": target_seconds,
        "output": str((out_dir / f"{name}_flow_source.mp4").resolve()),
    }
    request_path = out_dir / "flow_request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "flow_prompt.txt").write_text(request["prompt"] + "\n", encoding="utf-8")
    (out_dir / "narration.txt").write_text(narration + "\n", encoding="utf-8")
    (out_dir / "captions.srt").write_text(_srt(caption_items), encoding="utf-8")
    return request


def submit(manifest_path: str, dry_run: bool = False, poll_seconds: int = 10) -> str:
    """요청 패키지를 만든 뒤 Veo 이미지→영상 생성 작업을 제출한다."""
    request = prepare(manifest_path)
    request_file = OUTPUT_DIR / request["name"] / "flow_request.json"
    if dry_run:
        print(f"요청 준비 완료(dry-run): {request_file}")
        return str(request_file)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(".env에 GEMINI_API_KEY가 필요합니다. 실제 요청 전 --dry-run으로 검증할 수 있습니다.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Google 영상 생성을 쓰려면 `pip install google-genai` 하세요.") from exc

    image_path = Path(request["image"])
    image = types.Image.from_file(location=str(image_path))
    source = types.GenerateVideosSource(prompt=request["prompt"], image=image)
    config = types.GenerateVideosConfig(
        aspect_ratio=request["aspect_ratio"],
        resolution=request["resolution"],
        duration_seconds=request["generation_seconds"],
        number_of_videos=1,
    )
    client = genai.Client(api_key=api_key)
    operation = client.models.generate_videos(
        model=request["model"], source=source, config=config
    )
    print(f"Veo 요청 접수: {getattr(operation, 'name', 'operation')}")
    while not operation.done:
        time.sleep(poll_seconds)
        operation = client.operations.get(operation)
        print("  생성 중…")

    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError(f"Veo 생성 결과가 없습니다: {operation}")
    destination = Path(request["output"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    video = operation.response.generated_videos[0].video
    client.files.download(file=video, destination=str(destination))
    print(f"Flow/Veo 원본 완성: {destination}")
    if request["target_seconds"] != request["generation_seconds"]:
        print(
            f"  생성 원본은 {request['generation_seconds']}초입니다. "
            f"CapCut에서 목표 {request['target_seconds']}초에 맞추세요."
        )
    return str(destination)
