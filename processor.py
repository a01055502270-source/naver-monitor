"""
processor.py — 정규화 · 필터링 · diff (신규/변동/소멸 탐지)
"""

import logging
from typing import List, Tuple, Optional

import os
import config

# Supabase 환경이면 db_supabase, 아니면 로컬 SQLite
if os.environ.get("SUPABASE_URL"):
    from db_supabase import get_article, get_active_nos_by_region
else:
    from db import get_article, get_active_nos_by_region

logger = logging.getLogger(__name__)


# ── 가격 파싱 ────────────────────────────────────────────────

def _parse_price_manwon(raw) -> int:
    """
    '4억 5,000' → 45000
    '5,000'     → 5000
    '3억'       → 30000
    '150'       → 150   (월세 만원 단위)
    0 / '' / None → 0
    """
    if not raw:
        return 0
    s = str(raw).strip().replace(",", "").replace(" ", "").replace("만원", "")
    if s in ("-", ""):
        return 0
    total = 0
    if "억" in s:
        parts = s.split("억")
        try:
            total += int(parts[0]) * 10_000
        except ValueError:
            pass
        remainder = parts[1] if len(parts) > 1 else ""
        if remainder:
            try:
                total += int(remainder)
            except ValueError:
                pass
    else:
        try:
            total = int(s)
        except ValueError:
            logger.debug(f"가격 파싱 실패: {raw!r}")
    return total


def _parse_area(raw) -> float:
    if not raw:
        return 0.0
    try:
        return round(float(str(raw).replace("m²", "").replace("㎡", "").strip()), 2)
    except (ValueError, TypeError):
        return 0.0


# ── 정규화 ───────────────────────────────────────────────────

def _get(raw: dict, *keys, default="") -> str:
    """여러 후보 key 를 순서대로 시도해 첫 번째 유효값 반환.
    API 버전 간 필드명 차이를 흡수한다.
    """
    for k in keys:
        v = raw.get(k)
        if v is not None and str(v).strip() not in ("", "0", "null"):
            return str(v).strip()
    return default


def normalize_article(raw: dict) -> dict:
    """원시 API dict → 정규화된 dict.

    [key 매핑 대조표]
    모바일 API     PC new.land API    의미
    articleNo      atclNo             매물 고유번호
    articleName    atclNm             단지/건물명
    tradeTypeCode  tradTpCd           거래유형 코드
    dealOrWarrantPrc  warrantPrc      보증금/전세금
    rentPrc        monthlyPrc         월세
    spc1           supplySpace        공급면적
    spc2           exclusiveSpace     전용면적
    floorInfo      flrInfo            층 정보
    exposeStartYMD exposeYmd          등록(확인)일
    """
    article_no = _get(raw, "articleNo", "atclNo", "id")
    if not article_no:
        logger.debug(f"articleNo 없는 항목 스킵: {list(raw.keys())}")
        return {}

    deposit_raw = _get(raw, "dealOrWarrantPrc", "warrantPrc", "dealPrc", "prc")
    rent_raw    = _get(raw, "rentPrc", "monthlyPrc", "rentPrice", default="0")

    trade_code = _get(raw, "tradeTypeCode", "tradTpCd", "tradeType")

    return {
        "article_no":       article_no,
        "region_name":      raw.get("_region_name", ""),
        "region_code":      raw.get("_cortar_no", ""),
        "real_estate_type": _get(raw, "realEstateTypeCode", "rletTpCd"),
        "trade_type":       trade_code,
        "complex_name":     _get(raw, "articleName", "atclNm", "complexName"),
        "building_name":    _get(raw, "buildingName", "bldNm"),
        "deposit_manwon":   _parse_price_manwon(deposit_raw),
        "rent_manwon":      _parse_price_manwon(rent_raw),
        "area_supply_m2":   _parse_area(_get(raw, "spc1", "supplySpace", "supplySpc")),
        "area_excl_m2":     _parse_area(_get(raw, "spc2", "exclusiveSpace", "exclusiveSpc")),
        "floor_info":       _get(raw, "floorInfo", "flrInfo"),
        "direction":        _get(raw, "direction", "atclDrctn"),
        "feature_desc":     _get(raw, "articleFeatureDesc", "atclFetrDesc"),
        "realtor_name":     _get(raw, "realtorName", "rltrNm"),
        "confirmed_date":   _get(raw, "exposeStartYMD", "exposeYmd", "verifyYMD"),
        "detail_url":       f"https://fin.land.naver.com/articles/{article_no}",
    }


# ── 필터 ─────────────────────────────────────────────────────

def passes_filter(art: dict) -> bool:
    """사용자 조건 충족 여부.

    조건: 보증금 > 2억 OR 월세 > 240만원 이면 제외
          전용면적 41~100㎡ 범위 밖이면 제외
    """
    if not art.get("article_no"):
        return False

    deposit = art["deposit_manwon"]
    rent    = art["rent_manwon"]
    area    = art["area_excl_m2"]

    if deposit > config.DEPOSIT_MAX_MANWON:
        return False
    if rent > config.RENT_MAX_MANWON:
        return False
    # 면적 정보가 있는 경우에만 필터 적용 (면적 미기재 매물은 통과시킴)
    if area > 0 and not (config.AREA_MIN_M2 <= area <= config.AREA_MAX_M2):
        return False

    return True


# ── diff ─────────────────────────────────────────────────────

def compute_diff(
    region_name: str,
    incoming: List[dict],
) -> Tuple[List[dict], List[dict], List[str]]:
    """
    Parameters
    ----------
    region_name : str
        DB 에서 이 지역의 기존 active 매물을 조회하는 데 사용
    incoming : List[dict]
        이번 수집에서 필터를 통과한 매물 목록

    Returns
    -------
    new_articles     : DB 에 없던 완전 신규 매물
    changed_articles : 보증금 또는 월세가 바뀐 매물 (prev_deposit, prev_rent 포함)
    gone_ids         : DB 에는 있는데 이번 수집에 없는 매물 article_no 목록
    """
    current_nos: set = {a["article_no"] for a in incoming}
    db_nos:      set = set(get_active_nos_by_region(region_name))

    new_articles:     List[dict] = []
    changed_articles: List[dict] = []

    for art in incoming:
        no = art["article_no"]
        existing: Optional[dict] = get_article(no)

        if existing is None:
            new_articles.append(art)
        else:
            if (existing["deposit_manwon"] != art["deposit_manwon"] or
                    existing["rent_manwon"] != art["rent_manwon"]):
                art["prev_deposit"] = existing["deposit_manwon"]
                art["prev_rent"]    = existing["rent_manwon"]
                changed_articles.append(art)

    gone_ids: List[str] = list(db_nos - current_nos)

    return new_articles, changed_articles, gone_ids
