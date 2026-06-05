"""
processor.py — 정규화 · 필터링 · diff

직방(Zigbang) API와 네이버 API 양쪽 필드를 모두 처리한다.
"""

import os, logging
from typing import List, Tuple, Optional

import config

# DB 모듈 자동 감지 (Supabase 우선)
if os.environ.get("SUPABASE_URL"):
    from db_supabase import get_article, get_active_nos_by_region
else:
    from db import get_article, get_active_nos_by_region

logger = logging.getLogger(__name__)


# ── 가격 파싱 (네이버 형식: "4억 5,000") ─────────────────────
def _parse_price_manwon(raw) -> int:
    if not raw:
        return 0
    try:
        return int(raw)          # 이미 숫자면 그대로
    except (ValueError, TypeError):
        pass
    s = str(raw).strip().replace(",", "").replace(" ", "").replace("만원", "")
    if s in ("-", ""):
        return 0
    total = 0
    if "억" in s:
        parts = s.split("억")
        try: total += int(parts[0]) * 10_000
        except ValueError: pass
        rem = parts[1] if len(parts) > 1 else ""
        if rem:
            try: total += int(rem)
            except ValueError: pass
    else:
        try: total = int(s)
        except ValueError: pass
    return total


def _parse_area(raw) -> float:
    if not raw:
        return 0.0
    try:
        return round(float(str(raw).replace("m²","").replace("㎡","").strip()), 2)
    except (ValueError, TypeError):
        return 0.0


# ── 정규화 ────────────────────────────────────────────────────
def normalize_article(raw: dict) -> dict:
    """직방 또는 네이버 API 응답 → 공통 DB 스키마."""
    is_zb = "item_id" in raw   # 직방 판별

    # article_no
    if is_zb:
        article_no = f"zb_{raw['item_id']}"
    else:
        article_no = str(raw.get("articleNo") or raw.get("atclNo") or raw.get("id") or "")
    if not article_no or article_no in ("zb_", ""):
        return {}

    # 거래 유형
    if is_zb:
        sales_type = raw.get("sales_type", "")
        trade_code = {"전세": "B1", "월세": "B2"}.get(sales_type, "B2")
    else:
        trade_code = raw.get("tradeTypeCode") or raw.get("tradTpCd") or ""

    # 가격
    if is_zb:
        deposit_manwon = int(raw.get("deposit") or 0)
        rent_manwon    = int(raw.get("rent")    or 0)
    else:
        deposit_manwon = _parse_price_manwon(
            raw.get("dealOrWarrantPrc") or raw.get("warrantPrc") or raw.get("dealPrc") or "0")
        rent_manwon = _parse_price_manwon(
            raw.get("rentPrc") or raw.get("monthlyPrc") or "0")

    # 면적
    if is_zb:
        area_excl   = _parse_area(raw.get("size_m2") or raw.get("전용면적") or 0)
        area_supply = _parse_area(raw.get("supply_size_m2") or 0)
    else:
        area_excl   = _parse_area(raw.get("spc2") or raw.get("exclusiveSpace") or 0)
        area_supply = _parse_area(raw.get("spc1") or raw.get("supplySpace") or 0)

    # 층수
    if is_zb:
        fl  = raw.get("floor", "")
        bfl = raw.get("building_floor", "")
        floor_info = f"{fl}/{bfl}" if fl and bfl else str(fl or "")
    else:
        floor_info = raw.get("floorInfo") or raw.get("flrInfo") or ""

    # 단지명
    if is_zb:
        complex_name = (raw.get("address1") or raw.get("name") or
                        raw.get("building_name") or "")
        building_name = raw.get("address2") or ""
    else:
        complex_name  = raw.get("articleName") or raw.get("atclNm") or ""
        building_name = raw.get("buildingName") or raw.get("bldNm") or ""

    # 방향 / 특징
    direction    = raw.get("direction") or raw.get("atclDrctn") or ""
    feature_desc = (raw.get("description") or raw.get("articleFeatureDesc") or
                    raw.get("atclFetrDesc") or "")[:100]
    realtor_name = raw.get("agent_name") or raw.get("realtorName") or raw.get("rltrNm") or ""
    confirmed    = raw.get("exposeStartYMD") or raw.get("exposeYmd") or ""

    # 매물 URL
    if is_zb:
        detail_url = f"https://www.zigbang.com/home/apt/items/{raw['item_id']}"
    else:
        detail_url = f"https://fin.land.naver.com/articles/{article_no}"

    return {
        "article_no":       article_no,
        "region_name":      raw.get("_region_name", ""),
        "region_code":      raw.get("_cortar_no", ""),
        "real_estate_type": raw.get("_service_type") or raw.get("realEstateTypeCode") or "APT",
        "trade_type":       trade_code,
        "complex_name":     complex_name,
        "building_name":    building_name,
        "deposit_manwon":   deposit_manwon,
        "rent_manwon":      rent_manwon,
        "area_supply_m2":   area_supply,
        "area_excl_m2":     area_excl,
        "floor_info":       floor_info,
        "direction":        direction,
        "feature_desc":     feature_desc,
        "realtor_name":     realtor_name,
        "confirmed_date":   confirmed,
        "detail_url":       detail_url,
    }


# ── 필터 ─────────────────────────────────────────────────────
def passes_filter(art: dict) -> bool:
    if not art.get("article_no"):
        return False
    if art["deposit_manwon"] > config.DEPOSIT_MAX_MANWON:
        return False
    if art["rent_manwon"] > config.RENT_MAX_MANWON:
        return False
    area = art["area_excl_m2"]
    if area > 0 and not (config.AREA_MIN_M2 <= area <= config.AREA_MAX_M2):
        return False
    return True


# ── diff ─────────────────────────────────────────────────────
def compute_diff(region_name, incoming):
    current = {a["article_no"] for a in incoming}
    db_nos  = set(get_active_nos_by_region(region_name))

    new_arts, changed = [], []
    for art in incoming:
        ex = get_article(art["article_no"])
        if ex is None:
            new_arts.append(art)
        elif (ex["deposit_manwon"] != art["deposit_manwon"] or
              ex["rent_manwon"]    != art["rent_manwon"]):
            art["prev_deposit"] = ex["deposit_manwon"]
            art["prev_rent"]    = ex["rent_manwon"]
            changed.append(art)

    gone = list(db_nos - current)
    return new_arts, changed, gone
