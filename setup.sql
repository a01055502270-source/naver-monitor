-- ============================================================
-- setup.sql — Supabase SQL Editor 에서 한 번만 실행
-- ============================================================

-- 매물 테이블
CREATE TABLE IF NOT EXISTS listings (
    article_no       TEXT PRIMARY KEY,
    region_name      TEXT NOT NULL,
    region_code      TEXT,
    real_estate_type TEXT,              -- APT / VL
    trade_type       TEXT,              -- B1(전세) / B2(월세)
    complex_name     TEXT,
    building_name    TEXT,
    deposit_manwon   INTEGER,           -- 보증금 (만원)
    rent_manwon      INTEGER DEFAULT 0, -- 월세 (만원, 전세=0)
    area_supply_m2   FLOAT,
    area_excl_m2     FLOAT,
    floor_info       TEXT,
    direction        TEXT,
    feature_desc     TEXT,
    realtor_name     TEXT,
    confirmed_date   TEXT,              -- 네이버 확인일자 YYYYMMDD
    detail_url       TEXT,
    first_seen_at    TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at     TIMESTAMPTZ DEFAULT NOW(),
    status           TEXT DEFAULT 'active'  -- active / gone
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_listings_region_status
    ON listings (region_name, status);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen
    ON listings (first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_status
    ON listings (status);

-- 가격 이력 테이블
CREATE TABLE IF NOT EXISTS price_history (
    id             BIGSERIAL PRIMARY KEY,
    article_no     TEXT REFERENCES listings(article_no) ON DELETE CASCADE,
    deposit_manwon INTEGER,
    rent_manwon    INTEGER,
    observed_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 실행 로그 테이블
CREATE TABLE IF NOT EXISTS run_log (
    id            BIGSERIAL PRIMARY KEY,
    run_at        TIMESTAMPTZ DEFAULT NOW(),
    region_name   TEXT,
    collected     INTEGER DEFAULT 0,
    new_count     INTEGER DEFAULT 0,
    changed_count INTEGER DEFAULT 0,
    gone_count    INTEGER DEFAULT 0
);

-- ── 유용한 뷰 (선택) ─────────────────────────────────────────
-- 신규 매물 (24시간 이내)
CREATE OR REPLACE VIEW v_new_listings AS
SELECT * FROM listings
WHERE status = 'active'
  AND first_seen_at >= NOW() - INTERVAL '24 hours'
ORDER BY first_seen_at DESC;

-- 지역별 현황
CREATE OR REPLACE VIEW v_region_stats AS
SELECT
    region_name,
    COUNT(*) FILTER (WHERE status='active') AS active_count,
    COUNT(*) FILTER (WHERE trade_type='B1' AND status='active') AS jeonse_count,
    COUNT(*) FILTER (WHERE trade_type='B2' AND status='active') AS wolse_count,
    COUNT(*) FILTER (WHERE first_seen_at >= NOW() - INTERVAL '24h' AND status='active') AS new_24h
FROM listings
GROUP BY region_name
ORDER BY region_name;

-- ============================================================
-- 실행 확인용 쿼리
-- ============================================================
-- SELECT * FROM v_region_stats;
-- SELECT article_no, region_name, complex_name, deposit_manwon, rent_manwon
--   FROM listings WHERE status='active' ORDER BY first_seen_at DESC LIMIT 20;
