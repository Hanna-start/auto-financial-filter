#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
상장사 스크리너 결과 대시보드 생성기 (실데이터 전용).

데이터 소스:
  - 단계별 통과/탈락: 최신 `상장사_스크리너_결과_*.xlsx` (run_listed_screener.py 산출)
  - 회사별 재무 수치: screener.db (실제 DART, 연 단위) — annual 필터와 동일하게 계산

산출: dashboard.html (외부 의존 없는 단일 파일). 가짜 데이터 미사용.

사용:
  py build_dashboard.py                  # 최신 결과 xlsx 자동 선택
  py build_dashboard.py --xlsx 파일.xlsx
"""
import sys
import io
import glob
import os
import argparse
import html
from datetime import datetime
from pathlib import Path

import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from auto_financial_filter.config import FilterConfig
from auto_financial_filter.data_access.screener_db_adapter import ScreenerDBAdapter, DEFAULT_DB_PATH

# run_listed_screener.build_config 와 동일한 기준
DEBT_MAX = 200.0
GROWTH_MIN = 0.0
MARGIN_MIN = 5.0
VOLUME_MIN_KRW = 5_000_000_000

STAGE_LABELS = ["유동성", "재무건전성", "품질성장", "모멘텀"]


def _zfill(code) -> str:
    return str(code).strip().zfill(6)


def load_stage_membership(xlsx: str):
    """xlsx의 'Stage N Passed' 시트 → 단계별 통과 코드 집합."""
    xl = pd.ExcelFile(xlsx)
    passed = {}
    for n in (1, 2, 3, 4):
        sheet = f"Stage {n} Passed"
        if sheet in xl.sheet_names:
            df = pd.read_excel(xlsx, sheet_name=sheet)
            passed[n] = {_zfill(c) for c in df["Code"].tolist()}
        else:
            passed[n] = set()
    summary = pd.read_excel(xlsx, sheet_name="Summary")
    stages = pd.read_excel(xlsx, sheet_name="Stage Results")
    return passed, summary, stages


def compute_metrics(annual: list) -> dict:
    """annual_financial_filters 와 동일한 계산."""
    if not annual:
        return {}
    latest = annual[-1]
    rev = latest.get("revenue", 0.0)
    m = {
        "year": latest.get("year"),
        "revenue": rev,
        "debt_ratio": latest.get("debt_ratio", 999.0),
        "op_profit": latest.get("operating_profit", 0.0),
        "ocf": latest.get("operating_cash_flow", 0.0),
        "n_years": len(annual),
    }
    # 매출성장 YoY
    if len(annual) >= 2 and annual[-2].get("revenue", 0.0) > 0:
        prev = annual[-2]["revenue"]
        m["rev_growth"] = (rev - prev) / prev * 100
    else:
        m["rev_growth"] = None
    # 영업이익률
    m["op_margin"] = (m["op_profit"] / rev * 100) if rev > 0 else None
    # 이익 피크 (최근이 보유연도 중 최고)
    ops = [a.get("operating_profit", 0.0) for a in annual]
    m["is_peak"] = (m["op_profit"] >= max(ops)) if ops else False
    # 영업현금흐름 건전성
    ocfs = [a.get("operating_cash_flow", 0.0) for a in annual]
    m["ocf_ok"] = bool(ocfs) and (all(x > 0 for x in ocfs) or sum(ocfs) > 0)
    return m


def furthest_stage(code: str, passed: dict) -> int:
    """0=유동성탈락 … 4=최종통과. (해당 stage까지 '통과'한 최대 N)"""
    f = 0
    for n in (1, 2, 3, 4):
        if code in passed[n]:
            f = n
    return f


def fmt_won(v) -> str:
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e12:
        return f"{v/1e12:.1f}조"
    if a >= 1e8:
        return f"{v/1e8:.0f}억"
    return f"{v:,.0f}"


def fmt_pct(v) -> str:
    return "—" if v is None else f"{v:.1f}%"


def build(xlsx: str, db_path: str) -> str:
    passed, summary, stages = load_stage_membership(xlsx)

    adapter = ScreenerDBAdapter(FilterConfig(), db_path)
    symbols = adapter.get_listed_symbols(require_financials=True)

    rows = []
    for s in symbols:
        code = _zfill(s.code)
        try:
            data = adapter.get_financial_statements(s, years=5)
            metrics = compute_metrics(data.get("annual_data", []))
        except Exception:
            metrics = {}
        rows.append({
            "code": code, "name": s.name, "market": s.market,
            "stage": furthest_stage(code, passed), "m": metrics,
        })

    total = len(rows)
    funnel = [total, len(passed[1]), len(passed[2]), len(passed[3]), len(passed[4])]
    finalists = [r for r in rows if r["stage"] == 4]
    kospi = sum(1 for r in rows if r["market"] == "KOSPI")
    kosdaq = total - kospi

    # 정렬: 멀리 간 순 → 매출 큰 순
    rows.sort(key=lambda r: (-r["stage"], -(r["m"].get("revenue") or 0)))

    gen_time = datetime.fromtimestamp(os.path.getmtime(xlsx)).strftime("%Y-%m-%d %H:%M")
    return render_html(xlsx, gen_time, total, funnel, finalists, rows, kospi, kosdaq)


def render_html(xlsx, gen_time, total, funnel, finalists, rows, kospi, kosdaq):
    e = html.escape

    # 깔때기
    funnel_steps = ["전체 대상"] + STAGE_LABELS
    funnel_html = ""
    for i, (label, cnt) in enumerate(zip(funnel_steps, funnel)):
        pct = cnt / funnel[0] * 100 if funnel[0] else 0
        is_final = (i == len(funnel) - 1)
        funnel_html += f"""
        <div class="fstep{' final' if is_final else ''}">
          <div class="fbar" style="width:{max(pct,6):.1f}%"></div>
          <div class="flabel">{e(label)}</div>
          <div class="fcount">{cnt}<span>개</span></div>
        </div>"""

    # 최종 후보 카드
    cards = ""
    for r in finalists:
        m = r["m"]
        cards += f"""
        <div class="card">
          <div class="cname">{e(r['name'])}</div>
          <div class="cmeta">{e(r['code'])} · {e(r['market'])}</div>
          <div class="cgrid">
            <div><span>매출(최근)</span><b>{fmt_won(m.get('revenue'))}</b></div>
            <div><span>매출성장</span><b>{fmt_pct(m.get('rev_growth'))}</b></div>
            <div><span>영업이익률</span><b>{fmt_pct(m.get('op_margin'))}</b></div>
            <div><span>부채비율</span><b>{fmt_pct(m.get('debt_ratio'))}</b></div>
          </div>
        </div>"""
    if not cards:
        cards = '<p class="muted">최종 후보가 없습니다.</p>'

    # 전체 표
    stage_badge = {
        0: ('탈락·유동성', 'b0'), 1: ('탈락·재무건전성', 'b1'),
        2: ('탈락·품질성장', 'b2'), 3: ('탈락·모멘텀', 'b3'), 4: ('최종 후보', 'b4'),
    }
    trs = ""
    for r in rows:
        m = r["m"]
        label, cls = stage_badge[r["stage"]]

        def cell(val, ok, txt):
            c = "" if ok is None else (" ok" if ok else " no")
            return f'<td class="num{c}">{txt}</td>'

        debt = m.get("debt_ratio")
        gro = m.get("rev_growth")
        mar = m.get("op_margin")
        trs += f"""
        <tr>
          <td class="nm">{e(r['name'])}<span class="cd">{e(r['code'])}</span></td>
          <td>{e(r['market'])}</td>
          <td><span class="badge {cls}">{e(label)}</span></td>
          {cell(debt, (debt < DEBT_MAX) if debt is not None else None, fmt_pct(debt))}
          {cell(gro, (gro >= GROWTH_MIN) if gro is not None else None, fmt_pct(gro))}
          {cell(mar, (mar >= MARGIN_MIN) if mar is not None else None, fmt_pct(mar))}
          <td class="num{' ok' if m.get('ocf_ok') else ' no' if m else ''}">{fmt_won(m.get('ocf'))}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>상장사 스크리너 결과 대시보드</title>
