# -*- coding: utf-8 -*-
"""로컬 인터랙티브 스크리너 — 기준을 직접 조절하며 '통과 종목'을 즉시 확인.

기존 production(engine.py·run_*.py)은 '고정 기준'으로 통과 종목을 대시보드 HTML로
굽는다. 이 앱은 같은 엔진·같은 데이터를 쓰되, 기준(Criteria)을 슬라이더로 바꿔가며 통과
목록이 어떻게 달라지는지를 내 PC에서 실시간 탐색하는 도구.

설계 핵심:
  - 지표(compute)·시세는 시장·시점당 '고정' → 시장당 한 번만 계산해 캐시(@st.cache_data).
  - 슬라이더가 바꾸는 건 Criteria뿐 → 매 조작마다 engine.screen()만 재호출(즉시 반응).
  - 시세는 market_cache.db의 마지막 스냅샷을 읽어 오프라인·즉시 구동(인터넷 불필요).
  - engine.py는 건드리지 않음(세 시장 production의 단일 출처 보존). 통과 종목만 표시.
  - 이익피크 요구·TTM영업현금>0은 항상 적용(v1, A안). 두 토글은 다음 확장에서.

실행: streamlit run app.py     (최초 1회: pip install streamlit pandas)
"""
from dataclasses import replace
from pathlib import Path
import os
import sqlite3
import json

import pandas as pd
import streamlit as st

from engine import (DB, KR_CRITERIA, US_CRITERIA,
                    load_company, compute, add_valuation, screen,
                    debt_ratio_display, TRADING_AVG_DAYS)
import market_cache

DATA = "D:/Agent_Project/dart-audit-extractor/data"

# 시장별 설정: 명단·시세캐시키·기준 프로파일. 통화·식별자 차이는 kind(KR/US)로 분기.
MARKETS = {
    "코스피":      dict(kind="KR", cache="KOSPI",  base=KR_CRITERIA, idx=[f"{DATA}/kospi_index.json"]),
    "코스닥":      dict(kind="KR", cache="KOSDAQ", base=KR_CRITERIA, idx=[f"{DATA}/kosdaq_index.json"]),
    "미국 S&P500": dict(kind="US", cache="US",     base=US_CRITERIA, idx=[f"{DATA}/us_index.json"]),
    "미국 전체":   dict(kind="US", cache="US",     base=US_CRITERIA,
                       idx=[f"{DATA}/us_index.json", f"{DATA}/us_liquid_index.json"]),
}


# ── 데이터 로딩 (시장당 1회, 캐시) ───────────────────────────────────────────
def _trim_recent(d, n_q):
    """미국 이력창 절단(engine.US_CRITERIA.recent_quarters와 동일 의미). 0이면 제한 없음."""
    if not d or n_q <= 0 or len(d["qkeys"]) <= n_q:
        return d
    qk = d["qkeys"][-n_q:]
    return {**d, "quarters": {k: d["quarters"][k] for k in qk}, "qkeys": qk}


def _data_version():
    """DB 파일들의 수정시각 → 디스크 캐시 키. 재무 재수집·시세 갱신(run_*.py 실행)으로
    screener.db / market_cache.db가 바뀌면 키가 달라져 캐시가 자동 무효화·재계산된다."""
    out = []
    for p in (DB, str(market_cache.DB)):
        try:
            out.append(f"{p}:{os.path.getmtime(p)}")
        except OSError:
            pass
    return "|".join(out)


@st.cache_data(show_spinner="재무·시세 불러오는 중…", persist="disk")
def load_universe(market, data_version):
    """대상 명단 × financials_q × market_cache 스냅샷을 결합해 종목별 지표를 한 번 계산.
    반환: (rows, asof_date). rows = [{name, code, sector, m, md}]. 기준과 무관(고정)."""
    cfg = MARKETS[market]
    base = cfg["base"]
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    have = {r[0] for r in conn.execute("SELECT DISTINCT corp_code FROM financials_q")}

    uni, seen = [], set()
    for p in cfg["idx"]:
        for c in json.loads(Path(p).read_text(encoding="utf-8")):
            if cfg["kind"] == "KR":               # 식별자=corp_code, 시세키=종목코드(zfill6)
                code = c["corp_code"]
                if code in seen:
                    continue
                seen.add(code)
                uni.append(dict(corp=code, name=c.get("corp_name", ""),
                                tk=str(c.get("stock_code", "")).zfill(6), sector=""))
            else:                                  # 미국: 식별자=CIK, 시세키=ticker
                code = c["cik"]
                if code in seen:
                    continue
                seen.add(code)
                uni.append(dict(corp=code, name=c.get("name", ""),
                                tk=c["ticker"], sector=c.get("sector", "")))

    mdmap = market_cache.load_latest(cfg["cache"])
    rows, asof = [], set()
    for u in uni:
        if u["corp"] not in have:
            continue
        d = _trim_recent(load_company(conn, u["corp"]), base.recent_quarters)
        m = compute(d) if d else None
        if not m:                                  # 4분기 미만 등 지표 산출 불가 → 제외
            continue
        md = mdmap.get(u["tk"], {})
        add_valuation(m, md.get("marcap"))         # 시총 있으면 PER/PBR/PSR 채움(미국 캐시는 대개 None)
        if md.get("asof"):
            asof.add(md["asof"])
        rows.append(dict(name=u["name"], code=u["tk"], sector=u["sector"], m=m, md=md))
    conn.close()
    return rows, (max(asof) if asof else None)


