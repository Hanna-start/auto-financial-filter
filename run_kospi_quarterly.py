#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""코스피 분기 스크리너 — 실제 DART 분기 재무(financials_q) 기반.

판단 원칙(계절성 보정):
  - 규모·수익성: TTM(최근 4개 분기 합)으로 판단 (단일 3개월 아님)
  - 성장: YoY(같은 분기 전년 대비)로 판단
  - 분기값: 누적(값_누적) 차감으로 순수 분기 환산 (Q2=반기-1Q, Q4=연간-3Q)

데이터:
  - 재무 = screener.db financials_q (build_kospi_universe → collect_quarterly 산출)
  - 거래대금·시총·등락률 = FinanceDataReader (KRX, 키 불필요)

산출: 콘솔 리포트 + 코스피_분기_결과_*.xlsx + dashboard_kospi.html
사용: py run_kospi_quarterly.py
"""
import sys, io, sqlite3, json, html
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 공유 엔진(적재·환산·지표·기준·게이트)은 engine.py 한 곳. 기준은 KR_CRITERIA 프로파일.
from engine import (DB, MAX_DEBT, MIN_GROWTH_YOY, MIN_OP_MARGIN,
                    load_company, compute, add_valuation, screen, debt_ratio_display,
                    KR_CRITERIA, TRADING_AVG_DAYS)

# 표시용 별칭(단일 출처=engine.KR_CRITERIA). 게이트는 screen(m, trading, KR_CRITERIA).
MIN_TRADING_KRW = KR_CRITERIA.min_trading  # 거래대금 100억원
KOSPI_INDEX = "D:/Agent_Project/dart-audit-extractor/data/kospi_index.json"


def fetch_krx_marcap(market, avg_days=TRADING_AVG_DAYS, max_back=None):
    """KRX 일별 시세 → {종목코드:{close, amount, marcap, chg}} + 기준거래일.
      - 현재가·시총·등락률 = 가장 최근 거래일 값(EOD, 평균 아님).
      - 거래대금(amount) = 최근 avg_days 거래일 평균(업계 표준; 하루치 출렁임 완화).

    FDR 'FinanceData/fdr_krx_data_cache' GitHub의 일별 CSV를 max_work_dt부터 거슬러,
    '실제 존재하는' 거래일 CSV를 avg_days개 모은다(주말·휴장·미게시일은 건너뜀 → max_back일 내).
    가장 최근 성공일이 기준거래일(price_date). 받은 값은 market_cache로도 적재됨."""
    import requests, pandas as pd
    from datetime import timedelta
    max_back = max_back or (avg_days * 2 + 10)            # 거래일 avg_days개 확보용 달력일 여유
    h = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.krx.co.kr/"}
    ru = ("http://data.krx.co.kr/comm/bldAttendant/executeForResourceBundle.cmd"
          "?baseName=krx.mdc.i18n.component&key=B128.bld")
    mwd = json.loads(requests.get(ru, headers=h, timeout=10).text)["result"]["output"][0]["max_work_dt"]
    base = ("https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/"
            "refs/heads/master/data/listing/krx/{}.csv")
    mkt = {"KOSPI": "STK", "KOSDAQ": "KSQ"}[market]
    nn = lambda v: float(v) if v == v else None           # NaN 제거
    d0 = datetime.strptime(mwd, "%Y%m%d")
    latest, price_date = None, None                       # 최근 거래일 종가·시총·등락률
    amt_sum, amt_cnt = {}, {}                             # 거래대금 평균 누적(종목별)
    days = 0
    for i in range(max_back):
        if days >= avg_days:
            break
        ds = (d0 - timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            df = pd.read_csv(base.format(ds), dtype={"Code": str, "MarketId": str})
        except Exception:
            continue                                      # 주말·휴장·미게시일
        df = df[df["MarketId"] == mkt]
        if not len(df):
            continue
        first = latest is None                            # 첫(=가장 최근) 성공일
        if first:
            latest, price_date = {}, ds
        for _, r in df.iterrows():
            code = str(r["Code"]).zfill(6)
            a = nn(r["Amount"])
            if a is not None:
                amt_sum[code] = amt_sum.get(code, 0.0) + a
                amt_cnt[code] = amt_cnt.get(code, 0) + 1
            if first:
                latest[code] = {"close": nn(r["Close"]), "marcap": nn(r["Marcap"]),
                                "chg": nn(r["ChagesRatio"])}
        days += 1
    if latest is None:
        return {}, None
    out = {}
    for code, v in latest.items():
        out[code] = {"close": v["close"],
                     "amount": (amt_sum[code] / amt_cnt[code]) if amt_cnt.get(code) else None,
                     "marcap": v["marcap"], "chg": v["chg"]}
    return out, price_date


def main(xlsx_prefix="코스피_분기_결과", dash="dashboards/dashboard_kospi.html",
         title="코스피 분기 스크리너 결과", criteria_note="",
         market="KOSPI", index_json=None):
    """market: FDR StockListing 시장명(KOSPI/KOSDAQ). 주가·거래대금·시총 출처.
    index_json: 대상 명단 json 경로. 주면 그 회사들만(이름·종목코드도 여기서) 스크리닝
                → financials_q에 코스피·코스닥이 섞여도 시장별 분리. 없으면 financials_q 전체."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    if index_json:
        have = {r[0] for r in conn.execute("SELECT DISTINCT corp_code FROM financials_q")}
        uni = json.loads(Path(index_json).read_text(encoding="utf-8"))
        meta = {c["corp_code"]: (c.get("corp_name", ""), str(c.get("stock_code", "")).zfill(6))
                for c in uni}
        corps = [c["corp_code"] for c in uni if c["corp_code"] in have]
    else:
        corps = [r[0] for r in conn.execute("SELECT DISTINCT corp_code FROM financials_q")]
        meta = {r[0]: (r[1], r[2]) for r in
                conn.execute("SELECT corp_code, corp_name, stock_code FROM companies")}
    print(f"분기 재무 보유 {market}: {len(corps)}개사")

    # KRX 시장데이터: 현재가·등락률·거래대금·시총 (최근 거래일 기준)
    fdr_map = {}
    price_date = None
    try:
        fdr_map, price_date = fetch_krx_marcap(market)
        print(f"KRX 시장데이터(현재가·거래대금·시총): {len(fdr_map)}종목"
              + (f" · 거래일 {price_date}" if price_date else ""))
    except Exception as e:
        print(f"[!] KRX 시장데이터 생략: {e}")

    # 시세 캐시: 라이브 성공분 저장 + 실패/누락분은 직전 저장값으로 폴백
    import market_cache
    fdr_map, cinfo = market_cache.merge_with_cache(market, fdr_map, price_date)
    if not price_date and cinfo["asof_dates"]:
        price_date = max(cinfo["asof_dates"])
    if cinfo["cache"]:
        print(f"  └ 거래대금 폴백: 캐시 {cinfo['cache']}종목"
              + (f"(as-of {price_date})" if price_date else "")
              + f" · 라이브 {cinfo['live']}종목")

    results = []
    for corp in corps:
        name, scode = meta.get(corp, (corp, ""))
        scode = (scode or "").zfill(6)
        d = load_company(conn, corp)
        m = compute(d) if d else None
        fdr_i = fdr_map.get(scode, {})
        add_valuation(m, fdr_i.get("marcap"))
        st = screen(m, fdr_i.get("amount"), KR_CRITERIA)
        # 최종 후보 = 3단계 모두 통과
        final = st["liquidity"] and st["financial"] and st["quality"]
        # 도달 단계
        if final: stage = 3
        elif st["liquidity"] and st["financial"]: stage = 2
        elif st["liquidity"]: stage = 1
        else: stage = 0
        results.append({"corp": corp, "name": name, "code": scode,
                        "m": m, "fdr": fdr_i, "st": st, "stage": stage, "final": final})
    conn.close()

    # 깔때기
    n = len(results)
    n_liq = sum(1 for r in results if r["st"]["liquidity"])
    n_fh = sum(1 for r in results if r["st"]["liquidity"] and r["st"]["financial"])
    n_qg = sum(1 for r in results if r["final"])
    finals = [r for r in results if r["final"]]

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(f"기준: 거래대금≥{MIN_TRADING_KRW/1e8:.0f}억 · 부채비율<{MAX_DEBT:.0f}% · "
          f"매출성장(YoY)≥{MIN_GROWTH_YOY:.0f}% · TTM영업이익률≥{MIN_OP_MARGIN:.0f}% · 이익피크 · 원가율개선 · TTM영업현금>0")
    print(f"\n단계별 통과:")
    print(f"  대상           : {n}")
    print(f"  ① 유동성       : {n_liq}  ({n_liq/n*100:.0f}%)")
    print(f"  ② 재무건전성   : {n_fh}")
    print(f"  ③ 품질성장(최종): {n_qg}")
    print(f"\n최종 후보 {len(finals)}개:")
    finals.sort(key=lambda r: -(r["fdr"].get("marcap") or 0))
    for r in finals:
        m = r["m"]; f = r["fdr"]
        cl = f.get("close"); ch = f.get("chg")
        px = (f"{cl:,.0f}원" + (f"({ch:+.1f}%)" if ch is not None else "")) if cl else "주가—"
        per = f"PER {m['per']:.1f}" if m.get("per") else "PER —"
        pbr = f"PBR {m['pbr']:.2f}" if m.get("pbr") else "PBR —"
        print(f"  - {r['name']}({r['code']})  {px} · 영업이익률(TTM) {m['op_margin']:.1f}% · "
              f"매출성장(YoY) {m['rev_yoy']:.1f}% · 부채비율 {m['debt_ratio']:.0f}% · "
              f"{per} · {pbr}")

    # 저장 (xlsx→results/, 대시보드→dashboards/)
    Path("results").mkdir(exist_ok=True); Path("dashboards").mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx = f"results/{xlsx_prefix}_{ts}.xlsx"
    save_xlsx(results, xlsx, price_date=price_date, sheet=title)
    print(f"\n📁 결과 저장: {xlsx}")
    html_out = render(results, n, n_liq, n_fh, n_qg, finals, title=title,
                      criteria_note=criteria_note, price_date=price_date)
    Path(dash).write_text(html_out, encoding="utf-8")
    print(f"📊 대시보드: {dash}")
    return results


