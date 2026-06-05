"""
collector.py — 직방 API 기반 매물 수집기 (Naver 대체)

직방은 GitHub Actions(미국 서버)에서도 차단 없이 접근 가능.
두 단계:
  1. GET /v2/items         → geohash + 조건으로 item_id 목록 수집
  2. POST /v2/items/list   → item_id로 상세 정보 배치 수집
"""

import time, logging
from typing import List
import requests
import geohash2
import config

logger = logging.getLogger(__name__)

API_BASE = "https://apis.zigbang.com"
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Accept":          "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer":         "https://www.zigbang.com/",
    "Origin":          "https://www.zigbang.com",
}

# 수집할 서비스 유형
SERVICE_TYPES = ["아파트", "빌라"]


def _get_ids(geohash: str, service_type: str) -> List[int]:
    """geohash + 서비스 유형으로 item_id 목록 반환."""
    try:
        r = requests.get(
            f"{API_BASE}/v2/items",
            params={
                "deposit_gteq":      0,
                "domain":            "zigbang",
                "geohash":           geohash,
                "needHasNoFiltered": "true",
                "rent_gteq":         0,
                "sales_type_in":     "전세|월세",
                "service_type_eq":   service_type,
            },
            headers=HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        logger.info(f"    {service_type}: {len(items)}건 ID 수집")
        # 디버그: 첫 항목 구조 확인
        if items:
            logger.debug(f"    샘플 item: {list(items[0].keys())}")
        return [it["item_id"] for it in items if "item_id" in it]
    except Exception as e:
        logger.error(f"    ID 수집 실패 ({service_type}): {e}")
        return []


def _get_details(ids: List[int]) -> List[dict]:
    """item_id 리스트 → 상세 정보 배치 수집 (100개씩)."""
    all_items = []
    for i in range(0, len(ids), 100):
        batch = ids[i:i+100]
        try:
            r = requests.post(
                f"{API_BASE}/v2/items/list",
                params={"domain": "zigbang", "withCoalition": "true", "item_ids": batch},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            all_items.extend(items)
            # 디버그: 첫 배치의 첫 항목 구조
            if i == 0 and items:
                logger.debug(f"    상세 샘플 keys: {list(items[0].keys())}")
                logger.debug(f"    상세 샘플 값: {items[0]}")
            if i > 0:
                time.sleep(0.4)
        except Exception as e:
            logger.error(f"    상세 수집 실패 (batch {i//100+1}): {e}")
    return all_items


def collect_region(region: dict) -> List[dict]:
    """한 지역 전·월세 아파트+빌라 전체 수집."""
    lat, lon = region["lat"], region["lon"]
    gh = geohash2.encode(lat, lon, precision=5)
    logger.info(f"  [{region['name']}] geohash={gh}")

    all_raw = []
    for svc in SERVICE_TYPES:
        ids = _get_ids(gh, svc)
        if not ids:
            continue
        details = _get_details(ids)
        for item in details:
            item["_service_type"] = "APT" if svc == "아파트" else "VL"
            item["_region_name"]  = region["name"]
            item["_cortar_no"]    = region.get("cortar_no", "")
        all_raw.extend(details)
        time.sleep(0.5)

    logger.info(f"  [{region['name']}] 총 {len(all_raw)}건")
    return all_raw
