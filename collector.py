"""
collector.py — 네이버 부동산 모바일 API 기반 매물 수집기

한국 IP 환경(네이버 클라우드 서울 서버)에서 실행.
"""

import time
import random
import logging
from typing import List, Tuple

import requests
import config

logger = logging.getLogger(__name__)

BASE_URL = "https://m.land.naver.com/cluster/ajax/articleList"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S901N) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.6099.144 Mobile Safari/537.36"
    ),
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://m.land.naver.com/",
    "X-Requested-With": "XMLHttpRequest",
}

_session = requests.Session()
_session.headers.update(_HEADERS)


def _bbox(region: dict) -> dict:
    lat, lon = region["lat"], region["lon"]
    d_lat = config.BBOX_DELTA_LAT
    d_lon = config.BBOX_DELTA_LON
    return {
        "btm": round(lat - d_lat, 7),
        "lft": round(lon - d_lon, 7),
        "top": round(lat + d_lat, 7),
        "rgt": round(lon + d_lon, 7),
    }


def _parse_body(data: dict) -> Tuple[List[dict], bool]:
    articles = None
    for key in ("body", "articleList", "result", "items", "data"):
        val = data.get(key)
        if isinstance(val, list):
            articles = val
            break

    if articles is None:
        logger.debug(f"알 수 없는 응답 구조 — 키: {list(data.keys())}")
        articles = []

    is_more = bool(data.get("isMoreData", False))
    if "isMoreData" not in data:
        is_more = len(articles) >= 20

    return articles, is_more


def fetch_page(region: dict, page: int) -> Tuple[List[dict], bool]:
    params = {
        "rletTpCd": config.RLET_TP,
        "tradTpCd": config.TRAD_TP,
        "z":        config.ZOOM,
        "lat":      region["lat"],
        "lon":      region["lon"],
        **_bbox(region),
        "spcMin":   int(config.AREA_MIN_M2),
        "spcMax":   int(config.AREA_MAX_M2),
        "showR0":   "",
        "page":     page,
    }
    if region.get("cortar_no"):
        params["cortarNo"] = region["cortar_no"]

    try:
        resp = _session.get(BASE_URL, params=params, timeout=25)

        if resp.status_code == 429:
            logger.warning("Rate-limit(429) — 15초 대기")
            time.sleep(15)
            resp = _session.get(BASE_URL, params=params, timeout=25)

        resp.raise_for_status()
        return _parse_body(resp.json())

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP {e.response.status_code} | {region['name']} p{page}")
        return [], False
    except Exception as e:
        logger.error(f"요청 실패 | {region['name']} p{page}: {e}")
        return [], False


def collect_region(region: dict) -> List[dict]:
    all_articles: List[dict] = []

    for page in range(1, config.MAX_PAGES + 1):
        articles, is_more = fetch_page(region, page)
        all_articles.extend(articles)
        logger.info(
            f"  [{region['name']}] p{page}: {len(articles)}건 "
            f"(누적 {len(all_articles)}) {'→ 계속' if is_more else '→ 완료'}"
        )

        if not is_more:
            break

        time.sleep(random.uniform(*config.REQUEST_DELAY))

    return all_articles
