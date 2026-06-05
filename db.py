"""
db.py — SQLite 스키마 정의 및 CRUD
"""

import sqlite3
from contextlib import contextmanager
from typing import List, Optional

import config

# ── 스키마 ────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    article_no       TEXT PRIMARY KEY,
    region_name      TEXT NOT NULL,
    region_code      TEXT,
    real_estate_type TEXT,          -- APT / VL
    trade_type       TEXT,          -- B1(전세) / B2(월세)
    complex_name     TEXT,
    building_name    TEXT,
    deposit_manwon   INTEGER,       -- 보증금 (만원)
    rent_manwon      INTEGER,       -- 월세 (만원, 전세=0)
    area_supply_m2   REAL,          -- 공급면적
    area_excl_m2     REAL,          -- 전용면적
    floor_info       TEXT,          -- 예) "14/25"
    direction        TEXT,
    feature_desc     TEXT,
    realtor_name     TEXT,
    confirmed_date   TEXT,          -- 네이버 확인일자 YYYYMMDD
    detail_url       TEXT,
    first_seen_at    TEXT DEFAULT (datetime('now','localtime')),
    last_seen_at     TEXT DEFAULT (datetime('now','localtime')),
    status           TEXT DEFAULT 'active'   -- active / gone
);

CREATE TABLE IF NOT EXISTS price_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    article_no     TEXT NOT NULL,
    deposit_manwon INTEGER,
    rent_manwon    INTEGER,
    observed_at    TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (article_no) REFERENCES listings(article_no)
);

CREATE TABLE IF NOT EXISTS run_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at      TEXT DEFAULT (datetime('now','localtime')),
    region_name TEXT,
    collected   INTEGER DEFAULT 0,
    new_count   INTEGER DEFAULT 0,
    changed_count INTEGER DEFAULT 0,
    gone_count  INTEGER DEFAULT 0
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """테이블 초기화 (없으면 생성, 있으면 스킵)."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ── 조회 ─────────────────────────────────────────────────────

def get_article(article_no: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM listings WHERE article_no = ?", (article_no,)
        ).fetchone()
    return dict(row) if row else None


def get_active_nos_by_region(region_name: str) -> List[str]:
    """특정 지역의 현재 active 매물 articleNo 목록."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT article_no FROM listings WHERE status='active' AND region_name=?",
            (region_name,)
        ).fetchall()
    return [r["article_no"] for r in rows]


# ── 적재 / 갱신 ───────────────────────────────────────────────

def upsert_article(article: dict):
    """신규면 INSERT, 기존이면 last_seen_at·가격 UPDATE."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO listings
              (article_no, region_name, region_code, real_estate_type, trade_type,
               complex_name, building_name, deposit_manwon, rent_manwon,
               area_supply_m2, area_excl_m2, floor_info, direction,
               feature_desc, realtor_name, confirmed_date, detail_url, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active')
            ON CONFLICT(article_no) DO UPDATE SET
                last_seen_at   = datetime('now','localtime'),
                deposit_manwon = excluded.deposit_manwon,
                rent_manwon    = excluded.rent_manwon,
                status         = 'active'
        """, (
            article["article_no"],   article["region_name"],  article["region_code"],
            article["real_estate_type"],  article["trade_type"],
            article["complex_name"], article["building_name"],
            article["deposit_manwon"],    article["rent_manwon"],
            article["area_supply_m2"],    article["area_excl_m2"],
            article["floor_info"],   article["direction"],
            article["feature_desc"], article["realtor_name"],
            article["confirmed_date"],    article["detail_url"],
        ))


def insert_price_history(article_no: str, deposit: int, rent: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO price_history (article_no, deposit_manwon, rent_manwon) VALUES (?,?,?)",
            (article_no, deposit, rent)
        )


def mark_gone(article_nos: List[str]):
    """더 이상 보이지 않는 매물을 gone 처리."""
    if not article_nos:
        return
    with get_conn() as conn:
        conn.executemany(
            "UPDATE listings SET status='gone', last_seen_at=datetime('now','localtime') "
            "WHERE article_no=?",
            [(no,) for no in article_nos]
        )


def log_run(region_name: str, collected: int,
            new_count: int, changed_count: int, gone_count: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO run_log (region_name,collected,new_count,changed_count,gone_count) "
            "VALUES (?,?,?,?,?)",
            (region_name, collected, new_count, changed_count, gone_count)
        )
