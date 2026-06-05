"""
main.py — 매물 스캔 진입점 (업데이트: Supabase 자동 감지)

실행:
    python main.py              # 정상 실행
    python main.py --dry-run    # 수집·diff 만, DB/알림 미반영
    python main.py --region "미사"  # 특정 지역만
"""

import argparse
import logging
import os
import sys

import config

# ── DB 레이어 자동 감지 ────────────────────────────────────────
# SUPABASE_URL 환경 변수가 있으면 Supabase 사용, 아니면 로컬 SQLite
if os.environ.get("SUPABASE_URL") or getattr(config, "SUPABASE_URL", ""):
    import db_supabase as db
    _db_mode = "Supabase ☁"
else:
    import db
    _db_mode = "SQLite (로컬)"

from collector  import collect_region
from processor  import normalize_article, passes_filter, compute_diff
from notifier   import notify_new, notify_changed, notify_summary

# ── 로깅 설정 ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_cycle(dry_run: bool = False, target_region: str = None):
    logger.info(f"▶ DB 모드: {_db_mode}")
    db.init_db()

    regions = config.REGIONS
    if target_region:
        regions = [r for r in regions if target_region in r["name"]]
        if not regions:
            logger.error(f"'{target_region}' 와 일치하는 지역 없음"); return

    stats = []

    for region in regions:
        logger.info(f"\n{'='*50}")
        logger.info(f"▶ {region['name']} 스캔 시작")

        # ① 수집
        raw_list = collect_region(region)

        # ② 정규화
        articles = []
        for raw in raw_list:
            raw["_region_name"] = region["name"]
            raw["_cortar_no"]   = region.get("cortar_no", "")
            art = normalize_article(raw)
            if art:
                articles.append(art)

        # ③ 필터
        filtered = [a for a in articles if passes_filter(a)]
        logger.info(f"  정규화 {len(articles)}건 → 필터 통과 {len(filtered)}건")

        if not filtered and not articles:
            logger.warning("  ⚠ 매물 0건. API 응답 구조를 확인하세요 (collector.py _parse_body)")

        # ④ diff
        new_arts, changed_arts, gone_ids = compute_diff(region["name"], filtered)
        logger.info(f"  신규 {len(new_arts)}건 / 변동 {len(changed_arts)}건 / 소멸 {len(gone_ids)}건")

        if not dry_run:
            # ⑤ DB 적재
            for art in filtered:
                db.upsert_article(art)
            for art in changed_arts:
                db.insert_price_history(art["article_no"], art["deposit_manwon"], art["rent_manwon"])
            if gone_ids:
                db.mark_gone(gone_ids)
            # ⑥ 알림
            for art in new_arts:
                notify_new(art)
            for art in changed_arts:
                notify_changed(art)
            db.log_run(region["name"], len(raw_list), len(new_arts), len(changed_arts), len(gone_ids))
        else:
            logger.info("  [dry-run] DB·알림 스킵")
            for art in new_arts[:3]:
                logger.info(f"  PREVIEW | {art['complex_name']} | 보증금 {art['deposit_manwon']:,}만 | 전용 {art['area_excl_m2']}㎡ {art['floor_info']}층")

        stats.append({"name": region["name"], "new": len(new_arts), "changed": len(changed_arts)})

    if not dry_run:
        notify_summary(stats)

    total_new = sum(s["new"] for s in stats)
    total_chg = sum(s["changed"] for s in stats)
    logger.info(f"\n✅ 스캔 완료 — 신규 {total_new}건 / 변동 {total_chg}건")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="네이버 부동산 전·월세 모니터")
    parser.add_argument("--dry-run", action="store_true", help="수집·diff 만, DB/알림 미반영")
    parser.add_argument("--region",  type=str, default=None, help="특정 지역명 부분 일치 필터")
    args = parser.parse_args()
    run_cycle(dry_run=args.dry_run, target_region=args.region)
