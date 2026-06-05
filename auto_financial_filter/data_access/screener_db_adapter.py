"""
ScreenerDB adapter — 실제 상장사 재무 데이터 소스.

옆 프로젝트(dart-audit-extractor)의 screener.db(SQLite)를 **읽기 전용**으로 열어
실제 DART 재무제표(연 단위)를 가져온다. 가짜 생성기(WebScrapingFinancialAdapter)를
대체하는 진짜 데이터 통로다.

설계 원칙:
- dart-audit-extractor 폴더는 독립 프로젝트이므로 **절대 수정하지 않는다**(읽기 전용).
- 데이터는 연(年) 단위다. 분기 가정이 있는 기존 필터가 아니라
  annual_financial_filters.py의 연 단위 필터와 함께 사용한다.
- 누락 계정은 임의로 채우지 않고 0/None으로 두어 해당 조건에서 자연 탈락시킨다.
"""

from typing import List, Dict, Any, Optional
import sqlite3
import logging
from pathlib import Path

import pandas as pd

from ..models.base import StockSymbol, DataSourceAdapter
from ..config import FilterConfig

logger = logging.getLogger(__name__)

# 기본 DB 경로 (사용자 Windows 환경 기준). 테스트/타 환경에서는 db_path 인자로 덮어쓴다.
DEFAULT_DB_PATH = "D:/Agent_Project/dart-audit-extractor/screener.db"

# DB의 (계정) 이름 → 우리 필터가 쓰는 키 매핑
_ACCOUNT_MAP = {
    "매출액": "revenue",
    "영업이익": "operating_profit",
    "매출원가": "cogs",
    "당기순이익": "net_income",
    "자산총계": "total_assets",
    "부채총계": "total_debt",
    "자본총계": "total_equity",
    "영업활동현금흐름": "operating_cash_flow",
}

# corp_cls → StockSymbol.market (StockSymbol이 허용하는 값으로만 매핑)
def _cls_to_market(corp_cls: Optional[str]) -> str:
    if corp_cls == "Y":
        return "KOSPI"
    # K(코스닥)/N(코넥스)/E(기타) 등은 KOSDAQ로 근사 (StockSymbol 유효값 제약).
    return "KOSDAQ"


