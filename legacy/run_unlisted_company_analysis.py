#!/usr/bin/env python3
"""
비상장 기업 재무 건전성 분석 스크립트
DART 감사보고서 추출기(dart-audit-extractor)를 연동하여
비상장사의 재무 데이터를 분석합니다.
"""

import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.quality_growth_filter import QualityGrowthFilter
from auto_financial_filter.data_access.dart_audit_adapter import DartAuditExtractorAdapter
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UnlistedDataManager:
    """비상장사용 임시 데이터 매니저 (DartAuditExtractorAdapter 래핑)"""
    def __init__(self, config: FilterConfig):
        self.dart_adapter = DartAuditExtractorAdapter(config)
        
    def get_financial_data(self, symbol: StockSymbol, quarters: int = 4):
        # 6년치 데이터를 가져옵니다. (품질성장 필터의 매출원가 트렌드 6분기 기준을 6년으로 대체)
        # We always fetch 6 periods to satisfy both filters.
        return self.dart_adapter.get_financial_statements(symbol, quarters=6)
        return self.dart_adapter.get_financial_statements(symbol, quarters=6)
        
    def get_trading_data(self, symbol, days):
        return self.dart_adapter.get_trading_data(symbol, days)
        
    def get_market_data(self, symbol):
        return {'sector': '비상장', 'market_cap': 0.0}

def main():
    parser = argparse.ArgumentParser(description="비상장 기업 분석 스크립트")
    parser.add_argument("company", nargs="?", default="야놀자", help="분석할 비상장 회사명 (예: 야놀자, 무신사, 카카오스타일)")
    args = parser.parse_args()
    
    company_name = args.company
    
    print(f"🏢 비상장 기업 재무 건전성 필터링 (DART 원본 연동)")
    print(f"대상 기업: {company_name}")
    print("=" * 70)
    
    # 설정 (비상장사는 연간 데이터이므로 기준을 적절히 조절)
    config = FilterConfig(
        max_debt_ratio_percent=300.0,            # 부채비율 300% 이하 (비상장사는 다소 높을 수 있음)
        min_revenue_growth_percent=0.0,          # 매출성장률 0% 이상
        cash_flow_quarters=4,                    # 4년 연속 영업현금흐름 양수 (엄격함)
        min_operating_margin_percent=0.0,        # 영업이익률 0% 이상 (흑자 여부)
        profit_trend_years=4,                    # 최근 4년 수익성 피크 확인
        cogs_trend_quarters=6,                   # 최근 6년 원가율 개선 확인
        verbose_output=True,
    )
    
    print(f"📊 적용 필터 기준 (연간 기준):")
    print(f"   💳 최대 부채비율: {config.max_debt_ratio_percent}%")
    print(f"   📈 최소 매출성장률: {config.min_revenue_growth_percent}%")
    print(f"   💰 영업현금흐름 연속 양수: {config.cash_flow_quarters}년")
    print(f"   📊 최소 영업이익률: {config.min_operating_margin_percent}%")
    print()
    
    try:
        data_manager = UnlistedDataManager(config)
        if not data_manager.dart_adapter.is_available():
            print("❌ 오류: dart-audit-extractor가 지정된 경로에 없습니다.")
            return 1
            
    except Exception as e:
        logger.error(f"Data manager initialization failed: {e}")
        return 1
        
    symbol = StockSymbol(code="UNLISTED", name=company_name, market="비상장")
    symbols = [symbol]
    
    # Stage 1 (유동성) 필터는 비상장사이므로 생략
    
    # Stage 2 (재무건전성)
    print("🔄 [Stage 2] 재무건전성 필터링 (부채비율, 성장률, 현금흐름)")
    f2 = FinancialHealthFilter(config, data_manager)
    res2 = f2.filter(symbols)
    
    if not res2.passed_symbols:
        print(f"❌ '{company_name}' 기업은 2단계 재무건전성 기준을 통과하지 못했습니다.")
        return 0
        
    print(f"✅ '{company_name}' 2단계 통과!")
    print()
    
    # Stage 3 (품질성장)
    print("🔄 [Stage 3] 품질성장 필터링 (이익률, 수익성 트렌드, 원가율 개선)")
    f3 = QualityGrowthFilter(config, data_manager)
    res3 = f3.filter(res2.passed_symbols)
    
    if not res3.passed_symbols:
        print(f"❌ '{company_name}' 기업은 3단계 품질성장 기준을 통과하지 못했습니다.")
        return 0
        
    print(f"🎉 최종 합격! '{company_name}' 기업은 모든 재무 필터를 통과했습니다.")
    
    # 간단한 재무 요약 출력
    try:
        data = data_manager.get_financial_data(symbol)
        print("\n📈 [최근 재무 요약]")
        for q in data['quarterly_data']:
            year = q['quarter']
            rev = q.get('revenue', 0) / 100_000_000 # 억원 단위
            op = q.get('operating_profit', 0) / 100_000_000
            debt_r = q.get('debt_ratio', 0)
            cogs_r = q.get('cogs', 0) / q.get('revenue', 1) * 100 if q.get('revenue', 0) > 0 else 0
            print(f"   - {year}년: 매출 {rev:,.0f}억원 | 영업이익 {op:,.0f}억원 | 부채비율 {debt_r:.1f}% | 원가율 {cogs_r:.1f}%")
            
    except Exception as e:
        print(f"요약 출력 실패: {e}")
    
    return 0

if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            if hasattr(_s, "reconfigure"):
                _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
