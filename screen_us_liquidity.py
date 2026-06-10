#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미국 거래소 상장(S&P500 밖) 유동성 1차 필터 — EDGAR 수집 전 대상 축소.

순서 역전 전략(사용자 설계): 7천 개 재무를 EDGAR에서 다 받아놓고 거르는 대신, 가장 싸고
가장 많이 떨어뜨리는 ①유동성(거래대금≥$10M)을 먼저 적용해 EDGAR 수집 대상을 줄인다.
재무가 아닌 '주가×거래량'만 필요하므로 yfinance bulk download로 수천 개를 빠르게 받는다.

입력 : dart-audit-extractor/data/us_all_index.json (build_us_all_universe.py 산출, CIK·티커)
거래대금 = 최근 10거래일 평균 달러거래대금(종가×거래량) — run_us_quarterly와 동일 산식.
통과 = 거래대금 ≥ $10M (MIN_TRADING_USD).
출력 : data/us_liquid_index.json (EDGAR 수집 대상 = 유동성 통과 명단, 거래대금 내림차순)
       + 콘솔 요약 + us_유동성후보_<날짜>.csv (검토용)

사용: py screen_us_liquidity.py [--chunk 400]
"""
import sys, io, json, csv, time, argparse
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_DIR = Path("D:/Agent_Project/dart-audit-extractor/data")
US_ALL = DATA_DIR / "us_all_index.json"
US_LIQUID = DATA_DIR / "us_liquid_index.json"
# 수집 전 선필터값. 일부러 최종 게이트(engine.US_CRITERIA.min_trading=$30M)보다 느슨하게 둔다
# ($10M~$30M 종목도 일단 수집해 두고 최종 스크린에서 $30M로 거른다). 이 값은 ≤ $30M이어야 한다.
MIN_TRADING_USD = 10_000_000


def _download_chunk(part, attempts=3):
    """yfinance bulk download를 지수 백오프(2·4초)로 재시도. 끝내 실패하면 None."""
    import yfinance as yf
    for a in range(attempts):
        try:
            return yf.download(part, period="1mo", interval="1d", group_by="ticker",
                               auto_adjust=False, threads=True, progress=False)
        except Exception as e:
            if a == attempts - 1:
                print(f"  [!] 청크 {len(part)}종목 {attempts}회 다운로드 실패: {e}")
                return None
            time.sleep(2 ** (a + 1))


def dollar_volume(tickers, chunk):
    """yfinance bulk download → {ticker: 최근10거래일 평균 달러거래대금(유효 5일 미만이면 제외)}.
    실패 종목은 누락하되 끝에 건수 보고(다음 단계 collect_us 입력이라 누락 추적이 중요)."""
    out, failed = {}, []
    n = len(tickers)
    for i in range(0, n, chunk):
        part = tickers[i:i + chunk]
        df = _download_chunk(part)
        if df is None:
            failed.extend(part); continue
        for tk in part:
            try:
                sub = df[tk] if len(part) > 1 else df
                dv = (sub["Close"] * sub["Volume"]).dropna().tail(10)
                if len(dv) >= 5:                 # 유효 거래일 5일 이상만 신뢰
                    v = float(dv.mean())
                    if v == v:                   # NaN 아님
                        out[tk] = v
                    else:
                        failed.append(tk)
                else:
                    failed.append(tk)
            except Exception:
                failed.append(tk); continue
        print(f"  진행 {min(i+chunk, n)}/{n} · 시세확보 {len(out)}", flush=True)
        time.sleep(1.0)                          # yfinance 과부하 완화
    if failed:
        print(f"  [!] 시세 미확보/거래일부족 {len(failed)}종목 — 유동성 미확인 제외")
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=400)
    args = ap.parse_args(argv[1:])

    uni = json.loads(US_ALL.read_text(encoding="utf-8"))
    print(f"대상(S&P500 밖 미국 거래소 상장): {len(uni)}개사")
    by_ticker = {c["ticker"]: c for c in uni}
    tickers = list(by_ticker.keys())

    print(f"yfinance 거래대금 조회(청크 {args.chunk})...")
    dv = dollar_volume(tickers, args.chunk)
    print(f"시세 확보: {len(dv)}/{len(tickers)}종목 (나머지는 yfinance 무자료 → 유동성 미확인 제외)")

    passed = []
    for tk, v in dv.items():
        if v >= MIN_TRADING_USD:
            c = dict(by_ticker[tk]); c["amount"] = v
            passed.append(c)
    passed.sort(key=lambda x: -x["amount"])

    # EDGAR 수집 대상 명단(JSON) — collect_us.py --index 가 읽는 형식(cik·ticker·name)
    US_LIQUID.write_text(json.dumps(passed, ensure_ascii=False, indent=2), encoding="utf-8")

    # 검토용 CSV
    today = datetime.now().strftime("%Y%m%d")
    Path("results").mkdir(exist_ok=True)
    csv_path = Path(f"results/us_유동성후보_{today}.csv")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["rank", "ticker", "name", "exchange", "거래대금($M)", "cik"])
        for i, c in enumerate(passed, 1):
            w.writerow([i, c["ticker"], c["name"], c.get("exchange", ""),
                        round(c["amount"] / 1e6, 1), c["cik"]])

    print(f"\n유동성 통과(거래대금≥${MIN_TRADING_USD/1e6:.0f}M): {len(passed)}개사 "
          f"→ {US_LIQUID.name} (EDGAR 수집 대상)")
    print(f"검토용: {csv_path.name}")
    print("\n상위 15:")
    for c in passed[:15]:
        print(f"  {c['ticker']:6s} {c['name'][:30]:30s} ${c['amount']/1e6:,.0f}M  ({c.get('exchange','')})")
    print("…")
    print("통과 하한 근처 5:")
    for c in passed[-5:]:
        print(f"  {c['ticker']:6s} {c['name'][:30]:30s} ${c['amount']/1e6:,.1f}M  ({c.get('exchange','')})")


if __name__ == "__main__":
    main(sys.argv)
