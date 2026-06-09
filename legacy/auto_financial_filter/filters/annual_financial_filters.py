"""
연 단위(annual) 재무 필터 — 실제 DART 데이터(screener.db)용.

기존 분기용 필터(financial_health_filter.py / quality_growth_filter.py)는
8분기·16분기를 요구하므로 연 데이터(회사당 최대 3~5년)로는 돌릴 수 없다.
이 모듈은 재무선배 기준을 **연 단위**에 맞게 재정의한 필터다.

데이터 입력: data_manager.get_financial_data(symbol)['annual_data']
  = [ {year, revenue, operating_profit, cogs, total_debt, total_equity,
       operating_cash_flow, debt_ratio, ...}, ... ]  (연도 오름차순)

분기→연 단위 기준 재정의(투명하게 명시):
- 매출성장: 최근 연도 vs 직전 연도 (YoY)
- 현금흐름: 보유 연도 전부 양수 OR 누적 양수
- 이익 피크: 최근 연도 영업이익이 보유 연도 중 최고
- 매출원가율 추세: 최근 연도가 가장 이른 연도보다 낮음(개선) OR 후반 평균 < 전반 평균
"""

from typing import List, Dict, Any
import logging

from ..models.base import StockSymbol, FilterResult, BaseFilter
from ..config import FilterConfig

logger = logging.getLogger(__name__)


def _get_annual(data_manager, symbol: StockSymbol) -> List[Dict[str, Any]]:
    """data_manager에서 연 단위 데이터 리스트를 안전하게 추출."""
    fd = data_manager.get_financial_data(symbol)
    if isinstance(fd, dict):
        return fd.get("annual_data", []) or []
    return []


class AnnualFinancialHealthFilter(BaseFilter):
    """2단계(연 단위): 부채비율 · 매출성장(YoY) · 영업현금흐름."""

    def __init__(self, config: FilterConfig, data_manager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)

    def get_stage_name(self) -> str:
        return "Financial Health Filter (Annual)"

    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        passed, failed = [], []
        criteria = {
            "max_debt_ratio_percent": self.config.max_debt_ratio_percent,
            "min_revenue_growth_percent": self.config.min_revenue_growth_percent,
            "basis": "annual",
        }
        for symbol in symbols:
            try:
                annual = _get_annual(self.data_manager, symbol)
                if not annual:
                    failed.append(symbol)
                    self.logger.debug(f"FAIL {symbol.code}: no annual data")
                    continue
                if self._passes(annual, symbol):
                    passed.append(symbol)
                else:
                    failed.append(symbol)
            except Exception as e:
                self.logger.warning(f"Error {symbol.code}: {e}")
                failed.append(symbol)
        self.logger.info(
            f"[Annual FH] {len(passed)} passed / {len(failed)} failed"
        )
        return FilterResult(passed, failed, self.get_stage_name(), criteria)

    def _passes(self, annual: List[Dict[str, Any]], symbol: StockSymbol) -> bool:
        latest = annual[-1]

        # 1) 부채비율
        debt_ratio = latest.get("debt_ratio", 999.0)
        if debt_ratio >= self.config.max_debt_ratio_percent:
            self.logger.debug(
                f"FAIL {symbol.code}: debt {debt_ratio:.0f}% >= "
                f"{self.config.max_debt_ratio_percent}%"
            )
            return False

        # 2) 매출성장 (YoY) — 직전 연도 필요
        if len(annual) >= 2:
            prev_rev = annual[-2].get("revenue", 0.0)
            cur_rev = latest.get("revenue", 0.0)
            if prev_rev > 0:
                growth = (cur_rev - prev_rev) / prev_rev * 100
                if growth < self.config.min_revenue_growth_percent:
                    self.logger.debug(
                        f"FAIL {symbol.code}: rev growth {growth:.1f}% < "
                        f"{self.config.min_revenue_growth_percent}%"
                    )
                    return False
        elif self.config.min_revenue_growth_percent > 0:
            # 성장 검증 불가(연도 1개)인데 성장 요구가 있으면 보수적으로 탈락
            self.logger.debug(f"FAIL {symbol.code}: only 1 year, cannot verify growth")
            return False

        # 3) 영업현금흐름 — 전부 양수 OR 누적 양수
        ocfs = [a.get("operating_cash_flow", 0.0) for a in annual]
        if not (all(x > 0 for x in ocfs) or sum(ocfs) > 0):
            self.logger.debug(f"FAIL {symbol.code}: OCF unhealthy {ocfs}")
            return False

        return True


class AnnualQualityGrowthFilter(BaseFilter):
    """3단계(연 단위): 영업이익률 · 이익 피크 · 매출원가율 추세."""

    def __init__(self, config: FilterConfig, data_manager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)

    def get_stage_name(self) -> str:
        return "Quality Growth Filter (Annual)"

    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        passed, failed = [], []
        criteria = {
            "min_operating_margin_percent": self.config.min_operating_margin_percent,
            "checks": "operating_margin + profit_peak + cogs_trend",
            "basis": "annual",
        }
        for symbol in symbols:
            try:
                annual = _get_annual(self.data_manager, symbol)
                if not annual:
                    failed.append(symbol)
                    continue
                if self._passes(annual, symbol):
                    passed.append(symbol)
                else:
                    failed.append(symbol)
            except Exception as e:
                self.logger.warning(f"Error {symbol.code}: {e}")
                failed.append(symbol)
        self.logger.info(
            f"[Annual QG] {len(passed)} passed / {len(failed)} failed"
        )
        return FilterResult(passed, failed, self.get_stage_name(), criteria)

    def _passes(self, annual: List[Dict[str, Any]], symbol: StockSymbol) -> bool:
        latest = annual[-1]
        rev = latest.get("revenue", 0.0)
        if rev <= 0:
            self.logger.debug(f"FAIL {symbol.code}: no revenue")
            return False

        # 1) 영업이익률
        opm = latest.get("operating_profit", 0.0) / rev * 100
        if opm < self.config.min_operating_margin_percent:
            self.logger.debug(
                f"FAIL {symbol.code}: OPM {opm:.1f}% < "
                f"{self.config.min_operating_margin_percent}%"
            )
            return False

        # 2) 이익 피크 — 최근 연도 영업이익이 보유 연도 중 최고
        op_profits = [a.get("operating_profit", 0.0) for a in annual]
        if latest.get("operating_profit", 0.0) < max(op_profits):
            self.logger.debug(f"FAIL {symbol.code}: not profit peak {op_profits}")
            return False

        # 3) 매출원가율 추세 (하락=개선)
        cogs_ratios = [
            (a.get("cogs", 0.0) / a.get("revenue", 0.0))
            for a in annual
            if a.get("revenue", 0.0) > 0
        ]
        if len(cogs_ratios) >= 2:
            recent_vs_oldest = cogs_ratios[-1] < cogs_ratios[0]
            mid = len(cogs_ratios) // 2
            first_avg = sum(cogs_ratios[:mid or 1]) / (mid or 1)
            second_avg = sum(cogs_ratios[mid:]) / (len(cogs_ratios) - mid)
            if not (recent_vs_oldest or second_avg < first_avg):
                self.logger.debug(f"FAIL {symbol.code}: COGS ratio not improving {cogs_ratios}")
                return False

        return True