def passing(rows, crit):
    """현재 기준(crit)으로 3단계(유동성·재무건전·품질성장) 모두 통과한 종목만."""
    out = []
    for r in rows:
        st_ = screen(r["m"], r["md"].get("amount"), crit)
        if st_["liquidity"] and st_["financial"] and st_["quality"]:
            out.append(r)
    return out


# ── 표시 포맷 (통화 인지) ────────────────────────────────────────────────────
def f_money(v, kind):
    if v is None:
        return "—"
    a = abs(v)
    if kind == "KR":
        return f"{v/1e12:.1f}조" if a >= 1e12 else f"{v/1e8:,.0f}억"
    return f"${v/1e9:.1f}B" if a >= 1e9 else (f"${v/1e6:,.0f}M" if a >= 1e6 else f"${v:,.0f}")


def f_price(v, kind):
    if v is None:
        return "—"
    return f"{v:,.0f}원" if kind == "KR" else f"${v:,.2f}"


def f_pct(v):
    return "—" if v is None else f"{v:.1f}%"


def f_mult(v, d=1):
    return "—" if v is None else f"{v:.{d}f}배"


# ── 사이드바: 기준 조절(7개 노브) ────────────────────────────────────────────
def criteria_controls(market):
    """슬라이더/토글 → Criteria 프로파일. 위젯 키에 market을 포함해 시장 전환 시 자동 초기화."""
    cfg = MARKETS[market]
    base = cfg["base"]
    kind = cfg["kind"]
    k = lambda s: f"{market}_{s}"

    st.sidebar.markdown("### 기준 조절")
    st.sidebar.caption("처음엔 기본 기준값. 움직이면 통과 목록이 즉시 바뀜.")

    if kind == "KR":
        trade = st.sidebar.slider("거래대금 하한 (억원)", 0, 500, int(base.min_trading / 1e8), 10,
                                  key=k("trade"), help=f"최근 {TRADING_AVG_DAYS}거래일 평균 일거래대금이 이 값 이상") * 1e8
    else:
        trade = st.sidebar.slider("거래대금 하한 ($M)", 0, 500, int(base.min_trading / 1e6), 5,
                                  key=k("trade"), help=f"최근 {TRADING_AVG_DAYS}거래일 평균 달러 거래대금이 이 값 이상") * 1e6

    debt = st.sidebar.slider("부채비율 상한 (%)", 0, 500, int(base.max_debt), 10,
                             key=k("debt"), help="부채비율이 이 값 '미만'이어야 통과")
    grow = st.sidebar.slider("매출성장 YoY 하한 (%)", -20, 100, int(base.min_growth_yoy), 5,
                             key=k("grow"), help="같은 분기 전년 대비 매출 증가율이 이 값 이상")
    opm = st.sidebar.slider("영업이익률(TTM) 하한 (%)", 0, 50, int(base.min_op_margin), 1,
                            key=k("opm"), help="최근 4분기 합 기준 영업이익률이 이 값 이상")
    peak = st.sidebar.slider("이익피크 최소 이력 (분기)", 0, 20, int(base.min_peak_quarters), 1,
                             key=k("peak"),
                             help="이력이 이 분기 수 이상일 때만 '이익피크'를 인정(짧은 이력의 거짓 피크 차단). 0=제한 없음")

    cogs = st.sidebar.checkbox("원가율 개선 요구", base.require_cogs_improving, key=k("cogs"),
                               help="최근 원가율이 과거보다 낮아졌을 것")
    negeq = st.sidebar.checkbox("음수자본 허용 (이익잉여금>0)", base.allow_neg_equity_if_retained, key=k("negeq"),
                                help="자본총계가 음수여도 이익잉여금>0이면 통과(자사주매입 우량주)")

    st.sidebar.caption("ⓘ 이익피크 요구·TTM영업현금>0은 항상 적용(v1). on/off 토글은 다음 확장에서.")
    if st.sidebar.button("기준 기본값으로 복원", use_container_width=True):
        for s in ("trade", "debt", "grow", "opm", "peak", "cogs", "negeq"):
            st.session_state.pop(k(s), None)
        st.rerun()

    return replace(base, min_trading=trade, max_debt=float(debt), min_growth_yoy=float(grow),
                   min_op_margin=float(opm), min_peak_quarters=int(peak),
                   require_cogs_improving=cogs, allow_neg_equity_if_retained=negeq)


