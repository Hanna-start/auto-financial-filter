#!/usr/bin/env python3
"""
상장사 스크리너 — 실제 데이터(하이브리드) 실행 진입점.

데이터 소스:
  - 1·4단계(유동성·모멘텀): yfinance 실시간 주가/거래량
  - 2·3단계(재무건전성·품질성장): dart-audit-extractor의 screener.db (실제 DART 재무, 연 단위)

가짜 데이터 생성기를 쓰지 않는다. 이 스크립트가 '진짜 필터'의 정식 실행 통로다.

사용:
  py run_listed_screener.py
  py run_listed_screener.py --db "D:/Agent_Project/dart-audit-extractor/screener.db"
"""

import sys
import io
import argparse
import logging
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.data_access.hybrid_manager import HybridDataAccessManager
from auto_financial_filter.data_access.screener_db_adapter import DEFAULT_DB_PATH
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.annual_financial_filters import (
    AnnualFinancialHealthFilter,
    AnnualQualityGrowthFilter,
)
from auto_financial_filter.filters.momentum_filter import MomentumFilter
from auto_financial_filter.utils.export import DataExporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def build_config() -> FilterConfig:
    return FilterConfig(
        min_trading_volume_krw=5_000_000_000,   # 50억 KRW (유동성)
        trading_volume_period_days=30,
        max_debt_ratio_percent=200.0,           # 부채비율 200% 이하
        min_revenue_growth_percent=0.0,         # 역성장 배제 (YoY 0% 이상)
        min_operating_margin_percent=5.0,       # 영업이익률 5% 이상
        verbose_output=True,
        log_level="INFO",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="상장사 실데이터 스크리너 (하이브리드)")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="screener.db 경로")
    parser.add_argument("--all", action="store_true",
                        help="재무 미수집 회사까지 전체 목록 사용(현재는 권장 안 함)")
    parser.add_argument("--no-price", action="store_true",
                        help="가격 단계(1·4) 생략하고 재무 2·3단계만 실행")
    args = parser.parse_args()

    print("🚀 상장사 스크리너 — 실제 데이터(하이브리드: yfinance + screener.db)")
    print("=" * 70)

    config = build_config()
    manager = HybridDataAccessManager(
        config, db_path=args.db, require_financials=not args.all
    )

    avail = manager.get_availability_status()
    print("📡 데이터 소스 상태:")
    for k, v in avail.items():
        print(f"   - {k}: {'✅' if v else '❌'}")
    if not avail.get("ScreenerDB_Financials"):
        print(f"❌ screener.db를 찾을 수 없습니다: {args.db}")
        return 1
    print()

    try:
        symbols = manager.get_all_symbols()
    except Exception as e:
        logger.error(f"종목 로딩 실패: {e}")
        return 1
    print(f"✅ 대상 종목 {len(symbols)}개 (실제 재무 보유 회사)")
    for i, s in enumerate(symbols, 1):
        print(f"   {i:2d}. {s.code} {s.name} ({s.market})")
    print()

    # 파이프라인 구성
    pipeline = StockFilterPipeline(config)
    if not args.no_price:
        pipeline.add_filter(LiquidityFilter(config, manager))          # 1 (yfinance)
    pipeline.add_filter(AnnualFinancialHealthFilter(config, manager))  # 2 (DB)
    pipeline.add_filter(AnnualQualityGrowthFilter(config, manager))    # 3 (DB)
    if not args.no_price:
        pipeline.add_filter(MomentumFilter(config, manager))           # 4 (yfinance)

    print("🔄 필터링 실행 중...")
    result = pipeline.execute(symbols)

    print("\n📊 단계별 결과:")
    for st in result.stage_results:
        print(f"   {st.stage}: {len(st.passed_symbols)}/{st.total_processed} "
              f"통과 ({st.pass_rate:.0f}%)")
    print(f"\n🎯 최종 후보 {len(result.final_candidates)}개:")
    for s in result.final_candidates:
        print(f"   - {s.code} {s.name} ({s.market})")

    # 엑셀 내보내기
    fname = f"상장사_스크리너_결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        DataExporter.export_pipeline_result_excel(result, fname)
        print(f"\n📁 결과 저장: {fname}")
    except Exception as e:
        logger.error(f"엑셀 저장 실패: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
