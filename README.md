# Vancouver Tech Events

여러 사이트의 벤쿠버 이벤트를 모아 **캘린더 웹페이지**로 보여주고, **매주 월요일 텔레그램**으로 앞으로 7일 일정을 보내줍니다.

```
sources.json (출처 목록)
  → GitHub Actions 매일 수집 (src/build.py → luma / productbc / generic 수집기)
  → docs/events.json + docs/data.js
       ├→ docs/index.html  (캘린더 + 출처 on/off·추가·삭제)
       └→ src/digest.py    (월요일 텔레그램 알림)
```

## 가장 빨리 데이터 보는 법 (GitHub 없이)
```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m src.build        # 수집 → docs/events.json, docs/data.js
```
그다음 `docs/index.html`을 **더블클릭으로 그냥 열면** 됩니다 (서버 불필요).
지금 들어 있는 `[샘플]` 이벤트는 수집이 한 번 돌면 사라집니다.

## 출처 관리
페이지 상단 "이벤트 출처" 패널에서:
- **스위치**: 해당 출처 이벤트를 달력에서 켜고 끔 (내 브라우저에만 저장)
- **출처 추가**: 이벤트 목록 페이지 URL 입력. luma.com / productbc.ca는 전용 수집기, 그 외는 범용 수집기(JSON-LD 기반)로 자동 지정
- **삭제 / 복원**
- **설정 내보내기**: 현재 상태를 `sources.json` 형식으로 출력 → 저장소의 `sources.json`을 교체해 커밋하면 **실제 수집 대상**에 반영

페이지의 변경은 내 브라우저에서만 즉시 바뀌고, 수집 대상까지 바꾸려면 `sources.json` 반영이 필요합니다 (정적 페이지라 서버에 저장할 수 없기 때문).
`sources.json`의 `enabled: false`인 출처는 수집을 건너뜁니다 (Eventbrite는 기본 꺼짐).

> 범용 수집기는 사이트가 schema.org Event(JSON-LD)를 제공할 때만 동작합니다. 0건이면 전용 수집기가 필요하고, 텔레그램으로 경고가 옵니다.

## GitHub 설정 (자동화)
1. **텔레그램 봇**: `@BotFather` → `/newbot` → 토큰. 봇에게 메시지를 보낸 뒤 `https://api.telegram.org/bot<토큰>/getUpdates`에서 `chat.id` 확인
2. 저장소에 푸시 → **Settings → Secrets and variables → Actions**
   - Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`(선택, 없으면 설명 앞부분을 요약 대신 사용)
   - Variables: `SITE_URL` = Pages 주소
3. **Settings → Pages → main / `/docs`**
4. **Actions → update-events → Run workflow → both**

## 첫 실행 확인 (중요)
Luma, Product BC는 비공식 방식이라 로그에서 `[luma-tech] … N개`, `[productbc] … N개`가 0이 아닌지 확인하세요. 0이면 로그를 공유해 주세요.

## 커스터마이징
- 벤쿠버 범위: `src/common.py`의 `AREA_KEYWORDS`
- 알림 요일/시간: `.github/workflows/update.yml` cron (UTC)
- 알림 범위: `src/digest.py`의 `DAYS_AHEAD`