# ── 결과 표현: 카드 / 목록 ───────────────────────────────────────────────────
def chip(label, val, hi=False):
    cls = "chip hi" if hi else "chip"
    return f'<div class="{cls}"><span>{label}</span><b>{val}</b></div>'


def cards_html(rows, kind):
    cells = []
    for r in rows:
        m, md = r["m"], r["md"]
        chgs = ""
        if md.get("chg") is not None:
            col = "#2DB400" if md["chg"] > 0 else ("#F04452" if md["chg"] < 0 else "#8B95A1")
            chgs = f'<span style="color:{col};font-size:12px;font-weight:600"> {md["chg"]:+.1f}%</span>'
        sub = r["code"] + (f' · {r["sector"]}' if r["sector"] else "") + f' · 시총 {f_money(md.get("marcap"), kind)}'
        cells.append(
            '<div class="card">'
            f'<div class="cname">{r["name"]}</div>'
            f'<div class="csub">{sub}</div>'
            '<div class="cgrid">'
            + chip("현재가", f_price(md.get("close"), kind) + chgs)
            + chip("영업이익률(TTM)", f_pct(m["op_margin"]), hi=True)
            + chip("매출성장(YoY)", f_pct(m["rev_yoy"]), hi=True)
            + chip("부채비율", f_pct(debt_ratio_display(m)))
            + chip("거래대금", f_money(md.get("amount"), kind))
            + chip("PER", f_mult(m.get("per")))
            + chip("PBR", f_mult(m.get("pbr"), 2))
            + chip("PSR", f_mult(m.get("psr"), 2))
            + "</div></div>")
    return '<div class="cards">' + "".join(cells) + "</div>"


def list_df(rows, kind):
    recs = []
    for r in rows:
        m, md = r["m"], r["md"]
        rec = {"회사": r["name"], "코드": r["code"]}
        if kind == "US":
            rec["섹터"] = r["sector"]
        rec["현재가"] = md.get("close")
        rec["등락률"] = md.get("chg")
        rec["영업이익률"] = m["op_margin"]
        rec["매출성장"] = m["rev_yoy"]
        rec["부채비율"] = debt_ratio_display(m)
        amt, mc = md.get("amount"), md.get("marcap")
        if kind == "KR":
            rec["거래대금(억)"] = amt / 1e8 if amt else None
            rec["시총(억)"] = mc / 1e8 if mc else None
        else:
            rec["거래대금($M)"] = amt / 1e6 if amt else None
            rec["시총($B)"] = mc / 1e9 if mc else None
        rec["PER"] = m.get("per")
        rec["PBR"] = m.get("pbr")
        recs.append(rec)
    df = pd.DataFrame(recs)

    num = st.column_config.NumberColumn
    cfg = {
        "현재가": num(format="%.2f" if kind == "US" else "%.0f"),
        "등락률": num(format="%.1f%%"),
        "영업이익률": num(format="%.1f%%"),
        "매출성장": num(format="%.1f%%"),
        "부채비율": num(format="%.0f%%"),
        "PER": num(format="%.1f"),
        "PBR": num(format="%.2f"),
    }
    if kind == "KR":
        cfg["거래대금(억)"] = num(format="%.0f")
        cfg["시총(억)"] = num(format="%.0f")
    else:
        cfg["거래대금($M)"] = num(format="%.0f")
        cfg["시총($B)"] = num(format="%.1f")
    return df, cfg


