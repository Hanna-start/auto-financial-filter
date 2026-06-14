#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미국(S&P500) 분기 스크리너 — 실제 SEC EDGAR 분기 재무(financials_q) 기반.

코스피판(run_kospi_quarterly.py)의 검증된 재무 엔진(load_company·compute·add_valuation,
누적차감·TTM·YoY)을 그대로 재사용한다. 미국 고유 차이는 둘뿐:
  - 시장 데이터(현재가·거래대금·시총·등락률) = FinanceDataReader(한국) 대신 **yfinance**
  - 표시 통화 = 원/억/조 대신 **달러($M/$B)**
재무 기준은 한국과 글자 그대로 동일. 거래대금만 달러 등가 기준 사용.

데이터:
  - 재무 = screener.db financials_q (collect_us.py가 CIK 키로 적재, fs_div=CFS)
  - 대상 명단·회사명·티커 = dart-audit-extractor/data/us_index.json (build_us_universe.py)

산출: 콘솔 리포트 + 미국_분기_결과_*.xlsx + dashboard_us.html
사용: py run_us_quarterly.py            # financials_q에 적재된 S&P500만 스크리닝
"""
import sys, io, sqlite3, json, html
from datetime import datetime
from pathlib import Path

# 공유 엔진 + 미국 기준 프로파일(US_CRITERIA). 기준 이원화는 engine.py / 기준_미국.md.
from engine import (load_company, compute, add_valuation, screen, debt_ratio_display,
                    MIN_OP_MARGIN, MAX_DEBT, MIN_GROWTH_YOY, DB, US_CRITERIA, TRADING_AVG_DAYS)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

US_INDEX = "D:/Agent_Project/dart-audit-extractor/data/us_index.json"

# 표시·이력창 별칭(단일 출처=engine.US_CRITERIA). 게이트는 screen(m, trading, US_CRITERIA).
# 거래대금 $10M(≈100억원), 이력창 최근 20분기(=5년): EDGAR 17년+ 이력에서 '이익피크·원가율
# 개선'을 한국과 동일 의미로 비교하려 최근 창으로 절단(2008년 대비 같은 무의미 비교 방지).
MIN_TRADING_USD = US_CRITERIA.min_trading
RECENT_QUARTERS = US_CRITERIA.recent_quarters


def trim_recent(d, n_q=RECENT_QUARTERS):
    """재무 history를 최근 n_q분기로 제한(이익피크·원가율개선을 한국과 같은 최근 창에서 판단).
    재무상태표(bs)는 최신 시점이라 그대로 둠."""
    if not d or len(d["qkeys"]) <= n_q:
        return d
    qk = d["qkeys"][-n_q:]
    quarters = {k: d["quarters"][k] for k in qk}
    return {**d, "quarters": quarters, "qkeys": qk}


def _download_chunk(part, period="2mo", attempts=3):
    """yfinance bulk download를 지수 백오프(2·4초)로 재시도. 끝내 실패하면 None.
    period: 거래대금 N일 평균 윈도우를 덮을 만큼 충분히 길게(기본 2개월≈42거래일). auto_adjust=False=원주가."""
    import yfinance as yf, time
    for a in range(attempts):
        try:
            return yf.download(part, period=period, interval="1d", group_by="ticker",
                               auto_adjust=False, threads=True, progress=False)
        except Exception as e:
            if a == attempts - 1:
                print(f"  [!] 청크 {len(part)}종목 {attempts}회 다운로드 실패: {e}")
                return None
            time.sleep(2 ** (a + 1))


def fetch_market(tickers, chunk=400, avg_days=TRADING_AVG_DAYS):
    """yfinance bulk download → {ticker:{close, amount(달러거래대금), marcap=None, chg}} + 주가기준일.
    수천 종목용(종목별 1콜 루프는 느리고 불안정 → 청크 bulk).
      - 현재가·등락률 = 마지막 일봉(EOD, 평균 아님).
      - 거래대금 = 최근 avg_days거래일 평균 달러거래대금(종가×거래량; 유효일이 절반 미만이면 None).
    시총(marcap)은 download에 없어 fetch_marcaps로 최종/재무통과 종목만 별도 조회.
    실패 종목은 누락하되 끝에 건수 보고."""
    import time
    period = f"{max(2, avg_days // 21 + 2)}mo"        # avg_days 거래일을 덮을 다운로드 기간
    out, price_date, failed = {}, None, []
    n = len(tickers)
    for i in range(0, n, chunk):
        part = tickers[i:i + chunk]
        df = _download_chunk(part, period)
        if df is None:
            failed.extend(part); continue
        if len(df.index):
            price_date = df.index[-1].strftime("%Y-%m-%d")
        for tk in part:
            try:
                sub = df[tk] if len(part) > 1 else df
                cl = sub["Close"].dropna()
                if not len(cl):
                    failed.append(tk); continue
                close = float(cl.iloc[-1])
                prev = float(cl.iloc[-2]) if len(cl) > 1 else None
                chg = (close / prev - 1) * 100 if prev else None
                dv = (sub["Close"] * sub["Volume"]).dropna().tail(avg_days)
                amount = float(dv.mean()) if len(dv) >= max(5, avg_days // 2) else None
                out[tk] = {"close": close, "amount": amount, "marcap": None, "chg": chg}
            except Exception:
                failed.append(tk); continue
        if n > chunk:
            print(f"  시장데이터 {min(i+chunk, n)}/{n} · 확보 {len(out)}", flush=True)
        time.sleep(1.0)
    if failed:
        print(f"  [!] 시세 미확보 {len(failed)}종목(예: {', '.join(failed[:8])}"
              + ("…" if len(failed) > 8 else "") + ") — 캐시 폴백 대상")
    return out, price_date


def fetch_marcaps(tickers, closes=None):
    """통과 종목 소수의 시총만 per-ticker로 — 밸류에이션(PER/PBR) 표시용.
    fast_info.market_cap이 자주 결측/실패해 PER·PBR이 '—'로 비던 문제를 보강:
      ① market_cap 우선 → ② 결측이면 현재가×발행주식수(shares) 폴백 → ③ 최대 3회 재시도.
    closes={ticker: 현재가}: 이미 받은 시세를 폴백 계산(현재가×주식수)에 재사용."""
    import time
    import yfinance as yf
    out, closes = {}, (closes or {})
    for tk in tickers:
        mc = None
        for a in range(3):
            try:
                fi = yf.Ticker(tk).fast_info
                v = fi.market_cap
                if v is not None and v == v and v > 0:
                    mc = float(v); break
                sh = fi.shares                              # 발행주식수 폴백
                px = closes.get(tk) or fi.last_price
                if sh and px and sh == sh and px == px:
                    mc = float(sh) * float(px); break
            except Exception:
                pass
            if a < 2:
                time.sleep(1.5 * (a + 1))
        if mc is not None:
            out[tk] = mc
    return out


def main(index_paths=None, label="S&P500", title="미국(S&P500) 분기 스크리너 결과",
         dash="dashboards/dashboard_us.html", xlsx_prefix="미국_분기_결과"):
    """index_paths: 대상 명단 json 경로 리스트(여러 개면 CIK 합집합). 기본=S&P500(us_index)."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    have = {r[0] for r in conn.execute("SELECT DISTINCT corp_code FROM financials_q")}
    uni, seen = [], set()
    for p in (index_paths or [US_INDEX]):
        for c in json.loads(Path(p).read_text(encoding="utf-8")):
            if c["cik"] not in seen:            # CIK 합집합(명단 간 중복 제거)
                seen.add(c["cik"]); uni.append(c)
    # cik가 financials_q.corp_code 자리 → 재무 적재된 종목만 대상
    corps = [c for c in uni if c["cik"] in have]
    print(f"분기 재무 보유 {label}: {len(corps)}개사 (전체 명단 {len(uni)})")

    print("yfinance 시장데이터(현재가·거래대금) 조회 중...")
    mkt, price_date = fetch_market([c["ticker"] for c in corps])
    print(f"  시장데이터 {len(mkt)}종목" + (f" · 주가 기준일 {price_date}" if price_date else ""))

    # 시세 캐시: 라이브 성공분 저장 + 실패/누락분은 직전 저장값으로 폴백
    import market_cache
    mkt, cinfo = market_cache.merge_with_cache("US", mkt, price_date)
    if not price_date and cinfo["asof_dates"]:
        price_date = max(cinfo["asof_dates"])
    if cinfo["cache"]:
        print(f"  └ 거래대금 폴백: 캐시 {cinfo['cache']}종목"
              + (f"(as-of {price_date})" if price_date else "")
              + f" · 라이브 {cinfo['live']}종목")

    results = []
    for c in corps:
        cik, name, tk = c["cik"], c.get("name", ""), c["ticker"]
        d = trim_recent(load_company(conn, cik))
        m = compute(d) if d else None
        mi = mkt.get(tk, {})
        st = screen(m, mi.get("amount"), US_CRITERIA)
        final = st["liquidity"] and st["financial"] and st["quality"]
        if final: stage = 3
        elif st["liquidity"] and st["financial"]: stage = 2
        elif st["liquidity"]: stage = 1
        else: stage = 0
        results.append({"corp": cik, "name": name, "code": tk, "sector": c.get("sector", ""),
                        "m": m, "fdr": mi, "st": st, "stage": stage, "final": final})
    conn.close()

    # 시총(밸류에이션 PER/PBR)은 재무건전 통과(stage≥2)만 per-ticker 조회 — 수천 개 회피
    pass_tk = [r["code"] for r in results if r["stage"] >= 2]
    closes = {r["code"]: (r["fdr"] or {}).get("close") for r in results if r["stage"] >= 2}
    marcaps = fetch_marcaps(pass_tk, closes)
    market_cache.update_marcap("US", marcaps)   # 캐시에도 반영 → app.py(캐시 읽음)도 미국 시총·PER/PBR 표시
    for r in results:
        if r["fdr"] is not None:
            r["fdr"]["marcap"] = marcaps.get(r["code"])
        add_valuation(r["m"], marcaps.get(r["code"]))

    n = len(results)
    n_liq = sum(1 for r in results if r["st"]["liquidity"])
    n_fh = sum(1 for r in results if r["st"]["liquidity"] and r["st"]["financial"])
    n_qg = sum(1 for r in results if r["final"])
    finals = [r for r in results if r["final"]]

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(f"기준(미국): 거래대금≥${MIN_TRADING_USD/1e6:.0f}M · 부채비율<{MAX_DEBT:.0f}% · "
          f"매출성장(YoY)≥{MIN_GROWTH_YOY:.0f}% · TTM영업이익률≥{MIN_OP_MARGIN:.0f}% · "
          f"이익피크({US_CRITERIA.min_peak_quarters}분기↑) · TTM영업현금>0 · 자본>0 or(자본<0&이익잉여금>0)")
    print(f"\n단계별 통과:")
    print(f"  대상           : {n}")
    print(f"  ① 유동성       : {n_liq}  ({n_liq/n*100:.0f}%)" if n else "  ① 유동성       : 0")
    print(f"  ② 재무건전성   : {n_fh}")
    print(f"  ③ 품질성장(최종): {n_qg}")
    print(f"\n최종 후보 {len(finals)}개:")
    finals.sort(key=lambda r: -(r["fdr"].get("marcap") or 0))
    for r in finals:
        m = r["m"]; f = r["fdr"]
        cl = f.get("close"); ch = f.get("chg")
        px = (f"${cl:,.2f}" + (f"({ch:+.1f}%)" if ch is not None else "")) if cl else "주가—"
        per = f"PER {m['per']:.1f}" if m.get("per") else "PER —"
        drx = debt_ratio_display(m)
        drs = f"{drx:.0f}%" if drx is not None else "—"
        print(f"  - {r['name']}({r['code']})  {px} · 영업이익률(TTM) {m['op_margin']:.1f}% · "
              f"매출성장(YoY) {m['rev_yoy']:.1f}% · 부채비율 {drs} · {per}")

    Path("results").mkdir(exist_ok=True); Path("dashboards").mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx = f"results/{xlsx_prefix}_{ts}.xlsx"
    save_xlsx(results, xlsx, price_date=price_date, sheet=title)
    print(f"\n📁 결과 저장: {xlsx}")
    Path(dash).write_text(
        render(results, n, n_liq, n_fh, n_qg, finals, price_date=price_date, title=title), encoding="utf-8")
    print(f"📊 대시보드: {dash}")
    return results


