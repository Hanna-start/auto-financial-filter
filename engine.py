#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공유 엔진 — 분기 재무 적재·환산·지표계산·필터 기준 (시장 무관).

세 시장(코스피·코스닥·미국) 스크리너의 공통 코어. run_*.py는 이 엔진을 import하고
시장별 부분(시세 출처, 통화 표시, 거래대금 기준)만 각자 둔다.

★ 필터 기준의 단일 출처 ★
  - 비율 기준(부채비율·매출성장·영업이익률)과 게이트 screen()이 여기 1벌 →
    기준을 바꾸려면 이 파일만 수정하면 세 시장에 일괄 반영.
  - 거래대금 기준만 시장별 통화(원/달러)라 run 스크립트에 두고 screen()에 인자로 넘긴다.

흐름:
  - load_company: financials_q → 누적차감으로 순수 분기 환산(Q2=반기-1Q, Q4=연간-3Q).
  - compute    : TTM(최근 4분기 합)=규모·이익률, YoY(같은 분기 전년)=성장,
                 이익피크·원가율개선·TTM영업현금.
  - add_valuation: 시총 결합 PER/PBR/PSR(표시용, 필터 아님).
  - screen     : 3단계(유동성·재무건전·품질성장) 통과 여부.
"""

from dataclasses import dataclass

DB = "D:/Agent_Project/dart-audit-extractor/screener.db"

# === 공통 기본 임계 (= 국내 '재무선배' 엄격 기준) ===
MAX_DEBT = 200.0                  # 부채비율 % (미만)
MIN_GROWTH_YOY = 10.0             # 매출성장 YoY % (이상)
MIN_OP_MARGIN = 10.0              # TTM 영업이익률 % (이상)
# 밸류에이션 배수 상한: 초과 시 분모(순이익·자본·매출)가 0에 가깝거나 결측이라 생긴
# 비정상값(예: PER 수천~수백만배)으로 보고 표시에서 제외('—'). 정상 고PER(수백배)은 보존. KR·US 공통.
RATIO_MAX = 1000.0


@dataclass(frozen=True)
class Criteria:
    """시장별 선별 기준 프로파일. 한국/미국을 독립적으로 조정하기 위한 이원화 단위.
    문서: 기준_국내.md / 기준_미국.md. 게이트 적용은 screen(m, trading, criteria).
    기본값 = 국내 기준(원래 '재무선배' 엄격). 미국은 시장 특성에 맞춰 일부 토글."""
    min_trading: float                  # 거래대금 하한 (시장 통화: KR=원, US=달러)
    recent_quarters: int = 0            # 이력 절단 분기수(0=제한없음). 미국=20(최근5년).
    max_debt: float = MAX_DEBT          # 부채비율 % (미만)
    min_growth_yoy: float = MIN_GROWTH_YOY
    min_op_margin: float = MIN_OP_MARGIN
    require_cogs_improving: bool = True  # ⑦ 원가율 개선 요구. 미국=False(SW 비중 커 무의미→마진·이익에 위임)
    allow_neg_equity_if_retained: bool = False  # ⑧ 음수자본 허용 조건. 미국=True:
    #     자본>0 OR (자본<0 AND 이익잉여금>0). 자사주매입 우량주(맥도날드류)는 통과,
    #     누적적자(진짜 자본잠식)는 탈락 → 부채비율<200%의 음수자본 허점도 동시에 차단.
    min_peak_quarters: int = 0          # ⑥ 이익피크 판정에 요구하는 최소 분기 이력. 미국=16
    #     (EDGAR 이력 완결성이 종목마다 달라, 짧은 이력의 거짓 피크 통과 방지)


KR_CRITERIA = Criteria(min_trading=10_000_000_000)                    # 국내: 거래대금 100억원, 원래 기준 그대로
US_CRITERIA = Criteria(min_trading=30_000_000, recent_quarters=20,    # 미국: 거래대금 $30M, 최근 5년
                       require_cogs_improving=False,                  #   원가율 제외
                       allow_neg_equity_if_retained=True,             #   음수자본+이익잉여금>0 허용
                       min_peak_quarters=16)                          #   피크 판정 16분기 이력 요구

ACCT = {"매출액": "revenue", "영업이익": "op", "매출원가": "cogs",
        "영업활동현금흐름": "ocf", "당기순이익": "net",
        "부채총계": "debt", "자본총계": "equity", "자산총계": "assets",
        "이익잉여금": "retained"}   # ⑧ 음수자본 원인 판별용(미국). 없으면 None.
FLOW = {"revenue", "op", "cogs", "ocf", "net"}
STOCK = {"debt", "equity", "assets", "retained"}
REPRT_ORDER = ["11013", "11012", "11014", "11011"]   # Q1,H1,9M,FY


def REPRT_NM(r):
    return {"11013": "1Q", "11012": "2Q(반기)", "11014": "3Q", "11011": "4Q(연간)"}.get(r, r)


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


def compute(d):
    q, qk, bs = d["quarters"], d["qkeys"], d["bs"]
    if len(qk) < 4:
        return None
    last4 = qk[-4:]

    def ttm(key):
        vals = [q[k].get(key) for k in last4]
        return sum(vals) if all(v is not None for v in vals) else None

    ttm_rev, ttm_op, ttm_cogs, ttm_ocf = ttm("revenue"), ttm("op"), ttm("cogs"), ttm("ocf")
    ttm_net = ttm("net")
    m = {
        "fs": d["fs"], "n_q": len(qk), "latest_q": f"{qk[-1][0]} {qk[-1][1]}Q",
        "ttm_revenue": ttm_rev, "ttm_op": ttm_op, "ttm_ocf": ttm_ocf, "ttm_net": ttm_net,
        "equity": bs.get("equity"), "retained": bs.get("retained"),
        "op_margin": (ttm_op / ttm_rev * 100) if (ttm_rev and ttm_op is not None) else None,
        "debt_ratio": (bs["debt"] / bs["equity"] * 100) if (bs.get("equity") and bs.get("debt") is not None) else None,
        "bs_asof": bs.get("asof"),
        # 밸류에이션은 시총이 필요 → main 루프에서 add_valuation()이 채움
        "per": None, "pbr": None, "psr": None, "p_op": None,
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


def add_valuation(m, marcap):
    """시총과 재무를 결합한 밸류에이션 지표를 m에 채운다(필터 아님, 참고용).
    PER=시총/TTM순이익, PBR=시총/자본총계, PSR=시총/TTM매출, 시총/TTM영업이익.
    분모가 0·음수·없음이면 None(적자·미달은 '—'로 표기)."""
    if not m or not marcap:
        return
    def ratio(denom):
        r = (marcap / denom) if (denom is not None and denom > 0) else None
        return None if (r is not None and r > RATIO_MAX) else r   # 비정상 배수(분모 미세) 제외
    m["per"] = ratio(m.get("ttm_net"))
    m["pbr"] = ratio(m.get("equity"))
    m["psr"] = ratio(m.get("ttm_revenue"))
    m["p_op"] = ratio(m.get("ttm_op"))


def debt_ratio_display(m):
    """표시용 부채비율. 음수자본(equity<0)이면 debt/equity가 음수(예: -150%)로 나와 혼동되므로
    None('—')으로 가린다. 필터 판정(screen)은 원래 m['debt_ratio']로 그대로 수행 — 표시만 가린다.
    (음수자본+이익잉여금>0 우량주가 음수 부채비율로 <200% 게이트를 통과하는 것은 의도된 동작.)"""
    if not m:
        return None
    dr = m.get("debt_ratio")
    if dr is None or (m.get("equity") is not None and m["equity"] < 0):
        return None
    return dr


def equity_ok(m, c):
    """⑧ 자본 게이트. 기본: 자본총계>0. 미국(allow_neg_equity_if_retained): 음수자본이어도
    이익잉여금>0이면 통과(자사주매입 우량주) / 이익잉여금≤0(누적적자)이면 탈락."""
    if not m or m.get("equity") is None:
        return False
    if m["equity"] > 0:
        return True
    if c.allow_neg_equity_if_retained:
        return m.get("retained") is not None and m["retained"] > 0
    return False


def screen(m, trading, c):
    """단계별 통과 여부. c=Criteria 프로파일(KR_CRITERIA/US_CRITERIA — 시장별 이원화).
    반환: dict(stage->bool)."""
    liq = trading is not None and trading >= c.min_trading
    fh = (m and equity_ok(m, c)
          and m["debt_ratio"] is not None and m["debt_ratio"] < c.max_debt
          and m["rev_yoy"] is not None and m["rev_yoy"] >= c.min_growth_yoy
          and m["ttm_ocf_ok"])
    # ⑥ 피크: 이력이 min_peak_quarters 이상일 때만 유효(짧은 이력의 거짓 피크 배제)
    peak_ok = bool(m) and m["is_peak"] and m["n_q"] >= c.min_peak_quarters
    qg = (m and m["op_margin"] is not None and m["op_margin"] >= c.min_op_margin
          and peak_ok
          and (m["cogs_improving"] if c.require_cogs_improving else True))  # ⑦ US는 원가율 면제
    return {"liquidity": bool(liq), "financial": bool(fh), "quality": bool(qg)}
