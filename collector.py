"""
collector.py — 네이버 부동산 모바일 API 호출 + 전 페이지 수집

사용 엔드포인트: m.land.naver.com/cluster/ajax/articleList
 - Bearer 토큰 불필요 (headers + session cookie 만으로 동작)
 - bbox(좌표 범위) + 필터 파라미터로 개별 매물 반환
 - 응답 구조: {"isMoreData": bool, "body": [...], ...}
"""

import time
import random
import logging
from typing import List, Tuple

import requests

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://m.land.naver.com/cluster/ajax/articleList"

# 실제 모바일 Chrome UA 로 위장
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
    "Sec-Fetch-Site":  "same-origin",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Dest":  "empty",
}

# Session 을 재사용해 쿠키 유지 (봇 탐지 완화)
_session = requests.Session()
_session.headers.update(_HEADERS)


def _bbox(region: dict) -> dict:
    lat, lon = region["lat"], region["lon"]
    d_lat    = config.BBOX_DELTA_LAT
    d_lon    = config.BBOX_DELTA_LON
    return {
        "btm": round(lat - d_lat, 7),
        "lft": round(lon - d_lon, 7),
        "top": round(lat + d_lat, 7),
        "rgt": round(lon + d_lon, 7),
    }


def _parse_body(data: dict) -> Tuple[List[dict], bool]:
    """응답 JSON 에서 매물 목록과 '더 있는지' 여부를 추출.

    Naver 는 API 버전에 따라 key 가 다를 수 있으므로 여러 key 를 시도.
    처음 실행 시 로그에 찍히는 'unknown keys' 를 보고 맞춰 넣을 것.
    """
    articles = None
    for key in ("body", "articleList", "result", "items", "data"):
        val = data.get(key)
        if isinstance(val, list):
            articles = val
            break

    if articles is None:
        logger.debug(f"알 수 없는 응답 구조 — 최상위 keys: {list(data.keys())}")
        logger.debug(f"응답 앞 200자: {str(data)[:200]}")
        articles = []

    is_more = bool(data.get("isMoreData", False))
    # isMoreData 키가 없을 경우 페이지 꽉 찬 경우(20건)면 더 있다고 가정
    if "isMoreData" not in data:
        is_more = len(articles) >= 20

    return articles, is_more


def fetch_page(region: dict, page: int) -> Tuple[List[dict], bool]:
    """단일 페이지 요청 → (articles, is_more)."""
    params = {
        "rletTpCd": config.RLET_TP,
        "tradTpCd": config.TRAD_TP,
        "z":        config.ZOOM,
        "lat":      region["lat"],
        "lon":      region["lon"],
        **_bbox(region),
        "spcMin":   int(config.AREA_MIN_M2),   # 전용면적 하한 (API 파라미터)
        "spcMax":   int(config.AREA_MAX_M2),   # 전용면적 상한
        "showR0":   "",
        "page":     page,
    }
    # cortarNo 가 설정된 경우 추가 필터로 사용
    if region.get("cortar_no"):
        params["cortarNo"] = region["cortar_no"]

    try:
        resp = _session.get(BASE_URL, params=params, timeout=12)

        if resp.status_code == 429:
            logger.warning("Rate-limit(429) — 15초 대기 후 재시도")
            time.sleep(15)
            resp = _session.get(BASE_URL, params=params, timeout=12)

        resp.raise_for_status()
        return _parse_body(resp.json())

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP {e.response.status_code} | {region['name']} p{page}")
        return [], False
    except requests.exceptions.RequestException as e:
        logger.error(f"요청 실패 | {region['name']} p{page}: {e}")
        return [], False
    except Exception as e:
        logger.error(f"파싱 오류 | {region['name']} p{page}: {e}")
        return [], False


def collect_region(region: dict) -> List[dict]:
    """한 지역의 전 페이지를 순회해 원시 매물 dict 목록 반환."""
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

        # 페이지 간 랜덤 딜레이 (anti-bot)
        time.sleep(random.uniform(*config.REQUEST_DELAY))

    return all_articles
