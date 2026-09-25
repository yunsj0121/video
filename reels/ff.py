"""ffmpeg 호출 헬퍼."""
import re
import subprocess

from .config import ffmpeg_bin


def run(args: list, quiet: bool = True) -> None:
    cmd = [ffmpeg_bin(), "-hide_banner", "-y"] + [str(a) for a in args]
    if quiet:
        cmd[3:3] = ["-loglevel", "error"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{' '.join(cmd)}\n{proc.stderr[-3000:]}")


def duration(path) -> float:
    """ffprobe 없이 `ffmpeg -i` 출력의 Duration 으로 길이(초)를 구한다."""
    proc = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise RuntimeError(f"길이를 읽을 수 없습니다: {path}\n{proc.stderr[-1000:]}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def silence(path, seconds: float) -> None:
    run(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{seconds:.3f}",
         "-c:a", "libmp3lame", "-b:a", "128k", path])


def frame(video, at: float, out_png) -> None:
    run(["-ss", f"{at:.3f}", "-i", video, "-frames:v", "1", out_png])