def save_xlsx(results, path, price_date=None, sheet="미국 분기 스크리닝"):
    try:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = sheet[:31]
        pcol = f"현재가($,{price_date})" if price_date else "현재가($)"
        ws.append(["티커", "회사명", "섹터", "결과단계", pcol, "등락률(%)", "재무기준일",
                   "거래대금($M)", "시총($B)",
                   "TTM매출($M)", "TTM영업이익($M)", "TTM순이익($M)", "영업이익률TTM(%)", "매출성장YoY(%)",
                   "부채비율(%)", "PER", "PBR", "PSR", "시총/TTM영업이익",
                   "이익피크", "원가율개선", "TTM영업현금>0"])
        order = sorted(results, key=lambda r: (-r["stage"], -(r["fdr"].get("marcap") or 0)))
        lbl = {3: "최종후보", 2: "탈락:품질성장", 1: "탈락:재무건전성", 0: "탈락:유동성"}
        for r in order:
            m = r["m"] or {}; f = r["fdr"]
            dr = debt_ratio_display(m)
            ws.append([
                r["code"], r["name"], r.get("sector", ""), lbl[r["stage"]],
                round(f.get("close"), 2) if f.get("close") else None,
                round(f.get("chg"), 2) if f.get("chg") is not None else None,
                m.get("bs_asof", ""),
                round(f.get("amount", 0)/1e6, 1) if f.get("amount") else None,
                round(f.get("marcap", 0)/1e9, 1) if f.get("marcap") else None,
                round(m.get("ttm_revenue", 0)/1e6, 0) if m.get("ttm_revenue") else None,
                round(m.get("ttm_op", 0)/1e6, 0) if m.get("ttm_op") else None,
                round(m.get("ttm_net", 0)/1e6, 0) if m.get("ttm_net") else None,
                round(m["op_margin"], 1) if m.get("op_margin") is not None else None,
                round(m["rev_yoy"], 1) if m.get("rev_yoy") is not None else None,
                round(dr, 0) if dr is not None else None,
                round(m["per"], 1) if m.get("per") is not None else None,
                round(m["pbr"], 2) if m.get("pbr") is not None else None,
                round(m["psr"], 2) if m.get("psr") is not None else None,
                round(m["p_op"], 1) if m.get("p_op") is not None else None,
                "O" if m.get("is_peak") else "X",
                "O" if m.get("cogs_improving") else "X",
                "O" if m.get("ttm_ocf_ok") else "X",
            ])
        wb.save(path)
    except Exception as e:
        print(f"[!] xlsx 저장 실패: {e}")


