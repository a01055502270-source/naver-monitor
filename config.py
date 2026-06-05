import os
# ============================================================
# config.py — 모든 설정을 여기서 관리
# ============================================================

# ── 필터 조건 (확정) ─────────────────────────────────────────
DEPOSIT_MAX_MANWON = 20_000     # 보증금 상한 2억 (만원)
RENT_MAX_MANWON    = 240        # 월세 상한 240만원
AREA_MIN_M2        = 41.0       # 전용면적 하한 (㎡)
AREA_MAX_M2        = 100.0      # 전용면적 상한 (㎡)

# ── 매물 유형 / 거래 유형 ────────────────────────────────────
#   APT  = 아파트
#   VL   = 빌라·연립·다세대
#   B1   = 전세  /  B2 = 월세
RLET_TP = "APT:VL"
TRAD_TP = "B1:B2"

# ── 텔레그램 알림 ────────────────────────────────────────────
#   1. BotFather → /newbot → 토큰 발급
#   2. 봇에게 메시지 한 번 보낸 뒤
#      https://api.telegram.org/bot{TOKEN}/getUpdates 에서 chat_id 확인
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "YOUR_CHAT_ID")

# ── DB 경로 (SQLite) ─────────────────────────────────────────
DB_PATH = "naver_monitor.db"

# ── 수집 파라미터 ─────────────────────────────────────────────
ZOOM           = 16         # 줌 레벨 (16 이상 = 개별 매물 반환)
BBOX_DELTA_LAT = 0.018      # 중심 좌표 기준 bbox 반경 (위도, 약 2km)
BBOX_DELTA_LON = 0.024      # bbox 반경 (경도)
REQUEST_DELAY  = (1.2, 2.8) # 페이지 간 딜레이 (초, 랜덤 범위)
MAX_PAGES      = 25         # 지역당 최대 페이지 (페이지당 20건 → 최대 500건)

# ── 모니터링 대상 지역 ────────────────────────────────────────
#
#   lat/lon : 동 중심 좌표 (대략값 — 정밀도 불필요)
#   cortar_no : 네이버 법정동 코드 (선택 사항)
#               정확한 값은 regions.py 를 실행해서 확인 후 채워 넣기.
#               비워두면 bbox 기반으로만 수집 (이것만으로도 동작함).
#
REGIONS = [
    # ── 하남시 ──────────────────────────────────────────────
    {
        "name"      : "하남 미사동",
        "lat"       : 37.5596,
        "lon"       : 127.1935,
        "cortar_no" : "",   # TODO: regions.py 로 확인
    },
    {
        "name"      : "하남 감일동",
        "lat"       : 37.4752,
        "lon"       : 127.1505,
        "cortar_no" : "",
    },
    {
        "name"      : "하남 덕풍·신장동",
        "lat"       : 37.5430,
        "lon"       : 127.2042,
        "cortar_no" : "",
    },
    {
        "name"      : "하남 위례(학암동)",
        "lat"       : 37.4900,
        "lon"       : 127.1325,
        "cortar_no" : "",
    },
    # ── 강동구 ──────────────────────────────────────────────
    {
        "name"      : "강동 고덕동",
        "lat"       : 37.5538,
        "lon"       : 127.1508,
        "cortar_no" : "",
    },
    {
        "name"      : "강동 상일·강일동",
        "lat"       : 37.5580,
        "lon"       : 127.1750,
        "cortar_no" : "",
    },
    {
        "name"      : "강동 명일·천호동",
        "lat"       : 37.5478,
        "lon"       : 127.1350,
        "cortar_no" : "",
    },
    # ── 남양주 다산신도시 ─────────────────────────────────────
    {
        "name"      : "남양주 다산(지금동)",
        "lat"       : 37.5939,
        "lon"       : 127.2067,
        "cortar_no" : "",
    },
    {
        "name"      : "남양주 다산(도농동)",
        "lat"       : 37.5898,
        "lon"       : 127.1820,
        "cortar_no" : "",
    },
]


# Supabase (환경 변수에서 읽음)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))
