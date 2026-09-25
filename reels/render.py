"""⑤ 영상 합성 — script.json 한 장으로 세로 숏폼 mp4 를 만든다.

흐름: 문장별 나레이션 생성 → 나레이션 길이만큼 소스 클립을 잘라 세로(1080x1920)로 크롭
     → 자막/스티커 오버레이 → 장면들을 이어붙임 → 타이틀 카드 + BGM + 효과음 믹싱.

모든 ffmpeg 호출에 -t(출력 길이)를 못박는다. 무한 루프 입력(-loop 1, -stream_loop -1)이
렌더를 끝없이 늘리는 사고를 막기 위해서다.
"""
import json
from pathlib import Path

from PIL import Image

from . import captions, ff, tts
from .config import CACHE_DIR, FPS, HEIGHT, OUTPUT_DIR, ROOT, WIDTH

_VCODEC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
_ACODEC = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
_CROP_Y = {"top": "0", "center": "(ih-oh)/2", "bottom": "ih-oh"}


def _resolve(base: Path, p: str) -> Path:
    for cand in (base / p, ROOT / p, Path(p)):
        if cand.exists():
            return cand.resolve()
    raise FileNotFoundError(p)


def _is_image(p: Path) -> bool:
    return p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")


def _render_scene(i, sc, base, cfg, work):
    text = sc["text"]
    speech, real = tts.narrate(text.replace("*", ""), cfg.get("voice_id", ""), cfg.get("model_id", ""),
                               sc.get("speed", cfg.get("speed", 1.0)))
    dur = round(ff.duration(speech) + sc.get("gap", cfg.get("gap", 0.25)), 3)

    cap_style = dict(cfg.get("style", {}).get("caption", {}), **sc.get("caption", {}))
    cap_png = captions.render_text(sc.get("subtitle", text), cap_style, work / f"cap_{i:02d}.png")

    clip = _resolve(base, sc["clip"])
    anchor = _CROP_Y[sc.get("crop_anchor", cfg.get("crop_anchor", "center"))]
    if _is_image(clip):
        src = ["-loop", "1", "-i", clip]
    else:  # 클립이 문장보다 짧아도 끊기지 않도록 루프, 길이는 -t 로 고정
        src = ["-stream_loop", "-1", "-ss", str(sc.get("start", 0)), "-i", clip]
    inputs = src + ["-loop", "1", "-i", cap_png, "-i", speech]

    fc = [f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={WIDTH}:{HEIGHT}:(iw-ow)/2:{anchor},setsar=1,fps={FPS}[base]"]
    layers = ["[1:v]"]
    st = sc.get("sticker")
    if st:
        sp = _resolve(base, st["path"])
        inputs += (["-ignore_loop", "0"] if sp.suffix.lower() == ".gif" else ["-loop", "1"]) + ["-i", sp]
        fc.append(f"[3:v]scale=iw*{st.get('scale', 1.0)}:-1[stk]")
        stk = ("[stk]", st.get("x", 0.5), st.get("y", 0.45))
        layers = layers + [stk] if st.get("above_caption", True) else [stk] + layers
    cur = "[base]"
    for n, layer in enumerate(layers):
        label, x, y = (layer, 0, 0) if isinstance(layer, str) else layer
        pos = "0:0" if isinstance(layer, str) else f"W*{x}-w/2:H*{y}-h/2"
        fc.append(f"{cur}{label}overlay={pos}:eof_action=repeat[v{n}]")
        cur = f"[v{n}]"
    fc.append("[2:a]aresample=44100,apad[a]")

    out = work / f"scene_{i:02d}.mp4"
    ff.run(inputs + ["-filter_complex", ";".join(fc), "-map", cur, "-map", "[a]",
                     "-t", f"{dur}"] + _VCODEC + _ACODEC + [out])
    return out, dur, real


def _contact_sheet(frames, out_png, cols=4, w=270):
    h = int(w * HEIGHT / WIDTH)
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "black")
    for k, f in enumerate(frames):
        sheet.paste(Image.open(f).convert("RGB").resize((w, h)), ((k % cols) * w, (k // cols) * h))
    sheet.save(out_png)


def render(script_path: str, output: str = "", previews: bool = True) -> str:
    script_path = Path(script_path).resolve()
    base = script_path.parent
    cfg = json.loads(script_path.read_text(encoding="utf-8"))
    name = cfg.get("name", base.name)
    work = CACHE_DIR / "render" / name
    work.mkdir(parents=True, exist_ok=True)
    out = Path(output or cfg.get("output") or OUTPUT_DIR / f"{name}.mp4")
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    segs, starts, t, all_real = [], [], 0.0, True
    for i, sc in enumerate(cfg["scenes"]):
        seg, dur, real = _render_scene(i, sc, base, cfg, work)
        print(f"  장면 {i + 1}/{len(cfg['scenes'])}: {dur:.2f}s  {sc['text'][:30]}")
        segs.append(seg); starts.append(t); t += dur
        all_real &= real
    total = round(t, 3)

    concat_list = work / "concat.txt"
    concat_list.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs))
    body = work / "body.mp4"
    ff.run(["-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", "-t", f"{total}", body])

    # 최종 합성: 타이틀 카드 + BGM + 효과음
    inputs, fc, idx = ["-i", body], [], 1
    vout = "0:v"
    if cfg.get("title"):
        tst = dict(captions.TITLE_DEFAULTS, **cfg.get("style", {}).get("title", {}))
        tpng = captions.render_text(cfg["title"], tst, work / "title.png")
        inputs += ["-loop", "1", "-t", f"{total}", "-i", tpng]
        until = tst["duration"] or total
        fc.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d={tst['fade_in']}:alpha=1[t];"
                  f"[0:v][t]overlay=0:0:enable='lte(t,{until})'[vout]")
        vout, idx = "[vout]", idx + 1

    mix = ["[0:a]"]
    if cfg.get("bgm"):
        inputs += ["-stream_loop", "-1", "-i", _resolve(base, cfg["bgm"])]
        fade = min(1.5, total / 3)
        fc.append(f"[{idx}:a]volume={cfg.get('bgm_volume', 0.12)},"
                  f"afade=t=out:st={total - fade:.3f}:d={fade:.3f}[bgm]")
        mix.append("[bgm]"); idx += 1
    for i, sc in enumerate(cfg["scenes"]):
        if sc.get("sfx"):
            ms = int((starts[i] + sc.get("sfx_offset", 0)) * 1000)
            inputs += ["-i", _resolve(base, sc["sfx"])]
            fc.append(f"[{idx}:a]volume={sc.get('sfx_volume', 0.6)},adelay={ms}|{ms}[sfx{i}]")
            mix.append(f"[sfx{i}]"); idx += 1
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=0.95[aout]")

    ff.run(inputs + ["-filter_complex", ";".join(fc), "-map", vout, "-map", "[aout]",
                     "-t", f"{total}"] + _VCODEC + _ACODEC + ["-movflags", "+faststart", out])
    print(f"완성: {out}  ({total:.2f}s)" + ("" if all_real else "  ※ dry-run: 나레이션은 무음(ElevenLabs 키 없음)"))

    if previews:  # 장면별 중간 프레임을 모은 컨택트 시트 — 레이아웃 확인/수정용
        frames = []
        for i, s in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else total
            f = work / f"preview_{i:02d}.png"
            ff.frame(out, (s + end) / 2, f)
            frames.append(f)
        sheet = out.with_name(out.stem + "_preview.png")
        _contact_sheet(frames, sheet)
        print(f"미리보기: {sheet}")
    return str(out)
