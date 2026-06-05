"""
db_supabase.py — Supabase DB 레이어 (db.py 대체)

db.py 와 동일한 함수 인터페이스를 유지하므로
main.py / processor.py 는 수정 없이 그대로 사용 가능.

설정 우선순위: 환경 변수 > config.py
 - SUPABASE_URL  : Supabase Project URL
 - SUPABASE_KEY  : service_role key (GitHub Actions 스크래퍼용)
                   ※ 대시보드(읽기 전용)는 anon key 사용
"""

import os
from typing import List, Optional

from supabase import create_client, Client

import config

# ── 클라이언트 캐시 ──────────────────────────────────────────────
_client: Optional[Client] = None

def _sb() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL") or getattr(config, "SUPABASE_URL", "")
        key = (os.environ.get("SUPABASE_SERVICE_KEY") or
               os.environ.get("SUPABASE_KEY") or
               getattr(config, "SUPABASE_KEY", ""))
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_KEY(or SUPABASE_SERVICE_KEY) 미설정.\n"
                "환경 변수 또는 config.py 를 확인하세요."
            )
        _client = create_client(url, key)
    return _client

# ── 유효 컬럼 목록 (raw dict 필터링용) ──────────────────────────
_COLS = {
    "article_no","region_name","region_code","real_estate_type","trade_type",
    "complex_name","building_name","deposit_manwon","rent_manwon",
    "area_supply_m2","area_excl_m2","floor_info","direction",
    "feature_desc","realtor_name","confirmed_date","detail_url","status",
}


def init_db():
    """연결 확인 (Supabase 테이블은 setup.sql 로 미리 생성)."""
    try:
        _sb().table("listings").select("article_no").limit(1).execute()
        print("✅ Supabase 연결 확인")
    except Exception as e:
        raise RuntimeError(
            f"Supabase 연결 실패: {e}\n"
            "1) SUPABASE_URL / SUPABASE_SERVICE_KEY 환경 변수 확인\n"
            "2) setup.sql 을 Supabase SQL Editor 에서 실행했는지 확인"
        )


# ── 조회 ─────────────────────────────────────────────────────────

def get_article(article_no: str) -> Optional[dict]:
    try:
        res = _sb().table("listings").select("*").eq("article_no", article_no).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_active_nos_by_region(region_name: str) -> List[str]:
    try:
        res = (
            _sb().table("listings")
            .select("article_no")
            .eq("status", "active")
            .eq("region_name", region_name)
            .execute()
        )
        return [r["article_no"] for r in res.data]
    except Exception:
        return []


# ── 적재 / 갱신 ───────────────────────────────────────────────────

def upsert_article(article: dict):
    """신규면 INSERT, 기존이면 last_seen_at·가격 UPDATE."""
    data = {k: v for k, v in article.items() if k in _COLS}
    # Supabase upsert: PK(article_no) 충돌 시 전체 컬럼 갱신
    _sb().table("listings").upsert(data).execute()


def insert_price_history(article_no: str, deposit: int, rent: int):
    _sb().table("price_history").insert({
        "article_no":     article_no,
        "deposit_manwon": deposit,
        "rent_manwon":    rent,
    }).execute()


def mark_gone(article_nos: List[str]):
    if not article_nos:
        return
    _sb().table("listings").update({"status": "gone"}).in_(
        "article_no", article_nos
    ).execute()


def log_run(region_name: str, collected: int,
            new_count: int, changed_count: int, gone_count: int):
    _sb().table("run_log").insert({
        "region_name":    region_name,
        "collected":      collected,
        "new_count":      new_count,
        "changed_count":  changed_count,
        "gone_count":     gone_count,
    }).execute()
