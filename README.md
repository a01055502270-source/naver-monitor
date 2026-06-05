# 네이버 부동산 전·월세 모니터

하남시 / 강동구 / 남양주 다산 일대의 **전세·월세 신규 매물을 자동 감지**하고
텔레그램으로 알림을 보내는 로컬 모니터링 도구.

## 적용 필터

| 항목 | 조건 |
|---|---|
| 거래 유형 | 전세 + 월세 |
| 매물 유형 | 아파트 + 빌라·연립·다세대 |
| 보증금 | 2억 이하 |
| 월세 | 240만원 이하 |
| 전용면적 | 41~100㎡ |

## 요구사항

- Python 3.8+
- 인터넷 연결

## 설치

```bash
pip install -r requirements.txt
```

## 초기 설정 (순서대로)

### 1. 텔레그램 봇 설정

1. 텔레그램에서 **@BotFather** 검색 → `/newbot` 명령으로 봇 생성
2. 발급된 **HTTP API Token** 복사
3. 만들어진 봇에 메시지 한 번 전송 ("안녕" 등)
4. 브라우저에서 아래 URL 열어 `chat_id` 확인:
   ```
   https://api.telegram.org/bot{TOKEN}/getUpdates
   ```
5. `config.py` 에서 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 입력

### 2. 지역 코드(cortarNo) 확인 — 선택 사항

`config.py` 의 기본 좌표로도 동작하지만, cortarNo 를 입력하면 더 정확하게 필터된다.

```bash
python regions.py
```

출력된 스니펫을 `config.py` → `REGIONS` 의 `"cortar_no"` 에 붙여넣기.

### 3. 동작 확인 (dry-run)

DB 나 텔레그램에 반영하지 않고 수집·필터만 테스트:

```bash
python main.py --dry-run
```

특정 지역만 먼저 테스트:

```bash
python main.py --dry-run --region "미사"
```

콘솔 로그에 `[알림 미설정 — 콘솔 출력]` 또는 매물 PREVIEW 가 뜨면 정상.

> **API 응답 구조 확인 방법**
> 만약 매물 0건이 나오면 `collector.py` 의 `_parse_body()` 에서
> `logger.debug` 로그를 보고 실제 응답 key 를 확인한 뒤
> `("body", "articleList", ...)` 리스트를 수정하세요.
> Chrome 개발자도구 → Network 탭에서 `articleList` 요청을 직접 확인하는 방법이 가장 확실합니다.

## 실행

```bash
python main.py
```

로그는 `monitor.log` 파일에도 기록됨.

## 자동화 (cron)

터미널에서 `crontab -e` 편집:

```cron
# 2시간마다 실행 (오전 7시 ~ 자정)
0 7,9,11,13,15,17,19,21,23 * * *  cd /path/to/naver_monitor && python main.py >> monitor.log 2>&1
```

GitHub Actions 를 쓴다면 `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    - cron: '0 */2 * * *'   # 2시간마다
jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
```

> GitHub Actions 를 쓰는 경우 `config.py` 에서 토큰을 읽는 대신
> `os.environ.get()` 로 환경 변수에서 읽도록 수정하면 더 안전합니다.

## 데이터베이스 조회

수집된 매물은 `naver_monitor.db` (SQLite) 에 저장됩니다.

```bash
# 현재 활성 매물 목록
sqlite3 naver_monitor.db "
  SELECT region_name, complex_name, trade_type,
         deposit_manwon, rent_manwon, area_excl_m2, floor_info
  FROM listings
  WHERE status='active'
  ORDER BY first_seen_at DESC
  LIMIT 50;
"

# 지역별 매물 수
sqlite3 naver_monitor.db "
  SELECT region_name, COUNT(*) as cnt
  FROM listings WHERE status='active'
  GROUP BY region_name;
"

# 실행 로그 확인
sqlite3 naver_monitor.db "SELECT * FROM run_log ORDER BY run_at DESC LIMIT 20;"
```

## 파일 구조

```
naver_monitor/
├── config.py       ← 모든 설정 (여기만 수정하면 됨)
├── main.py         ← 실행 진입점
├── collector.py    ← 네이버 API 호출
├── processor.py    ← 정규화·필터·diff 로직
├── db.py           ← SQLite CRUD
├── notifier.py     ← 텔레그램 알림
├── regions.py      ← cortarNo 탐색 유틸 (최초 1회)
└── requirements.txt
```

## 알려진 제한사항

- 네이버 약관상 공식 허용 수집이 아님. **개인 이용·저빈도** 전제.
- 과도한 호출 시 일시 차단될 수 있음 (딜레이 자동 적용됨).
- 소멸 감지는 "내 필터 내에서" 사라진 경우만 탐지. 가격이 올라 필터 밖으로 나간 경우도 소멸로 처리됨.
- API 응답 구조는 네이버 업데이트에 따라 바뀔 수 있음. 0건이면 devtools 로 확인.
