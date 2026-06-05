"""
notifier.py — 텔레그램 알림

Bot API 를 직접 호출해 외부 라이브러리 의존성을 최소화한다.
설정이 안 된 경우(토큰 = 플레이스홀더) 콘솔 로그만 출력하고 전송은 스킵한다.
"""

import logging
from typing import List

import requests

import config

logger = logging.getLogger(__name__)

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"

_NOT_CONFIGURED = (
    config.TELEGRAM_BOT_TOKEN in ("", "YOUR_BOT_TOKEN") or
    config.TELEGRAM_CHAT_ID   in ("", "YOUR_CHAT_ID")
)


def _send(text: str):
    if _NOT_CONFIGURED:
        logger.info(f"[알림 미설정 — 콘솔 출력]\n{text}\n")
        return
    url     = _TELEGRAM_URL.format(token=config.TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id":                config.TELEGRAM_CHAT_ID,
        "text":                   text,
        "parse_mode":             "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"텔레그램 전송 실패: {e}")


# ── 가격 포맷 ─────────────────────────────────────────────────

def _fmt_price(deposit: int, rent: int) -> str:
    """45000만원 → '4억 5,000', 월세가 있으면 '월세 X억 Y,000 / Z만'."""
    def _dep(d: int) -> str:
        if d == 0:
            return "0"
        awk = d // 10_000
        man = d % 10_000
        if awk > 0:
            return f"{awk}억" + (f" {man:,}" if man else "")
        return f"{d:,}만"

    dep_str = _dep(deposit)
    if rent > 0:
        return f"월세 {dep_str} / {rent:,}만"
    return f"전세 {dep_str}"


def _area_str(art: dict) -> str:
    excl = art.get("area_excl_m2", 0)
    sup  = art.get("area_supply_m2", 0)
    if excl > 0 and sup > 0:
        return f"공급 {sup:.0f} / 전용 {excl:.0f}㎡"
    if excl > 0:
        return f"전용 {excl:.0f}㎡"
    return ""


# ── 신규 매물 알림 ────────────────────────────────────────────

def notify_new(article: dict):
    trade = "전세" if article["rent_manwon"] == 0 else "월세"
    price = _fmt_price(article["deposit_manwon"], article["rent_manwon"])
    area  = _area_str(article)
    floor = article.get("floor_info", "")
    feat  = article.get("feature_desc", "")[:40]
    date  = article.get("confirmed_date", "")
    if len(date) == 8:  # YYYYMMDD → YY.MM.DD
        date = f"{date[2:4]}.{date[4:6]}.{date[6:8]}"

    text = (
        f"🆕 <b>신규 {trade}</b> | {article['region_name']}\n"
        f"<b>{article['complex_name']}</b>"
        + (f" {article['building_name']}" if article.get("building_name") else "")
        + f"\n{price}  {area}\n"
        f"{floor}층  {article.get('direction','')}\n"
        + (f"<i>{feat}</i>\n" if feat else "")
        + f"중개: {article.get('realtor_name','')}  확인: {date}\n"
        f"🔗 <a href=\"{article['detail_url']}\">매물 보기</a>"
    )
    _send(text)


# ── 가격 변동 알림 ────────────────────────────────────────────

def notify_changed(article: dict):
    prev = _fmt_price(article["prev_deposit"], article["prev_rent"])
    curr = _fmt_price(article["deposit_manwon"],  article["rent_manwon"])
    arrow = "⬇️" if article["deposit_manwon"] < article["prev_deposit"] else "⬆️"

    text = (
        f"{arrow} <b>가격 변동</b> | {article['region_name']}\n"
        f"<b>{article['complex_name']}</b>  {article.get('floor_info','')}층\n"
        f"{prev}  →  <b>{curr}</b>\n"
        f"🔗 <a href=\"{article['detail_url']}\">매물 보기</a>"
    )
    _send(text)


# ── 스캔 요약 알림 ────────────────────────────────────────────

def notify_summary(stats: List[dict]):
    """신규/변동이 1건 이상인 경우에만 요약 전송."""
    active_stats = [s for s in stats if s["new"] + s["changed"] > 0]
    if not active_stats:
        return

    lines = ["📊 <b>스캔 완료</b>"]
    for s in active_stats:
        lines.append(f"  • {s['name']}: 신규 {s['new']}건 / 가격변동 {s['changed']}건")

    _send("\n".join(lines))
