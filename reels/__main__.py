"""사용법:
  python -m reels render projects/<이름>/script.json   # 영상 합성
  python -m reels bgm tech                              # BGM 생성 (tech | calm | bright | 직접 --prompt)
  python -m reels demo                                  # 테스트용 클립을 만들어 데모 렌더
"""
import argparse

from . import bgm, ff, render
from .config import ROOT


def make_demo_assets():
    clips = ROOT / "projects" / "demo" / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    specs = {"a.mp4": "testsrc2=size=1920x1080:rate=30", "b.mp4": "mandelbrot=size=1280x720:rate=30",
             "c.mp4": "smptehdbars=size=1920x1080:rate=30"}
    for name, src in specs.items():
        if not (clips / name).exists():
            ff.run(["-f", "lavfi", "-i", src, "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", clips / name])
    sfx = ROOT / "projects" / "demo" / "pop.wav"
    if not sfx.exists():
        ff.run(["-f", "lavfi", "-i", "sine=frequency=880:duration=0.12", sfx])
    tone = ROOT / "projects" / "demo" / "bgm_tone.mp3"
    if not tone.exists():
        ff.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=8", "-c:a", "libmp3lame", tone])


def main():
    ap = argparse.ArgumentParser(prog="reels")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("script"); r.add_argument("-o", "--output", default="")
    r.add_argument("--no-preview", action="store_true")
    b = sub.add_parser("bgm"); b.add_argument("mood"); b.add_argument("--prompt", default="")
    b.add_argument("--seconds", type=int, default=20)
    sub.add_parser("demo")
    a = ap.parse_args()

    if a.cmd == "render":
        render.render(a.script, a.output, previews=not a.no_preview)
    elif a.cmd == "bgm":
        print(bgm.generate(a.mood, a.prompt, a.seconds))
    elif a.cmd == "demo":
        make_demo_assets()
        render.render(ROOT / "projects" / "demo" / "script.json")


if __name__ == "__main__":
    main()
