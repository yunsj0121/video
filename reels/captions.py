"""자막·타이틀 카드를 Pillow 로 1080x1920 투명 PNG 에 직접 그린다.

스타일 값은 전부 script.json 의 "style" 에서 덮어쓸 수 있다 — 프롬프트로 레이아웃을 "깎아나갈" 때
바뀌는 게 이 숫자들이다 (y 위치, 크기, 패딩, 알파, 자간, 행간, 그림자 …).
텍스트 안의 *단어* 는 강조색 + Bold 로 그린다.
"""
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import HEIGHT, WIDTH, font_path

CAPTION_DEFAULTS = {
    "y": 0.68,             # 자막 블록 중심의 세로 위치 (화면 높이 대비 비율)
    "size": 66,            # 폰트 크기(px)
    "weight": "bold",      # 본문 웨이트: bold | regular  (강조 *단어* 는 항상 bold)
    "max_width": 0.84,     # 한 줄 최대 폭 (화면 폭 대비)
    "align": "center",     # left | center | right
    "mode": "box",         # box: 반투명 배경 박스 / free: 드롭섀도만
    "color": "#FFFFFF",
    "emph_color": "#FFE14D",
    "box_color": "#000000",
    "box_alpha": 170,      # 0=완전투명, 255=불투명
    "padding": 28,
    "radius": 22,
    "line_spacing": 1.28,  # 행간 (폰트 크기 배수)
    "tracking": 0,         # 자간(px), 음수면 좁게
    "stroke": 0,           # 외곽선 두께(px)
    "stroke_color": "#000000",
    "shadow_alpha": 150,   # 드롭섀도 진하기 (0이면 없음)
    "shadow_blur": 6,
    "shadow_offset": 4,
    "safe_top": 0.10,      # 위쪽 세이프존 (상태바·계정명 영역)
    "safe_bottom": 0.20,   # 아래쪽 세이프존 (캡션·좋아요 버튼 영역)
}

TITLE_DEFAULTS = dict(CAPTION_DEFAULTS, y=0.17, size=84, mode="free", max_width=0.86,
                      shadow_alpha=190, shadow_blur=10, fade_in=0.4, duration=None)


@lru_cache(maxsize=32)
def _font(weight: str, size: int):
    return ImageFont.truetype(font_path(weight), size)


def _rgba(hex_color: str, alpha: int = 255):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _tokens(text: str):
    """'*나레이션*이 붙어요' -> [[('나레이션', True), ('이', False)], [('붙어요', False)]]
    단어(공백 단위)는 강조/일반 조각(run)들의 리스트 — 조사가 강조 단어에 붙어 있어도 띄우지 않는다."""
    words, cur, emph = [], [], False
    for piece in re.split(r"(\*|\s+)", text):
        if piece == "*":
            emph = not emph
        elif piece.isspace():
            if cur:
                words.append(cur); cur = []
        elif piece:
            cur.append((piece, emph))
    if cur:
        words.append(cur)
    return words


def _run_width(txt, emph, st):
    f = _font("bold" if emph else st["weight"], st["size"])
    return sum(f.getlength(c) for c in txt) + st["tracking"] * len(txt)


def _word_width(runs, st):
    return sum(_run_width(t, e, st) for t, e in runs) - st["tracking"]


def _wrap(text, st):
    max_w = WIDTH * st["max_width"] - 2 * st["padding"]
    space = _font(st["weight"], st["size"]).getlength(" ") + st["tracking"]
    lines, cur, cur_w = [], [], 0.0
    for runs in _tokens(text):
        w = _word_width(runs, st)
        if w > max_w:  # 한 단어가 한 줄보다 길면 글자 단위로 쪼갠다
            for t, e in runs:
                for ch in t:
                    cw = _word_width([(ch, e)], st)
                    if cur and cur_w + cw > max_w:
                        lines.append(cur); cur, cur_w = [], 0.0
                    cur.append(([(ch, e)], cw)); cur_w += cw
            continue
        add = w + (space if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append(cur); cur, cur_w, add = [], 0.0, w
        cur.append((runs, w)); cur_w += add
    if cur:
        lines.append(cur)
    return lines, space


def render_text(text: str, style: dict, out_path) -> str:
    st = dict(CAPTION_DEFAULTS, **(style or {}))
    lines, space = _wrap(text, st)
    line_h = int(st["size"] * st["line_spacing"])
    widths = [sum(w for _, w in ln) + space * (len(ln) - 1) for ln in lines]
    block_w = max(widths) if widths else 0
    block_h = line_h * len(lines)

    pad = st["padding"]
    top = int(HEIGHT * st["y"] - block_h / 2)
    top = max(int(HEIGHT * st["safe_top"]) + pad, min(top, int(HEIGHT * (1 - st["safe_bottom"])) - block_h - pad))

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    text_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    def line_x(w):
        if st["align"] == "left":
            return (WIDTH - block_w) / 2
        if st["align"] == "right":
            return (WIDTH + block_w) / 2 - w
        return (WIDTH - w) / 2

    for i, (ln, w) in enumerate(zip(lines, widths)):
        x, y = line_x(w), top + i * line_h + (line_h - st["size"]) / 2
        for runs, ww in ln:
            cx = x
            for txt, emph in runs:
                f = _font("bold" if emph else st["weight"], st["size"])
                fill = _rgba(st["emph_color"] if emph else st["color"])
                for ch in txt:
                    draw.text((cx, y), ch, font=f, fill=fill, stroke_width=st["stroke"],
                              stroke_fill=_rgba(st["stroke_color"]))
                    cx += f.getlength(ch) + st["tracking"]
            x += ww + space

    if st["mode"] == "box" and lines:
        box = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        bx0, by0 = (WIDTH - block_w) / 2 - pad, top - pad
        ImageDraw.Draw(box).rounded_rectangle(
            [bx0, by0, bx0 + block_w + 2 * pad, by0 + block_h + 2 * pad],
            radius=st["radius"], fill=_rgba(st["box_color"], st["box_alpha"]))
        img = Image.alpha_composite(img, box)

    if st["shadow_alpha"] > 0:
        alpha = text_layer.getchannel("A").point(lambda a: a * st["shadow_alpha"] // 255)
        off = st["shadow_offset"]
        shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        shadow.paste((0, 0, 0, 255), (off, off, WIDTH, HEIGHT), mask=alpha.crop((0, 0, WIDTH - off, HEIGHT - off)))
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(st["shadow_blur"])))

    img = Image.alpha_composite(img, text_layer)
    img.save(out_path)
    return str(out_path)