SORTS = {
    "시총 큰 순": lambda r: -(r["md"].get("marcap") or 0),
    "영업이익률 높은 순": lambda r: -(r["m"].get("op_margin") or 0),
    "매출성장 높은 순": lambda r: -(r["m"].get("rev_yoy") or 0),
    "거래대금 많은 순": lambda r: -(r["md"].get("amount") or 0),
}


# ── CSS (토스 스타일 보강: 폰트·카드·헤더) ──────────────────────────────────
CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
html, body, [class*="css"], .stMarkdown, button, input { font-family: 'Pretendard', -apple-system, 'Malgun Gothic', sans-serif; }
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 1180px; }
.hd h1 { font-size: 26px; font-weight: 800; color: #191F28; margin: 0; letter-spacing: -0.4px; }
.hd p { color: #8B95A1; font-size: 14px; margin: 4px 0 6px; }
.cnt { font-size: 15px; color: #4E5968; margin: 6px 0 18px; font-weight: 600; }
.cnt b { color: #3182F6; font-size: 22px; font-weight: 800; margin: 0 2px; }
.cnt span { color: #8B95A1; font-size: 13px; font-weight: 500; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(264px, 1fr)); gap: 16px; margin-top: 4px; }
.card { background: #fff; border: 1px solid #F2F4F6; border-radius: 20px; padding: 20px 22px;
        box-shadow: 0 1px 4px rgba(0,0,0,.05); transition: box-shadow .15s, transform .15s; }
.card:hover { box-shadow: 0 6px 18px rgba(49,130,246,.12); transform: translateY(-2px); }
.cname { font-size: 18px; font-weight: 700; color: #191F28; letter-spacing: -0.3px; }
.csub { font-size: 12px; color: #8B95A1; margin: 4px 0 16px; }
.cgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px 14px; }
.chip span { display: block; font-size: 11px; color: #8B95A1; margin-bottom: 3px; }
.chip b { font-size: 15px; color: #333D4B; font-weight: 700; }
.chip.hi b { color: #3182F6; }
section[data-testid="stSidebar"] { border-right: 1px solid #F2F4F6; }
section[data-testid="stSidebar"] h3 { color: #191F28; font-weight: 800; }
</style>
"""


# ── 메인 ────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="재무 스크리너", page_icon="📈", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="hd"><h1>📈 재무 스크리너</h1>'
                '<p>기준을 직접 조절하며 통과 종목을 바로 확인 · 내 PC 로컬 · 통과 종목만 표시</p></div>',
                unsafe_allow_html=True)

    market = st.radio("시장", list(MARKETS), horizontal=True, label_visibility="collapsed")
    kind = MARKETS[market]["kind"]

    crit = criteria_controls(market)
    rows, asof = load_universe(market, _data_version())
    hits = passing(rows, crit)

    c1, c2, c3 = st.columns([2, 2, 3])
    view = c1.radio("보기", ["카드", "목록"], horizontal=True, label_visibility="collapsed")
    sort = c2.selectbox("정렬", list(SORTS), label_visibility="collapsed")
    # 미국은 시세가 무거워 자동 갱신 대신 수동 버튼(한국은 .bat 실행 시 자동 갱신).
    if kind == "US" and c3.button("🔄 시세 새로고침", use_container_width=True,
                                  help="미국 현재가·거래대금을 최근 거래일 EOD로 다시 받아옵니다(수천 종목, 수 분 소요)"):
        import refresh_prices
        with st.spinner("미국 시세 새로고침 중… (수천 종목, 수 분 소요)"):
            status, pdate, n = refresh_prices.refresh_us([r["code"] for r in rows])
        if status == "updated":
            st.success(f"갱신 완료 · {n}종목 · 기준일 {pdate}")
            st.rerun()                              # market_cache.db 변경 → _data_version 키 바뀜 → 재계산
        else:
            st.error("시세 새로고침 실패 — 잠시 후 다시 시도해 주세요.")
    hits = sorted(hits, key=SORTS[sort])

    st.markdown(
        f'<div class="cnt">현재 기준 통과 <b>{len(hits)}</b>개'
        f'<span> · 대상 {len(rows)}개사 · 시세 {asof or "—"} 기준</span></div>',
        unsafe_allow_html=True)

    if not hits:
        st.info("현재 기준을 통과한 종목이 없습니다. 사이드바에서 기준을 완화해 보세요.")
    elif view == "카드":
        st.markdown(cards_html(hits, kind), unsafe_allow_html=True)
    else:
        df, colcfg = list_df(hits, kind)
        st.dataframe(df, use_container_width=True, hide_index=True, column_config=colcfg)


if __name__ == "__main__":
    main()
