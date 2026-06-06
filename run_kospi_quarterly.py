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

DB = "D:/Agent_Project/dart-audit-extractor/screener.db"

# 기준 — 원래 '재무선배' 기준 (config.py 기본값과 동일)
# 과거 완화(거래대금50억·성장0%·이익률5%)는 2025·2026 분기가 수집 전이라
# 통과 기업이 0이던 임시 우회책이었음. 데이터가 채워져 원래 기준으로 복귀.
MIN_TRADING_KRW = 10_000_000_000  # 거래대금 100억
MAX_DEBT = 200.0                  # 부채비율 %
MIN_GROWTH_YOY = 10.0             # 매출성장 YoY %
MIN_OP_MARGIN = 10.0              # TTM 영업이익률 %

ACCT = {"매출액": "revenue", "영업이익": "op", "매출원가": "cogs",
        "영업활동현금흐름": "ocf", "부채총계": "debt", "자본총계": "equity",
        "자산총계": "assets"}
FLOW = {"revenue", "op", "cogs", "ocf"}
STOCK = {"debt", "equity", "assets"}
REPRT_ORDER = ["11013", "11012", "11014", "11011"]   # Q1,H1,9M,FY


def load_company(conn, corp):
    rows = conn.execute(
        "SELECT bsns_year,reprt_code,fs_div,계정,값,값_누적 FROM financials_q WHERE corp_code=?",
        (corp,)).fetchall()
    if not rows:
        return None
    fs = "CFS" if any(r[2] == "CFS" for r in rows) else "OFS"
    idx = {}
    for y, r, fsd, acct, v, va in rows:
        if fsd != fs:
            continue
        k = ACCT.get(acct)
        if k:
            idx[(y, r, k)] = (v, va)

    quarters = {}
    years = sorted({y for (y, _, _) in idx})
    for y in years:
        for key in FLOW:
            def cum(r):
                t = idx.get((y, r, key))
                if t is None:
                    return None
                v, va = t
                return va if va is not None else v
            cq1, ch, c9 = cum("11013"), cum("11012"), cum("11014")
            tfy = idx.get((y, "11011", key))
            cfy = tfy[0] if tfy else None
            qv = {}
            if cq1 is not None:
                qv[1] = cq1
            if ch is not None and cq1 is not None:
                qv[2] = ch - cq1
            if c9 is not None and ch is not None:
                qv[3] = c9 - ch
            if cfy is not None and c9 is not None:
                qv[4] = cfy - c9
            for q, val in qv.items():
                quarters.setdefault((y, q), {})[key] = val

    qkeys = sorted(quarters.keys())
    present = sorted({(y, r) for (y, r, _) in idx},
                     key=lambda yr: (yr[0], REPRT_ORDER.index(yr[1])))
    bs = {}
    if present:
        ly, lr = present[-1]
        for key in STOCK:
            t = idx.get((ly, lr, key))
            bs[key] = t[0] if t else None
        bs["asof"] = f"{ly} {REPRT_NM(lr)}"
    return {"quarters": quarters, "qkeys": qkeys, "bs": bs, "fs": fs}


def REPRT_NM(r):
    return {"11013": "1Q", "11012": "2Q(반기)", "11014": "3Q", "11011": "4Q(연간)"}.get(r, r)


def compute(d):
    q, qk, bs = d["quarters"], d["qkeys"], d["bs"]
    if len(qk) < 4:
        return None
    last4 = qk[-4:]

    def ttm(key):
        vals = [q[k].get(key) for k in last4]
        return sum(vals) if all(v is not None for v in vals) else None

    ttm_rev, ttm_op, ttm_cogs, ttm_ocf = ttm("revenue"), ttm("op"), ttm("cogs"), ttm("ocf")
    m = {
        "fs": d["fs"], "n_q": len(qk), "latest_q": f"{qk[-1][0]} {qk[-1][1]}Q",
        "ttm_revenue": ttm_rev, "ttm_op": ttm_op, "ttm_ocf": ttm_ocf,
        "op_margin": (ttm_op / ttm_rev * 100) if (ttm_rev and ttm_op is not None) else None,
        "debt_ratio": (bs["debt"] / bs["equity"] * 100) if bs.get("equity") else None,
        "bs_asof": bs.get("asof"),
    }
    # YoY (같은 분기 전년)
    ly, lq = qk[-1]
    rn = q[qk[-1]].get("revenue")
    rp = q.get((ly - 1, lq), {}).get("revenue")
    m["rev_yoy"] = ((rn - rp) / rp * 100) if (rp and rn is not None) else None
    # 이익 피크: 롤링 4분기 영업이익 합 중 최근이 최고
    sums = []
    for i in range(len(qk) - 3):
        w = [q[k].get("op") for k in qk[i:i + 4]]
        if all(x is not None for x in w):
            sums.append(sum(w))
    m["is_peak"] = bool(sums) and ttm_op is not None and ttm_op >= max(sums)
    # 원가율 추세: 최근 TTM cogs율 < 가장 이른 4분기 cogs율
    def cogs_ratio(ks):
        cc = [q[k].get("cogs") for k in ks]; rr = [q[k].get("revenue") for k in ks]
        if all(x is not None for x in cc + rr) and sum(rr) > 0:
            return sum(cc) / sum(rr)
        return None
    cr_new = cogs_ratio(last4); cr_old = cogs_ratio(qk[:4])
    m["cogs_improving"] = (cr_new is not None and cr_old is not None and cr_new <= cr_old)
    m["ttm_ocf_ok"] = (ttm_ocf is not None and ttm_ocf > 0)
    return m


