# -*- coding: utf-8 -*-
"""시세(거래대금·현재가·시총·등락률) 로컬 캐시.

DART 재무는 screener.db에 영속 저장되지만, 주가·거래대금은 매 실행 시 FDR/yfinance로
새로 받아 메모리에서 쓰고 버렸다. 그래서 소스가 일시 장애(예: FDR StockListing 404)면
거래대금이 통째로 비어 1단계(유동성)에서 전원 탈락한다.

이 모듈은 시세를 날짜별로 SQLite(market_cache.db)에 누적 저장하고, 라이브 조회가 실패하거나
특정 종목이 누락되면 그 종목의 '가장 최근 저장값'으로 폴백한다. 거래대금은 일별 변동이 크지
않다는 전제(사용자 판단) — 폴백값은 as-of 날짜를 함께 노출해 정직하게 표시한다.

KR(FDR)·US(yfinance) 공용: 둘 다 {ticker: {close, amount, marcap, chg}} 형태라 그대로 받는다.
market 인자로 'KOSPI'/'KOSDAQ'/'US'를 분리 저장한다.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path(__file__).with_name("market_cache.db")


def _conn():
    c = sqlite3.connect(str(DB))
    c.execute("""CREATE TABLE IF NOT EXISTS market_cache(
        market TEXT, ticker TEXT, date TEXT,
        close REAL, amount REAL, marcap REAL, chg REAL,
        PRIMARY KEY(market, ticker, date))""")
    return c


def save_snapshot(market, date, data):
    """라이브 조회 성공분을 (market,ticker,date)로 upsert. date 없으면 저장 안 함."""
    if not date or not data:
        return 0
    n = 0
    with _conn() as c:
        for tk, v in data.items():
            if not v:
                continue
            c.execute("INSERT OR REPLACE INTO market_cache VALUES(?,?,?,?,?,?,?)",
                      (market, tk, date, v.get("close"), v.get("amount"),
                       v.get("marcap"), v.get("chg")))
            n += 1
    return n


def load_latest(market):
    """종목별 가장 최근 저장 스냅샷 {ticker: {close,amount,marcap,chg, asof}}."""
    out = {}
    with _conn() as c:
        rows = c.execute(
            "SELECT ticker, date, close, amount, marcap, chg FROM market_cache "
            "WHERE market=? ORDER BY date", (market,)).fetchall()
    for tk, date, close, amount, marcap, chg in rows:   # date 오름차순 → 뒤(최신)가 덮음
        out[tk] = {"close": close, "amount": amount, "marcap": marcap,
                   "chg": chg, "asof": date}
    return out


def merge_with_cache(market, live, price_date):
    """라이브 조회 결과를 캐시와 병합.
    - 라이브 성공분은 오늘(price_date)로 저장.
    - 라이브에 없거나 거래대금(amount)이 빈 종목은 최근 캐시값으로 폴백(asof 표시).
    반환: (effective_map, info). info={'live':n, 'cache':n, 'asof_dates':set, 'saved':n}."""
    live = live or {}
    saved = save_snapshot(market, price_date, live)
    cache = load_latest(market)
    eff, n_live, n_cache, asof_dates = {}, 0, 0, set()
    for tk in set(live) | set(cache):
        lv = live.get(tk)
        if lv and lv.get("amount") is not None:
            eff[tk] = dict(lv); eff[tk]["asof"] = price_date; n_live += 1
        elif tk in cache:
            eff[tk] = dict(cache[tk]); n_cache += 1
            if cache[tk].get("asof"):
                asof_dates.add(cache[tk]["asof"])
        elif lv:                       # 라이브에 있으나 amount 없음 + 캐시도 없음
            eff[tk] = dict(lv); eff[tk]["asof"] = price_date
    return eff, {"live": n_live, "cache": n_cache, "asof_dates": asof_dates, "saved": saved}
