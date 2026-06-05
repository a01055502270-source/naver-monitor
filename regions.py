"""
regions.py — cortarNo 탐색 유틸리티 (최초 1회 실행)

네이버 부동산의 지역 코드(cortarNo) 계층을 탐색해
config.py 에 붙여넣을 스니펫을 출력한다.

실행:
    python regions.py
"""

import json
import time
import requests

BASE = "https://new.land.naver.com/api/regions/list"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://new.land.naver.com/",
    "Accept":  "application/json",
}

# 탐색할 시·도 코드 (네이버 기준)
TOP_LEVEL = [
    ("서울특별시",   "1100000000"),
    ("경기도",       "4100000000"),
]

# 우리가 관심 있는 시·군·구 키워드
TARGET_SGG = ["강동구", "하남시", "남양주시"]

# 우리가 관심 있는 읍·면·동 키워드
TARGET_DONG = [
    "미사", "감일", "덕풍", "신장", "학암",    # 하남
    "고덕", "상일", "강일", "명일", "천호",    # 강동
    "지금", "도농", "다산",                    # 남양주
]


def fetch_regions(cortar_no: str = "") -> list:
    """cortarNo 에 속한 하위 지역 목록 반환."""
    try:
        resp = requests.get(
            BASE,
            params={"cortarNo": cortar_no} if cortar_no else {},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # 응답 key 는 버전마다 다를 수 있음
        for key in ("regionList", "list", "body", "result"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
    except Exception as e:
        print(f"  오류: {e}")
        return []


def extract_coords(region: dict):
    lat = region.get("centerLat") or region.get("latitude") or region.get("lat")
    lon = region.get("centerLon") or region.get("longitude") or region.get("lon")
    return lat, lon


def main():
    print("=" * 60)
    print("네이버 부동산 지역코드(cortarNo) 탐색기")
    print("=" * 60)

    results = []  # (name, lat, lon, cortar_no)

    for sido_name, sido_code in TOP_LEVEL:
        print(f"\n▶ {sido_name} ({sido_code})")
        sgus = fetch_regions(sido_code)
        time.sleep(0.5)

        for sgu in sgus:
            sgu_name = (sgu.get("cortarName") or sgu.get("name") or "")
            sgu_code = (sgu.get("cortarNo")   or sgu.get("code") or "")

            if not any(t in sgu_name for t in TARGET_SGG):
                continue

            print(f"  ├ {sgu_name} ({sgu_code})")
            dongs = fetch_regions(sgu_code)
            time.sleep(0.5)

            for dong in dongs:
                dong_name = (dong.get("cortarName") or dong.get("name") or "")
                dong_code = (dong.get("cortarNo")   or dong.get("code") or "")
                lat, lon  = extract_coords(dong)

                if any(t in dong_name for t in TARGET_DONG):
                    print(f"  │   ✓ {dong_name} ({dong_code})  lat={lat} lon={lon}")
                    results.append((
                        f"{sgu_name} {dong_name}",
                        lat, lon, dong_code
                    ))

    # config.py 에 붙여넣을 스니펫 출력
    print("\n" + "=" * 60)
    print("아래를 config.py 의 REGIONS 에 붙여넣으세요")
    print("=" * 60)
    for name, lat, lon, code in results:
        lat_str = f"{float(lat):.4f}" if lat else "0.0000"
        lon_str = f"{float(lon):.4f}" if lon else "0.0000"
        print(f"""    {{
        "name"      : "{name}",
        "lat"       : {lat_str},
        "lon"       : {lon_str},
        "cortar_no" : "{code}",
    }},""")

    print(f"\n총 {len(results)}개 동 확인 완료")

    # JSON 파일로도 저장
    with open("regions_found.json", "w", encoding="utf-8") as f:
        json.dump(
            [{"name": n, "lat": la, "lon": lo, "cortar_no": c}
             for n, la, lo, c in results],
            f, ensure_ascii=False, indent=2
        )
    print("regions_found.json 저장 완료")


if __name__ == "__main__":
    main()
