# CLAUDE.md

숏폼(릴스/쇼츠) 편집 파이프라인. 사용자는 한국어로 소통한다. 사용법·script.json 형식은 README.md 참고.

## 작업 흐름 (Claude가 오케스트레이터)

1. 사용자가 `projects/<이름>/clips/`에 원본 클립을 준다.
2. 클립에서 프레임을 뽑아(`reels.ff.frame`) 내용을 파악하고, 대본 초안을 짠다 → **사용자 컨펌 후** script.json 작성.
3. 문장마다 어울리는 클립 구간(`clip`, `start`)을 매칭한다.
4. `python -m reels render projects/<이름>/script.json` → `output/<이름>_preview.png`를 직접 보고 자막 밀림·겹침을 점검.
5. 사용자의 레이아웃 피드백("조금 위로", "더 투명하게")은 README의 용어표에 따라 `style` 값으로 옮겨 재렌더.
6. 발행(YouTube/Instagram)은 되돌릴 수 없는 공개 행위 — 반드시 사용자의 명시적 확인 후에만.

## 규칙

- API 키는 `.env`에서만 읽는다. 코드·커밋에 넣지 않는다.
- TTS 엔진은 edge(무료, 기본) / elevenlabs / silent. `cache/tts`에 해시 캐싱되어 같은 문장·보이스·속도면 재호출하지 않는다.
- 이 클라우드 환경에서 edge-tts를 돌릴 땐 `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt`가 필요하다 (프록시 인증서).
- ffmpeg 호출에는 항상 `-t`로 출력 길이를 못박는다 (루프 입력 무한 렌더 방지).
- 검증: `python -m reels demo`가 오류 없이 `output/demo.mp4`(1080x1920)를 만들어야 한다.