def render(results, n, n_liq, n_fh, n_qg, finals, price_date=None,
           title="미국(S&P500) 분기 스크리너 결과"):
    e = html.escape
    def usd(v):
        if v is None: return "—"
        a = abs(v)
        return f"${v/1e9:.1f}B" if a >= 1e9 else (f"${v/1e6:.0f}M" if a >= 1e6 else f"${v:,.0f}")
    def pct(v): return "—" if v is None else f"{v:.1f}%"
    def x1(v): return "—" if v is None else f"{v:.1f}배"
    def x2(v): return "—" if v is None else f"{v:.2f}배"
    def prc(v): return "—" if v is None else f"${v:,.2f}"
    def chg(v):
        if v is None: return ""
        c = "var(--ok)" if v > 0 else ("var(--no)" if v < 0 else "var(--mut)")
        return f'<span style="color:{c};font-size:12px"> {v:+.1f}%</span>'

    funnel = [("전체 대상", n), ("① 유동성", n_liq), ("② 재무건전성", n_fh), ("③ 품질성장(최종)", n_qg)]
    fhtml = ""
    for i, (lb, c) in enumerate(funnel):
        w = c/funnel[0][1]*100 if funnel[0][1] else 0
        fin = i == len(funnel)-1
        fhtml += f'<div class="fstep{" fin" if fin else ""}"><div class="fbar" style="width:{max(w,5):.1f}%"></div><div class="fl">{e(lb)}</div><div class="fc">{c}</div></div>'

    cards = ""
    for r in sorted(finals, key=lambda r:-(r["fdr"].get("marcap") or 0)):
        m=r["m"]; f=r["fdr"]
        cards += f'<div class="card"><div class="cn">{e(r["name"])}</div><div class="cm">{e(r["code"])} · {e(r.get("sector",""))} · 시총 {usd(f.get("marcap"))}</div><div class="cg"><div><span>현재가</span><b>{prc(f.get("close"))}{chg(f.get("chg"))}</b></div><div><span>영업이익률(TTM)</span><b>{pct(m["op_margin"])}</b></div><div><span>매출성장(YoY)</span><b>{pct(m["rev_yoy"])}</b></div><div><span>부채비율</span><b>{pct(debt_ratio_display(m))}</b></div><div><span>거래대금</span><b>{usd(f.get("amount"))}</b></div><div><span>PER</span><b>{x1(m.get("per"))}</b></div><div><span>PBR</span><b>{x2(m.get("pbr"))}</b></div><div><span>PSR</span><b>{x2(m.get("psr"))}</b></div></div></div>'
    if not cards: cards = '<p class="mut">최종 후보 없음</p>'

    badge = {3:("최종후보","b3"),2:("탈락·품질","b2"),1:("탈락·재무","b1"),0:("탈락·유동성","b0")}
    order = sorted(results, key=lambda r:(-r["stage"], -(r["fdr"].get("marcap") or 0)))
    trs = ""
    for r in order:
        m=r["m"] or {}; f=r["fdr"]; lb,cl=badge[r["stage"]]
        def cell(v, ok, txt):
            c = "" if ok is None else (" ok" if ok else " no")
            return f'<td class="num{c}">{txt}</td>'
        dr=debt_ratio_display(m); gr=m.get("rev_yoy"); om=m.get("op_margin")
        trs += f'<tr><td class="nm">{e(r["name"])}<span class="cd">{e(r["code"])}</span></td><td><span class="bd {cl}">{e(lb)}</span></td><td class="num">{prc(f.get("close"))}{chg(f.get("chg"))}</td>{cell(om,(om>=MIN_OP_MARGIN) if om is not None else None,pct(om))}{cell(gr,(gr>=MIN_GROWTH_YOY) if gr is not None else None,pct(gr))}{cell(dr,(dr<MAX_DEBT) if dr is not None else None,pct(dr))}<td class="num">{x1(m.get("per"))}</td><td class="num">{x2(m.get("pbr"))}</td><td class="num">{usd(m.get("ttm_revenue"))}</td><td class="num">{usd(f.get("amount"))}</td></tr>'

    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<style>
