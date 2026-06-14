# -*- coding: utf-8 -*-
"""시세 캐시만 갱신(스크리닝·대시보드 재생성 없이) — '거래일 단위 EOD'.

시세 기준 = '가장 최근에 마감·확정된 거래일'(EOD). 장중 실시간이 아니라 거래일 단위라,
같은 거래일에 여러 번 갱신해도 같은 값 → 이미 최신 거래일이 캐시에 있으면 받지 않는다.

- 한국(refresh_kr): `재무스크리너.bat`(launch.py) 실행 시 자동. KRX 최신 거래일을 먼저
  싸게 확인해, 캐시에 이미 있으면 스킵(빠른 실행). 새 거래일일 때만 fetch.
- 미국(refresh_us): 앱(app.py)의 '🔄 시세 새로고침' 버튼. 수천 종목이라 무거워 수동.

받은 값은 market_cache.merge_with_cache로 적재(실패·누락분은 직전 저장값 폴백). 시총은
시세만 갱신 시 비므로 market_cache.load_latest의 '시총 이월'이 직전 값을 유지한다.
"""
import market_cache


def _krx_latest_workday():
    """KRX 최신 거래일(YYYY-MM-DD). 작은 요청 1개 → 캐시 날짜와 비교해 스킵 판단용."""
    import json
    from datetime import datetime
    import requests
    h = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.krx.co.kr/"}
    ru = ("http://data.krx.co.kr/comm/bldAttendant/executeForResourceBundle.cmd"
          "?baseName=krx.mdc.i18n.component&key=B128.bld")
    mwd = json.loads(requests.get(ru, headers=h, timeout=10).text)["result"]["output"][0]["max_work_dt"]
    return datetime.strptime(mwd, "%Y%m%d").strftime("%Y-%m-%d")


def refresh_kr(market, force=False):
    """KR(KOSPI/KOSDAQ) 시세 캐시 갱신. force=False면 최신 거래일이 이미 캐시에 있으면 스킵.
    반환: (status, price_date). status = 'updated' | 'skipped' | 'failed'."""
    if not force:
        try:
            latest = _krx_latest_workday()
            cached = {v.get("asof") for v in market_cache.load_latest(market).values()}
            if latest in cached:
                return "skipped", latest
        except Exception:
            pass                       # 거래일 확인 실패 시 그냥 갱신 시도
    try:
        from run_kospi_quarterly import fetch_krx_marcap
        live, pdate = fetch_krx_marcap(market)
    except Exception:
        return "failed", None
    if not live:
        return "failed", None
    market_cache.merge_with_cache(market, live, pdate)
    return "updated", pdate


def refresh_us(tickers):
    """US 시세 캐시 갱신(앱 버튼용). 현재가·거래대금(20일평균)을 최근 거래일 EOD로 다시 받는다.
    시총(marcap)은 여기서 받지 않으며 load_latest의 '시총 이월'로 직전 값이 유지된다.
    반환: (status, price_date, n_live)."""
    try:
        from run_us_quarterly import fetch_market
        live, pdate = fetch_market(tickers)
    except Exception:
        return "failed", None, 0
    if not live:
        return "failed", None, 0
    _eff, info = market_cache.merge_with_cache("US", live, pdate)
    return "updated", pdate, info.get("live", 0)