def screen(m, trading_krw):
    """단계별 통과 여부. 반환: dict(stage->bool), reasons."""
    liq = trading_krw is not None and trading_krw >= MIN_TRADING_KRW
    fh = (m and m["debt_ratio"] is not None and m["debt_ratio"] < MAX_DEBT
          and m["rev_yoy"] is not None and m["rev_yoy"] >= MIN_GROWTH_YOY
          and m["ttm_ocf_ok"])
    qg = (m and m["op_margin"] is not None and m["op_margin"] >= MIN_OP_MARGIN
          and m["is_peak"] and m["cogs_improving"])
    return {"liquidity": bool(liq), "financial": bool(fh), "quality": bool(qg)}


def main(xlsx_prefix="코스피_분기_결과", dash="dashboard_kospi.html",
         title="코스피 분기 스크리너 결과", criteria_note=""):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    corps = [r[0] for r in conn.execute("SELECT DISTINCT corp_code FROM financials_q")]
    meta = {r[0]: (r[1], r[2]) for r in
            conn.execute("SELECT corp_code, corp_name, stock_code FROM companies")}
    print(f"분기 재무 보유 코스피: {len(corps)}개사")

    # FDR 거래대금·시총
    fdr_map = {}
    try:
        import FinanceDataReader as fdr
        df = fdr.StockListing("KOSPI")
        for _, r in df.iterrows():
            fdr_map[str(r["Code"]).zfill(6)] = {
                "amount": float(r["Amount"]) if r.get("Amount") == r.get("Amount") else None,
                "marcap": float(r["Marcap"]) if r.get("Marcap") == r.get("Marcap") else None,
                "chg": float(r["ChagesRatio"]) if r.get("ChagesRatio") == r.get("ChagesRatio") else None,
            }
        print(f"FDR 시장데이터(거래대금·시총): {len(fdr_map)}종목")
    except Exception as e:
        print(f"[!] FDR 시장데이터 생략: {e}")

    results = []
    for corp in corps:
        name, scode = meta.get(corp, (corp, ""))
        scode = (scode or "").zfill(6)
        d = load_company(conn, corp)
        m = compute(d) if d else None
        fdr_i = fdr_map.get(scode, {})
        st = screen(m, fdr_i.get("amount"))
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
        m = r["m"]
        print(f"  - {r['name']}({r['code']})  영업이익률(TTM) {m['op_margin']:.1f}% · "
              f"매출성장(YoY) {m['rev_yoy']:.1f}% · 부채비율 {m['debt_ratio']:.0f}%")

    # 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx = f"{xlsx_prefix}_{ts}.xlsx"
    save_xlsx(results, xlsx)
    print(f"\n📁 결과 저장: {xlsx}")
    html_out = render(results, n, n_liq, n_fh, n_qg, finals, title=title, criteria_note=criteria_note)
    Path(dash).write_text(html_out, encoding="utf-8")
    print(f"📊 대시보드: {dash}")
    return results


def save_xlsx(results, path):
    try:
        import openpyxl
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "코스피 분기 스크리닝"
        ws.append(["종목코드", "회사명", "결과단계", "재무기준일", "거래대금(억)", "시총(억)",
                   "TTM매출(억)", "TTM영업이익(억)", "영업이익률TTM(%)", "매출성장YoY(%)",
                   "부채비율(%)", "이익피크", "원가율개선", "TTM영업현금>0"])
        order = sorted(results, key=lambda r: (-r["stage"], -(r["fdr"].get("marcap") or 0)))
        lbl = {3: "최종후보", 2: "탈락:품질성장", 1: "탈락:재무건전성", 0: "탈락:유동성"}
        for r in order:
            m = r["m"] or {}
            f = r["fdr"]
            ws.append([
                r["code"], r["name"], lbl[r["stage"]], m.get("bs_asof", ""),
                round(f.get("amount", 0)/1e8, 1) if f.get("amount") else None,
                round(f.get("marcap", 0)/1e8, 0) if f.get("marcap") else None,
                round(m.get("ttm_revenue", 0)/1e8, 0) if m.get("ttm_revenue") else None,
                round(m.get("ttm_op", 0)/1e8, 0) if m.get("ttm_op") else None,
                round(m["op_margin"], 1) if m.get("op_margin") is not None else None,
                round(m["rev_yoy"], 1) if m.get("rev_yoy") is not None else None,
                round(m["debt_ratio"], 0) if m.get("debt_ratio") is not None else None,
                "O" if m.get("is_peak") else "X",
                "O" if m.get("cogs_improving") else "X",
                "O" if m.get("ttm_ocf_ok") else "X",
            ])
        wb.save(path)
    except Exception as e:
        print(f"[!] xlsx 저장 실패: {e}")


