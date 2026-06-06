"""
processor.py — 정규화 · 필터링 · diff (네이버 API 기반)
"""

import os
import logging
from typing import List, Tuple, Optional

import config

if os.environ.get("SUPABASE_URL"):
    from db_supabase import get_article, get_active_nos_by_region
else:
    from db import get_article, get_active_nos_by_region

logger = logging.getLogger(__name__)


def _parse_price_manwon(raw) -> int:
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
        rem = parts[1] if len(parts) > 1 else ""
        if rem:
            try:
                total += int(rem)
            except ValueError:
                pass
    else:
        try:
            total = int(s)
        except ValueError:
            pass
    return total


def _parse_area(raw) -> float:
    if not raw:
        return 0.0
    try:
        return round(float(str(raw).replace("m²","").replace("㎡","").strip()), 2)
    except (ValueError, TypeError):
        return 0.0


def _get(raw: dict, *keys, default="") -> str:
    for k in keys:
        v = raw.get(k)
        if v is not None and str(v).strip() not in ("", "0", "null"):
            return str(v).strip()
    return default


def normalize_article(raw: dict) -> dict:
    article_no = _get(raw, "articleNo", "atclNo", "id")
    if not article_no:
        return {}

    deposit_raw = _get(raw, "dealOrWarrantPrc", "warrantPrc", "dealPrc", "prc")
    rent_raw    = _get(raw, "rentPrc", "monthlyPrc", "rentPrice", default="0")

    return {
        "article_no":       article_no,
        "region_name":      raw.get("_region_name", ""),
        "region_code":      raw.get("_cortar_no", ""),
        "real_estate_type": _get(raw, "realEstateTypeCode", "rletTpCd"),
        "trade_type":       _get(raw, "tradeTypeCode", "tradTpCd", "tradeType"),
        "complex_name":     _get(raw, "articleName", "atclNm", "complexName"),
        "building_name":    _get(raw, "buildingName", "bldNm"),
        "deposit_manwon":   _parse_price_manwon(deposit_raw),
        "rent_manwon":      _parse_price_manwon(rent_raw),
        "area_supply_m2":   _parse_area(_get(raw, "spc1", "supplySpace")),
        "area_excl_m2":     _parse_area(_get(raw, "spc2", "exclusiveSpace")),
        "floor_info":       _get(raw, "floorInfo", "flrInfo"),
        "direction":        _get(raw, "direction", "atclDrctn"),
        "feature_desc":     _get(raw, "articleFeatureDesc", "atclFetrDesc")[:100],
        "realtor_name":     _get(raw, "realtorName", "rltrNm"),
        "confirmed_date":   _get(raw, "exposeStartYMD", "exposeYmd"),
        "detail_url":       f"https://fin.land.naver.com/articles/{article_no}",
    }


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
