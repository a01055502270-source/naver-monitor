
import requests, geohash2, json, sys
import config

REGIONS_TEST = config.REGIONS[:3]  # 처음 3개 지역만

output = []
for region in REGIONS_TEST:
    lat, lon = region["lat"], region["lon"]
    gh = geohash2.encode(lat, lon, precision=5)
    output.append(f"\n=== {region['name']} (geohash={gh}) ===")

    for svc in ["아파트", "빌라"]:
        r = requests.get("https://apis.zigbang.com/v2/items",
            params={"deposit_gteq":0,"domain":"zigbang","geohash":gh,
                    "needHasNoFiltered":"true","rent_gteq":0,
                    "sales_type_in":"전세|월세","service_type_eq":svc},
            timeout=20, headers={"Referer":"https://www.zigbang.com/"})
        items = r.json().get("items", [])
        ids   = [i["item_id"] for i in items[:50]]
        output.append(f"  {svc} ID수: {len(items)} (상세조회: {len(ids)}개)")

        if not ids:
            continue

        r2 = requests.post("https://apis.zigbang.com/v2/items/list",
            params={"domain":"zigbang","withCoalition":"true","item_ids":ids},
            timeout=20, headers={"Referer":"https://www.zigbang.com/"})
        details = r2.json().get("items", [])
        output.append(f"  상세 {len(details)}건")

        passed = 0
        for d in details:
            dep  = int(d.get("deposit") or 0)
            rent = int(d.get("rent")    or 0)
            area = float(d.get("size_m2") or 0)
            if dep <= config.DEPOSIT_MAX_MANWON and rent <= config.RENT_MAX_MANWON:
                if area <= 0 or (config.AREA_MIN_M2 <= area <= config.AREA_MAX_M2):
                    passed += 1

        # 가격대 분포
        deps = sorted([int(d.get("deposit",0)) for d in details if d.get("sales_type")=="전세"])
        rents= sorted([int(d.get("rent",0)) for d in details if d.get("sales_type")=="월세"])
        sizes= sorted([float(d.get("size_m2",0)) for d in details if d.get("size_m2")])

        if deps:
            output.append(f"  전세 보증금 범위: {min(deps):,}~{max(deps):,}만 ({len(deps)}건)")
        if rents:
            output.append(f"  월세 범위: {min(rents):,}~{max(rents):,}만 ({len(rents)}건)")
        if sizes:
            output.append(f"  면적 범위: {min(sizes):.0f}~{max(sizes):.0f}㎡")

        output.append(f"  ★ 필터 통과: {passed}/{len(details)}건 (보증금≤2억, 월세≤240만, 면적41-100㎡)")

        # 샘플 1건
        if details:
            s = details[0]
            output.append(f"  샘플: deposit={s.get('deposit')}, rent={s.get('rent')}, size_m2={s.get('size_m2')}, sales_type={s.get('sales_type')}, keys={list(s.keys())[:8]}")

print("\n".join(output))