:root{{--bg:#0f1226;--card:#1a1f3a;--line:#2a3052;--fg:#e8ebf7;--mut:#9aa3c7;--ok:#34d399;--no:#fb7185;--ac:#7c9cff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 'Segoe UI','Malgun Gothic',sans-serif;padding:32px 20px}}
.w{{max-width:1100px;margin:0 auto}}h1{{font-size:24px;margin:0 0 4px}}.sub{{color:var(--mut);font-size:13px;margin:0 0 24px}}
.p{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:20px}}
h2{{font-size:15px;margin:0 0 16px;color:var(--ac)}}
.fstep{{position:relative;height:34px;margin:8px 0}}.fbar{{height:34px;border-radius:7px;background:linear-gradient(90deg,#4759b8,#7c9cff)}}.fstep.fin .fbar{{background:linear-gradient(90deg,#1f9d6b,#34d399)}}
.fl{{position:absolute;left:12px;top:7px;font-weight:600;font-size:13px;color:#fff;text-shadow:0 1px 2px #0006}}.fc{{position:absolute;right:12px;top:6px;font-weight:700;font-size:15px;color:#fff;text-shadow:0 1px 2px #0006}}
.cards{{display:flex;gap:14px;flex-wrap:wrap}}.card{{flex:1;min-width:230px;background:#141831;border:1px solid var(--line);border-left:3px solid var(--ok);border-radius:12px;padding:16px}}
.cn{{font-size:17px;font-weight:700}}.cm{{color:var(--mut);font-size:12px;margin:2px 0 12px}}.cg{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.cg span{{display:block;color:var(--mut);font-size:11px}}.cg b{{font-size:15px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--mut);font-size:11px;text-transform:uppercase}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}td.num.ok{{color:var(--ok)}}td.num.no{{color:var(--no)}}
.nm{{font-weight:600}}.cd{{color:var(--mut);font-weight:400;font-size:11px;margin-left:6px}}
.bd{{padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap}}.b3{{background:#103d2c;color:#34d399}}.b2{{background:#3a2540;color:#e879f9}}.b1{{background:#3a1f2a;color:#fb7185}}.b0{{background:#252a44;color:#9aa3c7}}
.mut{{color:var(--mut)}}.lg{{color:var(--mut);font-size:12px;margin-top:12px}}
</style></head><body><div class="w">
<h1>{e(title)}</h1>
<p class="sub">실제 SEC EDGAR 분기 재무(TTM·YoY 기준) + yfinance 현재가·거래대금·시총 · 대상 {n}개사 · 생성 {datetime.now().strftime("%Y-%m-%d %H:%M")}{(" · 주가 기준일 " + e(price_date)) if price_date else ""}</p>
<div class="p"><h2>단계별 깔때기</h2>{fhtml}<p class="lg">판단: 규모·수익성=TTM(최근 4분기 합), 성장=YoY(같은 분기 전년). 분기값은 누적 차감으로 환산. 기준(미국): 거래대금({TRADING_AVG_DAYS}일평균)≥${MIN_TRADING_USD/1e6:.0f}M·부채비율&lt;{MAX_DEBT:.0f}%·매출성장≥{MIN_GROWTH_YOY:.0f}%·영업이익률(TTM)≥{MIN_OP_MARGIN:.0f}%·이익피크({US_CRITERIA.min_peak_quarters}분기↑)·TTM영업현금&gt;0·자본&gt;0 or(자본&lt;0&amp;이익잉여금&gt;0) · (원가율개선 미적용)</p></div>
<div class="p"><h2>최종 후보</h2><div class="cards">{cards}</div></div>
<div class="p"><h2>전체 {n}개사 (통과 멀리 간 순 · 시총순)</h2><table><thead><tr><th>회사</th><th>결과</th><th>현재가</th><th>영업이익률(TTM)</th><th>매출성장(YoY)</th><th>부채비율</th><th>PER</th><th>PBR</th><th>TTM매출</th><th>거래대금</th></tr></thead><tbody>{trs}</tbody></table><p class="lg"><span style="color:var(--ok)">초록</span>=기준통과 / <span style="color:var(--no)">빨강</span>=미달. 거래대금은 yfinance 최근 {TRADING_AVG_DAYS}거래일 평균 달러거래대금(현재가는 최근 거래일 종가).</p></div>
</div></body></html>"""


if __name__ == "__main__":
    main()