class ScreenerDBAdapter(DataSourceAdapter):
    """screener.db에서 실제 상장사 재무를 읽는 어댑터."""

    def __init__(self, config: FilterConfig, db_path: str = DEFAULT_DB_PATH):
        super().__init__(config)
        self.db_path = Path(db_path)
        self.retry_count = 0
        self._stock_to_corp: Dict[str, str] = {}
        self._corp_meta: Dict[str, Dict[str, Any]] = {}

    # --- DataSourceAdapter 인터페이스 ---
    def is_available(self) -> bool:
        return self.db_path.exists()

    def get_retry_count(self) -> int:
        return self.retry_count

    def _connect(self) -> sqlite3.Connection:
        # 읽기 전용(uri=ro)으로 열어 옆 프로젝트 DB를 보호한다.
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def _load_company_index(self, conn: sqlite3.Connection) -> None:
        """companies 테이블에서 stock_code↔corp_code 및 메타 캐싱."""
        if self._stock_to_corp:
            return
        rows = conn.execute(
            "SELECT corp_code, corp_name, stock_code, corp_cls FROM companies"
        ).fetchall()
        for corp_code, corp_name, stock_code, corp_cls in rows:
            if not stock_code:
                continue
            sc = str(stock_code).strip().zfill(6)
            self._stock_to_corp[sc] = corp_code
            self._corp_meta[corp_code] = {
                "corp_name": corp_name,
                "stock_code": sc,
                "corp_cls": corp_cls,
            }

    # --- 종목 목록 ---
    def get_listed_symbols(self, require_financials: bool = True) -> List[StockSymbol]:
        """
        상장사 StockSymbol 목록.
        require_financials=True면 financials에 실제 데이터가 있는 회사만 반환
        (현재 DB에는 파일럿 수집분만 존재).
        """
        if not self.is_available():
            raise RuntimeError(f"screener.db not found at {self.db_path}")

        with self._connect() as conn:
            self._load_company_index(conn)

            if require_financials:
                corp_codes = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT corp_code FROM financials"
                    ).fetchall()
                ]
            else:
                corp_codes = list(self._corp_meta.keys())

        symbols: List[StockSymbol] = []
        for corp_code in corp_codes:
            meta = self._corp_meta.get(corp_code)
            if not meta or not meta.get("stock_code"):
                continue
            name = (meta.get("corp_name") or "").strip() or meta["stock_code"]
            try:
                symbols.append(
                    StockSymbol(
                        code=meta["stock_code"],
                        name=name,
                        market=_cls_to_market(meta.get("corp_cls")),
                    )
                )
            except ValueError as e:
                logger.warning(f"Skipping invalid symbol {corp_code}: {e}")
        logger.info(
            f"ScreenerDB: {len(symbols)} listed symbols "
            f"({'with financials' if require_financials else 'all'})"
        )
        return symbols

    # --- 재무 데이터 ---
    def get_financial_statements(self, symbol: StockSymbol, years: int = 5) -> Dict[str, Any]:
        """
        해당 종목의 연 단위 재무를 반환.
        반환 형식:
            {'symbol': code, 'annual_data': [ {year, revenue, ...}, ... ]}  # 연도 오름차순
        연결(CFS) 우선, 없으면 별도(OFS).
        """
        if not self.is_available():
            raise RuntimeError(f"screener.db not found at {self.db_path}")

        with self._connect() as conn:
            self._load_company_index(conn)
            corp_code = self._stock_to_corp.get(str(symbol.code).strip().zfill(6))
            if corp_code is None:
                raise ValueError(f"corp_code not found for stock {symbol.code}")

            rows = conn.execute(
                "SELECT bsns_year, fs_div, 계정, 값 FROM financials WHERE corp_code=?",
                (corp_code,),
            ).fetchall()

        if not rows:
            raise ValueError(f"No financial data in DB for {symbol.code} ({symbol.name})")

        # (year, fs_div) -> {key: value}
        buckets: Dict[tuple, Dict[str, float]] = {}
        for bsns_year, fs_div, account, value in rows:
            key = _ACCOUNT_MAP.get(account)
            if key is None:
                continue
            buckets.setdefault((int(bsns_year), fs_div), {})[key] = float(value)

        # 연도별로 연결(CFS) 우선 선택
        years_avail = sorted({y for (y, _div) in buckets.keys()})
        annual_data: List[Dict[str, Any]] = []
        for y in years_avail:
            chosen = None
            if (y, "CFS") in buckets:
                chosen = buckets[(y, "CFS")]
            elif (y, "OFS") in buckets:
                chosen = buckets[(y, "OFS")]
            else:
                # 그 외 구분이 있으면 첫 번째
                for (yy, _div), v in buckets.items():
                    if yy == y:
                        chosen = v
                        break
            if not chosen:
                continue

            total_debt = chosen.get("total_debt", 0.0)
            total_equity = chosen.get("total_equity", 0.0)
            debt_ratio = (total_debt / total_equity * 100) if total_equity > 0 else 999.0

            annual_data.append({
                "year": y,
                "revenue": chosen.get("revenue", 0.0),
                "operating_profit": chosen.get("operating_profit", 0.0),
                "cogs": chosen.get("cogs", 0.0),
                "net_income": chosen.get("net_income", 0.0),
                "total_assets": chosen.get("total_assets", 0.0),
                "total_debt": total_debt,
                "total_equity": total_equity,
                "operating_cash_flow": chosen.get("operating_cash_flow", 0.0),
                "debt_ratio": debt_ratio,
            })

        annual_data = annual_data[-years:] if years else annual_data
        return {"symbol": symbol.code, "annual_data": annual_data}
