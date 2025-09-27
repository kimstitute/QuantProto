import json
import re
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.services.portfolio_service import portfolio_service
from app.services.trading_engine import trading_engine
from app.services.trading_config import trading_config
from app.config import settings

logger = logging.getLogger(__name__)


class TradingRecommendation(BaseModel):
    """LLM 트레이딩 추천 데이터 모델"""
    action: str  # "buy", "sell", "hold"
    ticker: str
    shares: Decimal
    price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    reason: str
    confidence: float = 0.5


class LLMResponse(BaseModel):
    """LLM 응답 데이터 모델"""
    analysis: str
    trades: List[TradingRecommendation]
    confidence: float
    reasoning: Optional[str] = None


@dataclass
class LLMConfig:
    """LLM 설정"""
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 1500
    api_key: Optional[str] = None


class LLMTradingService:
    """
    레퍼런스 프로젝트의 simple_automation.py 로직을 구현한 LLM 트레이딩 서비스
    
    주요 기능:
    - 포트폴리오 상태 기반 프롬프트 생성
    - LLM API 호출 (OpenAI/Claude 등)
    - 트레이딩 결정 파싱 및 실행
    - 결과 로깅 및 분석
    """
    
    def __init__(self, config: LLMConfig = None):
        # 환경변수에서 설정 로드
        if config is None:
            config = LLMConfig(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                api_key=settings.openai_api_key
            )
        self.config = config
        self._response_history = []
    
    def generate_trading_prompt(
        self, 
        db: Session,
        custom_instructions: str = None
    ) -> str:
        """
        레퍼런스의 generate_trading_prompt() 구현
        현재 포트폴리오 상태를 기반으로 LLM용 프롬프트 생성
        """
        try:
            # 포트폴리오 요약 정보 가져오기
            portfolio_summary = portfolio_service.get_portfolio_summary(db)
            cash_balance = portfolio_service.cash_balance
            
            # 총 자산 계산
            portfolio_value = sum(
                (pos.current_value or Decimal("0")) for pos in portfolio_summary
            )
            total_equity = cash_balance + portfolio_value
            
            # 보유 종목 포맷팅
            if portfolio_summary:
                holdings_text = self._format_holdings(portfolio_summary)
            else:
                holdings_text = "현재 보유 종목 없음"
            
            # 최근 성과 데이터 (선택적)
            recent_performance = self._get_recent_performance(db)
            
            # 현재 날짜
            today = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # 기본 프롬프트 템플릿 (레퍼런스 기반)
            base_prompt = f"""당신은 전문 포트폴리오 분석가입니다. 현재 포트폴리오 상태를 분석하고 트레이딩 결정을 내려주세요.

**현재 포트폴리오 상태** ({today})

[ 보유 종목 ]
{holdings_text}

[ 자산 현황 ]
현금 잔고: {cash_balance:,.0f} KRW
포트폴리오 가치: {portfolio_value:,.0f} KRW
총 자산: {total_equity:,.0f} KRW

{recent_performance}

**투자 규칙**
- 현금 잔고: {cash_balance:,.0f} KRW 사용 가능
- 한국 주식 시장 (KOSPI/KOSDAQ) 위주 투자
- 정수 주식만 매매 (옵션, 파생상품 제외)
- 포지션 사이즈는 보수적으로 관리 (총 자산의 10% 이하 권장)

**스톱로스 설정 기준** (매수 시 필수)
- 대형주: 매수가 대비 -8% ~ -12% 하락 시 손절
- 중형주: 매수가 대비 -10% ~ -15% 하락 시 손절
- 소형주: 매수가 대비 -12% ~ -18% 하락 시 손절
- 변동성이 큰 종목: 더 넓은 손절 범위 적용 가능
- 계산 예시: 매수가 100,000원 → 대형주 손절가 88,000~92,000원

**현재 시장 상황 분석 및 투자 추천사항을 제시해주세요.**

반드시 다음 JSON 형태로만 응답해주세요:
{{
    "analysis": "시장 분석 및 투자 근거",
    "trades": [
        {{
            "action": "buy|sell|hold",
            "ticker": "종목코드",
            "shares": 매매할_주식_수,
            "price": 예상_매매가격,
            "stop_loss": 손절가격(선택사항),
            "reason": "매매 근거",
            "confidence": 0.0_to_1.0_신뢰도
        }}
    ],
    "confidence": 전체_신뢰도_0.0_to_1.0,
    "reasoning": "전체적인 투자 전략 설명"
}}

추천할 거래가 없다면 trades 배열을 비워두세요."""

            # 사용자 정의 지시사항 추가
            if custom_instructions:
                base_prompt += f"\n\n**추가 지시사항:**\n{custom_instructions}"
            
            return base_prompt
            
        except Exception as e:
            logger.error(f"프롬프트 생성 중 오류: {e}")
            raise
    
    def _format_holdings(self, portfolio_summary: List) -> str:
        """보유 종목 포맷팅"""
        if not portfolio_summary:
            return "보유 종목 없음"
        
        lines = []
        lines.append(f"{'종목코드':<10} {'수량':<8} {'평균단가':<12} {'현재가':<12} {'평가손익':<12} {'수익률':<8} {'스톱로스':<10}")
        lines.append("-" * 80)
        
        for pos in portfolio_summary:
            ticker = pos.ticker
            shares = f"{pos.shares:.0f}"
            buy_price = f"{pos.buy_price:,.0f}" if pos.buy_price else "N/A"
            current_price = f"{pos.current_price:,.0f}" if pos.current_price else "N/A"
            pnl = f"{pos.pnl:+,.0f}" if pos.pnl else "N/A"
            pnl_pct = f"{pos.pnl_percent:+.1f}%" if pos.pnl_percent else "N/A"
            stop_loss = f"{pos.stop_loss:,.0f}" if pos.stop_loss else "N/A"
            
            lines.append(f"{ticker:<10} {shares:<8} {buy_price:<12} {current_price:<12} {pnl:<12} {pnl_pct:<8} {stop_loss:<10}")
        
        return "\n".join(lines)
    
    def _get_recent_performance(self, db: Session, days: int = 7) -> str:
        """최근 성과 데이터 가져오기"""
        try:
            from app.models.daily_performance import DailyPerformance
            from datetime import timedelta
            
            # 최근 N일간 성과 조회
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            performances = db.query(DailyPerformance).filter(
                DailyPerformance.date >= start_date,
                DailyPerformance.date <= end_date
            ).order_by(DailyPerformance.date.desc()).limit(days).all()
            
            if not performances:
                return ""
            
            # 성과 요약
            latest = performances[0]
            oldest = performances[-1] if len(performances) > 1 else latest
            
            period_return = ((latest.total_equity - oldest.total_equity) / oldest.total_equity * 100) if oldest.total_equity > 0 else 0
            
            return f"""
[ 최근 {len(performances)}일 성과 ]
기간 수익률: {period_return:+.2f}%
최신 총 자산: {latest.total_equity:,.0f} KRW
최신 현금: {latest.cash_balance:,.0f} KRW
최신 포트폴리오: {latest.portfolio_value:,.0f} KRW
"""
        except Exception as e:
            logger.warning(f"최근 성과 데이터 조회 실패: {e}")
            return ""
    
    async def call_llm_api(self, prompt: str) -> str:
        """
        LLM API 호출 (OpenAI/Claude 등)
        실제 구현시에는 환경에 따라 다른 API 사용 가능
        """
        try:
            # OpenAI API 호출 (예시)
            if self.config.api_key:
                return await self._call_openai_api(prompt)
            else:
                # API 키가 없을 때는 더미 응답 반환
                logger.warning("LLM API 키가 설정되지 않음. 더미 응답을 반환합니다.")
                return await self._generate_dummy_response(prompt)
                
        except Exception as e:
            logger.error(f"LLM API 호출 실패: {e}")
            raise
    
    async def _call_openai_api(self, prompt: str) -> str:
        """OpenAI API 호출"""
        try:
            # API 키 확인
            api_key = self.config.api_key or settings.openai_api_key
            if not api_key or api_key == "your_openai_api_key_here":
                logger.warning("OpenAI API 키가 설정되지 않음. 더미 응답을 반환합니다.")
                return await self._generate_dummy_response(prompt)
            
            # OpenAI API 라이브러리 import (선택적)
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system", 
                            "content": "당신은 전문적인 포트폴리오 분석가입니다. 항상 요청된 JSON 형식으로 정확히 응답하세요."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                
                return response.choices[0].message.content
                
            except ImportError:
                logger.error("openai 라이브러리가 설치되지 않음")
                return await self._generate_dummy_response(prompt)
                
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            return f'{{"error": "API 호출 실패: {e}"}}'
    
    async def _generate_dummy_response(self, prompt: str) -> str:
        """더미 LLM 응답 생성 (테스트용)"""
        return """{
    "analysis": "현재 시장이 횡보하는 상황으로, 안전 자산에 대한 선호도가 높아지고 있습니다. 대형주 위주의 포트폴리오를 유지하면서 일부 성장주에 소액 투자를 고려해볼만 합니다.",
    "trades": [
        {
            "action": "buy",
            "ticker": "005930",
            "shares": 10,
            "price": 75000,
            "stop_loss": 67500,
            "reason": "삼성전자는 반도체 업황 회복 기대감으로 매수 추천",
            "confidence": 0.7
        }
    ],
    "confidence": 0.6,
    "reasoning": "현재 시장 상황에서는 보수적 접근이 필요하며, 대형우량주 중심의 포트폴리오가 적절합니다."
}"""
    
    def parse_llm_response(self, response: str) -> LLMResponse:
        """
        레퍼런스의 parse_llm_response() 구현
        LLM 응답을 파싱하여 구조화된 데이터로 변환
        """
        try:
            # JSON 추출
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = response
            
            # JSON 파싱
            parsed_data = json.loads(json_str)
            
            # 트레이딩 추천사항 변환
            trades = []
            for trade_data in parsed_data.get('trades', []):
                try:
                    trade = TradingRecommendation(
                        action=trade_data.get('action', '').lower(),
                        ticker=trade_data.get('ticker', ''),
                        shares=Decimal(str(trade_data.get('shares', 0))),
                        price=Decimal(str(trade_data.get('price', 0))) if trade_data.get('price') else None,
                        stop_loss=Decimal(str(trade_data.get('stop_loss', 0))) if trade_data.get('stop_loss') else None,
                        reason=trade_data.get('reason', ''),
                        confidence=float(trade_data.get('confidence', 0.5))
                    )
                    trades.append(trade)
                except (ValueError, TypeError) as e:
                    logger.warning(f"거래 데이터 파싱 실패: {trade_data}, 오류: {e}")
                    continue
            
            # LLMResponse 객체 생성
            llm_response = LLMResponse(
                analysis=parsed_data.get('analysis', ''),
                trades=trades,
                confidence=float(parsed_data.get('confidence', 0.5)),
                reasoning=parsed_data.get('reasoning', '')
            )
            
            return llm_response
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"응답 내용: {response}")
            raise ValueError(f"LLM 응답 JSON 파싱 실패: {e}")
        except Exception as e:
            logger.error(f"LLM 응답 파싱 중 예외: {e}")
            raise
    
    async def execute_trading_decisions(
        self, 
        db: Session,
        llm_response: LLMResponse,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        레퍼런스의 execute_automated_trades() 구현
        LLM의 트레이딩 결정을 실제로 실행
        """
        execution_results = []
        successful_trades = 0
        failed_trades = 0
        
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}LLM 트레이딩 결정 실행: {len(llm_response.trades)}건")
        
        for trade in llm_response.trades:
            try:
                if dry_run:
                    # 드라이 런 모드
                    result = {
                        "success": True,
                        "message": f"[DRY RUN] {trade.action.upper()}: {trade.shares}주 of {trade.ticker}",
                        "dry_run": True
                    }
                    execution_results.append({
                        "trade": trade.dict(),
                        "result": result
                    })
                    successful_trades += 1
                    continue
                
                # 실제 거래 실행
                if trade.action == "buy":
                    if trade.price and trade.shares > 0:
                        result = portfolio_service.execute_buy_order(
                            db=db,
                            ticker=trade.ticker,
                            shares=trade.shares,
                            price=trade.price,
                            stop_loss=trade.stop_loss
                        )
                    else:
                        result = {"success": False, "message": "매수 주문 정보 부족"}
                        
                elif trade.action == "sell":
                    if trade.price and trade.shares > 0:
                        result = portfolio_service.execute_sell_order(
                            db=db,
                            ticker=trade.ticker,
                            shares=trade.shares,
                            price=trade.price,
                            reason=f"LLM 추천: {trade.reason}"
                        )
                    else:
                        result = {"success": False, "message": "매도 주문 정보 부족"}
                        
                elif trade.action == "hold":
                    result = {
                        "success": True,
                        "message": f"HOLD: {trade.ticker} - {trade.reason}"
                    }
                else:
                    result = {"success": False, "message": f"알 수 없는 액션: {trade.action}"}
                
                # 결과 기록
                execution_results.append({
                    "trade": trade.dict(),
                    "result": result
                })
                
                if result.get("success"):
                    successful_trades += 1
                    logger.info(f"✅ {trade.action.upper()}: {trade.ticker} - {result.get('message')}")
                else:
                    failed_trades += 1
                    logger.warning(f"❌ {trade.action.upper()}: {trade.ticker} - {result.get('message')}")
                    
            except Exception as e:
                failed_trades += 1
                error_result = {"success": False, "message": f"실행 오류: {e}"}
                execution_results.append({
                    "trade": trade.dict(),
                    "result": error_result
                })
                logger.error(f"거래 실행 중 오류: {trade.dict()}, 오류: {e}")
        
        # 실행 결과 요약
        summary = {
            "total_trades": len(llm_response.trades),
            "successful_trades": successful_trades,
            "failed_trades": failed_trades,
            "execution_rate": successful_trades / len(llm_response.trades) * 100 if llm_response.trades else 0,
            "llm_confidence": llm_response.confidence,
            "analysis": llm_response.analysis,
            "reasoning": llm_response.reasoning,
            "execution_results": execution_results,
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run
        }
        
        # 응답 히스토리에 저장
        self._response_history.append(summary)
        
        return summary
    
    def get_response_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """LLM 응답 히스토리 조회"""
        return self._response_history[-limit:]
    
    def clear_response_history(self):
        """응답 히스토리 초기화"""
        self._response_history.clear()


# 싱글톤 인스턴스
llm_trading_service = LLMTradingService()