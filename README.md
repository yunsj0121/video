# reels — 코드로 만드는 숏폼(릴스/쇼츠) 편집 파이프라인

원본 클립과 대본(`script.json`)을 넣으면 **나레이션 → 세로 크롭 → 자막·스티커 → BGM·효과음 믹싱**까지
FFmpeg + Python(Pillow)으로 렌더링해 1080x1920 MP4를 만듭니다. CapCut 같은 GUI 편집기를 쓰지 않습니다.

```
[원본 클립] → ① 대본(Claude) → ② 나레이션(ElevenLabs, 캐싱) → ③ 스티커(로컬 PNG/GIF)
           → ④ BGM(ElevenLabs Music, 재사용) + 효과음 → ⑤ 합성(FFmpeg + Pillow) → [MP4]
```

## 빠른 시작

```bash
pip install -r requirements.txt        # ffmpeg 이 없으면 imageio-ffmpeg 바이너리를 대신 사용
python -m reels demo                   # 테스트 클립을 만들어 output/demo.mp4 렌더
```

API 키가 없어도 **dry-run**으로 돌아갑니다(나레이션 자리에 문장 길이만큼의 무음). 실제 목소리를 넣으려면:

```bash
cp .env.example .env                   # ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID 입력
python -m reels bgm tech               # (선택) BGM 생성 → assets/bgm/tech.mp3  (tech | calm | bright)
python -m reels render projects/<이름>/script.json
```

렌더가 끝나면 `output/<이름>.mp4`와 장면별 중간 프레임을 모은 `output/<이름>_preview.png`가 생깁니다.

## 새 영상 만들기

1. `projects/<이름>/clips/` 에 원본 클립을 넣습니다.
2. `projects/<이름>/script.json` 을 작성합니다 (Claude에게 "이 클립들로 릴스 대본 짜줘"라고 시켜도 됩니다).
3. `python -m reels render projects/<이름>/script.json`
4. 미리보기를 보고 "자막 조금 위로", "박스 더 투명하게" 식으로 스타일 값을 고쳐 다시 렌더합니다.
   나레이션은 캐시되어 있어 재렌더해도 TTS 요금이 다시 나가지 않습니다.

### script.json

```jsonc
{
  "name": "my-reel",
  "title": "타이틀 카드 *강조*",        // 생략하면 타이틀 없음
  "voice_id": "",                      // 비우면 .env 의 ELEVENLABS_VOICE_ID
  "speed": 1.0,                        // 나레이션 속도
  "gap": 0.25,                         // 문장 뒤 여유(초)
  "crop_anchor": "center",             // 가로→세로 크롭 기준: top | center | bottom
  "bgm": "../../assets/bgm/tech.mp3", "bgm_volume": 0.12,
  "style": { "caption": { ... }, "title": { ... } },
  "scenes": [
    {
      "text": "나레이션 문장. *강조 단어*는 노란색 Bold 자막",
      "subtitle": "(선택) 자막을 나레이션과 다르게 쓸 때",
      "clip": "clips/a.mp4", "start": 2.0,      // 이 지점부터 나레이션 길이만큼 사용
      "crop_anchor": "top",                      // 장면별 덮어쓰기
      "caption": { "mode": "free" },             // 장면별 자막 스타일 덮어쓰기
      "sfx": "../../assets/sfx/pop.mp3", "sfx_volume": 0.6,
      "sticker": { "path": "../../assets/stickers/wow.gif", "x": 0.5, "y": 0.45, "scale": 1.0, "above_caption": true }
    }
  ]
}
```

경로는 script.json 위치 → 저장소 루트 순으로 찾습니다.

### 레이아웃 용어 ↔ 스타일 값

| 말로 하면 | 바뀌는 값 (`style.caption` / `style.title`) |
|---|---|
| 위치 / 앵커 | `y` (블록 중심, 화면 높이 비율) |
| 정렬 | `align`: left / center / right |
| 세이프존 | `safe_top`, `safe_bottom` (자막이 이 영역을 넘지 않도록 자동 보정) |
| 패딩 / 여백 | `padding`, 박스 모서리 `radius` |
| 자간 / 트래킹 | `tracking` (px, 음수면 좁게) |
| 행간 / 줄간격 | `line_spacing` (폰트 크기 배수) |
| 웨이트 | `weight`: bold / regular — `*강조*`는 항상 bold |
| 크기 / 스케일 | `size`, `max_width`, 스티커 `scale` |
| 레이어 순서 | 스티커 `above_caption` |
| 오퍼시티 / 알파 | `box_alpha` (0~255) |
| 드롭섀도 | `shadow_alpha`, `shadow_blur`, `shadow_offset` / 외곽선 `stroke` |
| 박스 대 프리 | `mode`: box / free |
| 페이드인 | 타이틀 `fade_in`(초), 표시 시간 `duration` |
| 크롭 앵커 | `crop_anchor`: top / center / bottom |

## 폰트

기본은 시스템 한글 폰트를 찾습니다. 더 예쁜 결과를 원하면 `assets/fonts/`에
`Pretendard-Bold.otf`, `Pretendard-Regular.otf`(또는 `NotoSansKR-*.ttf`)를 넣으세요.

## 아직 없는 것 (다음 단계)

- ③ KLIPY 스티커 **자동 검색·다운로드** — 지금은 로컬 PNG/GIF 파일을 지정하는 방식
- ⑥ 발행(YouTube Data API / Zernio) — 공개 행위라 사람이 최종 확인 후 올리는 흐름으로 추가 예정

## 주의

- `.env`(API 키), OAuth 토큰 파일은 절대 커밋하지 마세요 — `.gitignore`에 포함되어 있습니다.
- 모든 ffmpeg 호출은 출력 길이(`-t`)를 명시합니다. 루프 입력 때문에 렌더가 끝나지 않는 사고를 막기 위함입니다.