<style>
  :root{{--bg:#0f1226;--card:#1a1f3a;--line:#2a3052;--fg:#e8ebf7;--mut:#9aa3c7;
        --ok:#34d399;--no:#fb7185;--accent:#7c9cff;}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);
    font:15px/1.5 'Segoe UI','Malgun Gothic',sans-serif;padding:32px 20px}}
  .wrap{{max-width:1100px;margin:0 auto}}
  h1{{font-size:24px;margin:0 0 4px}} .sub{{color:var(--mut);margin:0 0 28px;font-size:13px}}
  .panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:22px}}
  h2{{font-size:15px;margin:0 0 16px;color:var(--accent);letter-spacing:.3px}}
  /* funnel */
  .fstep{{margin:9px 0}} .fbar{{height:30px;border-radius:7px;
    background:linear-gradient(90deg,#4759b8,#7c9cff)}}
  .fstep.final .fbar{{background:linear-gradient(90deg,#1f9d6b,#34d399)}}
  .fstep{{position:relative;display:grid;grid-template-columns:1fr;align-items:center}}
  .flabel{{position:absolute;left:12px;top:5px;font-size:13px;font-weight:600;color:#fff;text-shadow:0 1px 2px #0006}}
  .fcount{{position:absolute;right:12px;top:3px;font-size:16px;font-weight:700;color:#fff;text-shadow:0 1px 2px #0006}}
  .fcount span{{font-size:11px;font-weight:400;opacity:.85;margin-left:2px}}
  /* cards */
  .cards{{display:flex;gap:16px;flex-wrap:wrap}}
  .card{{flex:1;min-width:240px;background:#141831;border:1px solid var(--line);
    border-radius:12px;padding:18px;border-left:3px solid var(--ok)}}
  .cname{{font-size:18px;font-weight:700}} .cmeta{{color:var(--mut);font-size:12px;margin:2px 0 14px}}
  .cgrid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  .cgrid span{{display:block;color:var(--mut);font-size:11px}} .cgrid b{{font-size:16px}}
  /* stats */
  .stats{{display:flex;gap:14px;flex-wrap:wrap}}
  .stat{{flex:1;min-width:120px;background:#141831;border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
  .stat b{{display:block;font-size:22px}} .stat span{{color:var(--mut);font-size:12px}}
  /* table */
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th,td{{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line)}}
  th{{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}}
  td.num.ok{{color:var(--ok)}} td.num.no{{color:var(--no)}}
  .nm{{font-weight:600}} .cd{{color:var(--mut);font-weight:400;font-size:11px;margin-left:7px}}
  .badge{{padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap}}
  .b4{{background:#103d2c;color:#34d399}} .b3{{background:#3a2b14;color:#fbbf24}}
  .b2{{background:#3a2540;color:#e879f9}} .b1{{background:#3a1f2a;color:#fb7185}} .b0{{background:#252a44;color:#9aa3c7}}
  .muted{{color:var(--mut)}} .legend{{color:var(--mut);font-size:12px;margin-top:12px}}
  .legend b{{color:var(--fg)}}
</style></head>
<body><div class="wrap">
  <h1>상장사 스크리너 결과 대시보드</h1>
  <p class="sub">실제 DART 재무 + yfinance 기반 · 대상 {total}개사 · 결과 시각 {e(gen_time)} · 출처 {e(os.path.basename(xlsx))}</p>

  <div class="panel">
    <h2>단계별 필터 깔때기</h2>
    {funnel_html}
    <p class="legend">기준: 유동성 거래대금 ≥ 50억 · 부채비율 &lt; {DEBT_MAX:.0f}% · 매출성장(YoY) ≥ {GROWTH_MIN:.0f}% · 영업이익률 ≥ {MARGIN_MIN:.0f}% · 영업이익 피크 · 영업현금흐름 건전</p>
  </div>

  <div class="panel">
    <h2>최종 후보</h2>
    <div class="cards">{cards}</div>
  </div>

  <div class="panel">
    <h2>구성</h2>
    <div class="stats">
      <div class="stat"><b>{total}</b><span>전체 대상</span></div>
      <div class="stat"><b>{kospi}</b><span>KOSPI</span></div>
      <div class="stat"><b>{kosdaq}</b><span>KOSDAQ</span></div>
      <div class="stat"><b>{len(finalists)}</b><span>최종 후보</span></div>
    </div>
  </div>

  <div class="panel">
    <h2>전체 {total}개사 (멀리 통과한 순)</h2>
    <table>
      <thead><tr>
        <th>회사</th><th>시장</th><th>결과</th>
        <th>부채비율</th><th>매출성장</th><th>영업이익률</th><th>영업현금흐름</th>
      </tr></thead>
      <tbody>{trs}</tbody>
    </table>
    <p class="legend"><b>색상</b>: <span style="color:var(--ok)">초록</span>=기준 통과 · <span style="color:var(--no)">빨강</span>=미달.
       재무 수치는 screener.db 최근 연도 기준. '결과'는 실제 4단계 파이프라인에서 탈락한 지점.</p>
  </div>
</div></body></html>"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="", help="결과 xlsx (기본: 최신 자동)")
    ap.add_argument("--db", default=DEFAULT_DB_PATH)
    ap.add_argument("--out", default="dashboard.html")
    args = ap.parse_args(argv[1:])

    xlsx = args.xlsx
    if not xlsx:
        cands = sorted(glob.glob("상장사_스크리너_결과_*.xlsx"), key=os.path.getmtime)
        if not cands:
            print("[!] 상장사_스크리너_결과_*.xlsx 없음. 먼저 run_listed_screener.py 실행.")
            return 1
        xlsx = cands[-1]

    print(f"입력: {xlsx}")
    html_out = build(xlsx, args.db)
    Path(args.out).write_text(html_out, encoding="utf-8")
    print(f"대시보드 생성: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