def save_xlsx(results, path, price_date=None, sheet="분기 스크리닝"):
    try:
        import openpyxl
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = sheet[:31]
        pcol = f"현재가(원,{price_date})" if price_date else "현재가(원)"
        ws.append(["종목코드", "회사명", "결과단계", pcol, "등락률(%)", "재무기준일",
                   "거래대금(억)", "시총(억)",
                   "TTM매출(억)", "TTM영업이익(억)", "TTM순이익(억)", "영업이익률TTM(%)", "매출성장YoY(%)",
                   "부채비율(%)", "PER", "PBR", "PSR", "시총/TTM영업이익",
                   "이익피크", "원가율개선", "TTM영업현금>0"])
        order = sorted(results, key=lambda r: (-r["stage"], -(r["fdr"].get("marcap") or 0)))
        lbl = {3: "최종후보", 2: "탈락:품질성장", 1: "탈락:재무건전성", 0: "탈락:유동성"}
        for r in order:
            m = r["m"] or {}
            f = r["fdr"]
            dr = debt_ratio_display(m)
            ws.append([
                r["code"], r["name"], lbl[r["stage"]],
                round(f.get("close")) if f.get("close") else None,
                round(f.get("chg"), 2) if f.get("chg") is not None else None,
                m.get("bs_asof", ""),
                round(f.get("amount", 0)/1e8, 1) if f.get("amount") else None,
                round(f.get("marcap", 0)/1e8, 0) if f.get("marcap") else None,
                round(m.get("ttm_revenue", 0)/1e8, 0) if m.get("ttm_revenue") else None,
                round(m.get("ttm_op", 0)/1e8, 0) if m.get("ttm_op") else None,
                round(m.get("ttm_net", 0)/1e8, 0) if m.get("ttm_net") else None,
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


def render(results, n, n_liq, n_fh, n_qg, finals, title="코스피 분기 스크리너 결과",
           criteria_note="", price_date=None):
    e = html.escape
    def won(v):
        return "—" if v is None else (f"{v/1e12:.1f}조" if abs(v)>=1e12 else f"{v/1e8:.0f}억")
    def pct(v): return "—" if v is None else f"{v:.1f}%"
    def x1(v): return "—" if v is None else f"{v:.1f}배"   # PER·시총/영업이익
    def x2(v): return "—" if v is None else f"{v:.2f}배"   # PBR·PSR
    def krw(v): return "—" if v is None else f"{v:,.0f}원"  # 현재가
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
        cards += f'<div class="card"><div class="cn">{e(r["name"])}</div><div class="cm">{e(r["code"])} · 시총 {won(f.get("marcap"))}</div><div class="cg"><div><span>현재가</span><b>{krw(f.get("close"))}{chg(f.get("chg"))}</b></div><div><span>영업이익률(TTM)</span><b>{pct(m["op_margin"])}</b></div><div><span>매출성장(YoY)</span><b>{pct(m["rev_yoy"])}</b></div><div><span>부채비율</span><b>{pct(m["debt_ratio"])}</b></div><div><span>거래대금</span><b>{won(f.get("amount"))}</b></div><div><span>PER</span><b>{x1(m.get("per"))}</b></div><div><span>PBR</span><b>{x2(m.get("pbr"))}</b></div><div><span>PSR</span><b>{x2(m.get("psr"))}</b></div></div></div>'
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
        trs += f'<tr><td class="nm">{e(r["name"])}<span class="cd">{e(r["code"])}</span></td><td><span class="bd {cl}">{e(lb)}</span></td><td class="num">{krw(f.get("close"))}{chg(f.get("chg"))}</td>{cell(om,(om>=MIN_OP_MARGIN) if om is not None else None,pct(om))}{cell(gr,(gr>=MIN_GROWTH_YOY) if gr is not None else None,pct(gr))}{cell(dr,(dr<MAX_DEBT) if dr is not None else None,pct(dr))}<td class="num">{x1(m.get("per"))}</td><td class="num">{x2(m.get("pbr"))}</td><td class="num">{won(m.get("ttm_revenue"))}</td><td class="num">{won(f.get("amount"))}</td></tr>'

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
<p class="sub">실제 DART 분기 재무(TTM·YoY 기준) + FinanceDataReader 현재가·거래대금·시총 · 대상 {n}개사 · 생성 {datetime.now().strftime("%Y-%m-%d %H:%M")}{(" · 주가 기준일 " + e(price_date)) if price_date else ""}{(" · " + e(criteria_note)) if criteria_note else ""}</p>
<div class="p"><h2>단계별 깔때기</h2>{fhtml}<p class="lg">판단: 규모·수익성=TTM(최근 4분기 합), 성장=YoY(같은 분기 전년). 분기값은 누적 차감으로 환산. 기준: 거래대금({TRADING_AVG_DAYS}일평균)≥{MIN_TRADING_KRW/1e8:.0f}억·부채비율&lt;{MAX_DEBT:.0f}%·매출성장≥{MIN_GROWTH_YOY:.0f}%·영업이익률(TTM)≥{MIN_OP_MARGIN:.0f}%·이익피크·원가율개선·TTM영업현금&gt;0</p></div>
<div class="p"><h2>최종 후보</h2><div class="cards">{cards}</div></div>
<div class="p"><h2>전체 {n}개사 (통과 멀리 간 순 · 시총순)</h2><table><thead><tr><th>회사</th><th>결과</th><th>현재가</th><th>영업이익률(TTM)</th><th>매출성장(YoY)</th><th>부채비율</th><th>PER</th><th>PBR</th><th>TTM매출</th><th>거래대금</th></tr></thead><tbody>{trs}</tbody></table><p class="lg"><span style="color:var(--ok)">초록</span>=기준통과 / <span style="color:var(--no)">빨강</span>=미달. 거래대금은 FDR 최근 {TRADING_AVG_DAYS}거래일 평균(현재가·시총은 최근 거래일 종가).</p></div>
</div></body></html>"""


if __name__ == "__main__":
    # index_json으로 코스피 명단만 대상화(financials_q에 코스닥·미국이 섞여 있으므로).
    main(index_json=KOSPI_INDEX)