def render(results, n, n_liq, n_fh, n_qg, finals, title="코스피 분기 스크리너 결과", criteria_note=""):
    e = html.escape
    def won(v):
        return "—" if v is None else (f"{v/1e12:.1f}조" if abs(v)>=1e12 else f"{v/1e8:.0f}억")
    def pct(v): return "—" if v is None else f"{v:.1f}%"

    funnel = [("전체 대상", n), ("① 유동성", n_liq), ("② 재무건전성", n_fh), ("③ 품질성장(최종)", n_qg)]
    fhtml = ""
    for i, (lb, c) in enumerate(funnel):
        w = c/funnel[0][1]*100 if funnel[0][1] else 0
        fin = i == len(funnel)-1
        fhtml += f'<div class="fstep{" fin" if fin else ""}"><div class="fbar" style="width:{max(w,5):.1f}%"></div><div class="fl">{e(lb)}</div><div class="fc">{c}</div></div>'

    cards = ""
    for r in sorted(finals, key=lambda r:-(r["fdr"].get("marcap") or 0)):
        m=r["m"]; f=r["fdr"]
        cards += f'<div class="card"><div class="cn">{e(r["name"])}</div><div class="cm">{e(r["code"])} · 시총 {won(f.get("marcap"))}</div><div class="cg"><div><span>영업이익률(TTM)</span><b>{pct(m["op_margin"])}</b></div><div><span>매출성장(YoY)</span><b>{pct(m["rev_yoy"])}</b></div><div><span>부채비율</span><b>{pct(m["debt_ratio"])}</b></div><div><span>거래대금</span><b>{won(f.get("amount"))}</b></div></div></div>'
    if not cards: cards = '<p class="mut">최종 후보 없음</p>'

    badge = {3:("최종후보","b3"),2:("탈락·품질","b2"),1:("탈락·재무","b1"),0:("탈락·유동성","b0")}
    order = sorted(results, key=lambda r:(-r["stage"], -(r["fdr"].get("marcap") or 0)))
    trs = ""
    for r in order:
        m=r["m"] or {}; f=r["fdr"]; lb,cl=badge[r["stage"]]
        def cell(v, ok, txt):
            c = "" if ok is None else (" ok" if ok else " no")
            return f'<td class="num{c}">{txt}</td>'
        dr=m.get("debt_ratio"); gr=m.get("rev_yoy"); om=m.get("op_margin")
        trs += f'<tr><td class="nm">{e(r["name"])}<span class="cd">{e(r["code"])}</span></td><td><span class="bd {cl}">{e(lb)}</span></td>{cell(om,(om>=MIN_OP_MARGIN) if om is not None else None,pct(om))}{cell(gr,(gr>=MIN_GROWTH_YOY) if gr is not None else None,pct(gr))}{cell(dr,(dr<MAX_DEBT) if dr is not None else None,pct(dr))}<td class="num">{won(m.get("ttm_revenue"))}</td><td class="num">{won(f.get("amount"))}</td></tr>'

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
<p class="sub">실제 DART 분기 재무(TTM·YoY 기준) + FinanceDataReader 거래대금·시총 · 대상 {n}개사 · {datetime.now().strftime("%Y-%m-%d %H:%M")}{(" · " + e(criteria_note)) if criteria_note else ""}</p>
<div class="p"><h2>단계별 깔때기</h2>{fhtml}<p class="lg">판단: 규모·수익성=TTM(최근 4분기 합), 성장=YoY(같은 분기 전년). 분기값은 누적 차감으로 환산. 기준: 거래대금≥{MIN_TRADING_KRW/1e8:.0f}억·부채비율&lt;{MAX_DEBT:.0f}%·매출성장≥{MIN_GROWTH_YOY:.0f}%·영업이익률(TTM)≥{MIN_OP_MARGIN:.0f}%·이익피크·원가율개선·TTM영업현금&gt;0</p></div>
<div class="p"><h2>최종 후보</h2><div class="cards">{cards}</div></div>
<div class="p"><h2>전체 {n}개사 (통과 멀리 간 순 · 시총순)</h2><table><thead><tr><th>회사</th><th>결과</th><th>영업이익률(TTM)</th><th>매출성장(YoY)</th><th>부채비율</th><th>TTM매출</th><th>거래대금</th></tr></thead><tbody>{trs}</tbody></table><p class="lg"><span style="color:var(--ok)">초록</span>=기준통과 / <span style="color:var(--no)">빨강</span>=미달. 거래대금은 FDR 최근 거래일 기준.</p></div>
</div></body></html>"""


if __name__ == "__main__":
    main()
