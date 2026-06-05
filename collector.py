"""
collector.py — 직방 API (빌라: new_villa=true, 아파트: 단지 API 시도)
"""
import time, logging
from typing import List
import requests
import geohash2
import config

logger = logging.getLogger(__name__)

BASE = "https://apis.zigbang.com"
HDR  = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "application/json",
    "Referer": "https://www.zigbang.com/",
}


def _fetch_villa(gh4: str, trade: str) -> List[dict]:
    """빌라·연립 — new_villa=true 파라미터."""
    try:
        r = requests.get(f"{BASE}/v2/items",
            params={"domain": "zigbang", "zoom": 14,
                    "sales_type_in": trade,
                    "deposit_lteq": config.DEPOSIT_MAX_MANWON,
                    "rent_lteq":    config.RENT_MAX_MANWON,
                    "new_villa": "true",
                    "geohash":   gh4},
            headers=HDR, timeout=20)
        items = r.json().get("items", [])
        logger.info(f"    빌라({trade}) geohash={gh4}: {len(items)}건 (HTTP {r.status_code})")
        return items
    except Exception as e:
        logger.error(f"    빌라 수집 실패: {e}")
        return []


def _fetch_apt(gh4: str, trade: str) -> List[dict]:
    """아파트 — 단지 마커 → 매물 조회."""
    try:
        # 단지 목록 조회
        r = requests.get(f"{BASE}/v2/complexes/markers",
            params={"domain": "zigbang", "geohash": gh4,
                    "sales_type_in": trade},
            headers=HDR, timeout=20)
        if r.status_code != 200:
            logger.info(f"    아파트 단지 API HTTP {r.status_code} — 스킵")
            return []
        complexes = r.json().get("complexes", r.json().get("markers", []))
        logger.info(f"    아파트 단지: {len(complexes)}개")

        ids = []
        for cx in complexes[:20]:
            cid = cx.get("complex_id") or cx.get("id")
            if cid:
                r2 = requests.get(f"{BASE}/v2/complexes/{cid}/items",
                    params={"domain":"zigbang","sales_type_in":trade},
                    headers=HDR, timeout=15)
                if r2.status_code == 200:
                    for item in r2.json().get("items", []):
                        item["_complex"] = cx.get("name","")
                        ids.append(item)
                time.sleep(0.3)
        logger.info(f"    아파트 매물: {len(ids)}건")
        return ids
    except Exception as e:
        logger.error(f"    아파트 수집 실패: {e}")
        return []


def _get_details(item_ids: List[int]) -> List[dict]:
    """item_id 목록 → 상세 배치 조회."""
    if not item_ids:
        return []
    all_items = []
    for i in range(0, len(item_ids), 100):
        batch = item_ids[i:i+100]
        try:
            r = requests.post(f"{BASE}/v2/items/list",
                params={"domain":"zigbang","withCoalition":"true","item_ids":batch},
                headers=HDR, timeout=20)
            all_items.extend(r.json().get("items", []))
            if i > 0:
                time.sleep(0.4)
        except Exception as e:
            logger.error(f"    상세 조회 실패: {e}")
    return all_items


def collect_region(region: dict) -> List[dict]:
    lat, lon = region["lat"], region["lon"]
    gh4 = geohash2.encode(lat, lon, precision=4)  # 더 넓은 범위
    gh5 = geohash2.encode(lat, lon, precision=5)
    logger.info(f"  [{region['name']}] geohash4={gh4} geohash5={gh5}")

    all_raw = []

    for trade in ["전세", "월세"]:
        # 빌라
        villas = _fetch_villa(gh4, trade)
        ids    = [v["item_id"] for v in villas if "item_id" in v]
        if ids:
            details = _get_details(ids)
            for d in details:
                d["_service_type"] = "VL"
                d["_region_name"]  = region["name"]
                d["_cortar_no"]    = region.get("cortar_no", "")
            all_raw.extend(details)

        # 아파트
        apts = _fetch_apt(gh4, trade)
        for a in apts:
            a["_service_type"] = "APT"
            a["_region_name"]  = region["name"]
            a["_cortar_no"]    = region.get("cortar_no", "")
        all_raw.extend(apts)

        time.sleep(0.5)

    logger.info(f"  [{region['name']}] 총 {len(all_raw)}건")
    return all_raw
