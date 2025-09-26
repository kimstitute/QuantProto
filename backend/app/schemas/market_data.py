from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class StockPrice(BaseModel):
    """주식 현재가 시세 정보"""
    
    symbol: str = Field(..., description="종목 코드")
    name: str = Field(..., description="종목명")
    price: float = Field(..., description="현재가")
    change: float = Field(..., description="전일 대비")
    change_rate: float = Field(..., description="전일 대비율")
    open: float = Field(..., description="시가")
    high: float = Field(..., description="고가")
    low: float = Field(..., description="저가")
    volume: int = Field(..., description="거래량")
    trade_value: int = Field(..., description="거래대금")
    market_cap: Optional[int] = Field(None, description="시가총액")
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "StockPrice":
        """API 응답으로부터 StockPrice 객체를 생성합니다."""
        
        # 필드 매핑
        return cls(
            symbol=data.get("stck_shrn_iscd", ""),  # 종목 코드
            name=data.get("stck_prpr_itms_name", ""),  # 종목명
            price=float(data.get("stck_prpr", "0")),  # 현재가
            change=float(data.get("prdy_vrss", "0")),  # 전일 대비
            change_rate=float(data.get("prdy_ctrt", "0")),  # 전일 대비율
            open=float(data.get("stck_oprc", "0")),  # 시가
            high=float(data.get("stck_hgpr", "0")),  # 고가
            low=float(data.get("stck_lwpr", "0")),  # 저가
            volume=int(data.get("acml_vol", "0")),  # 거래량
            trade_value=int(data.get("acml_tr_pbmn", "0")),  # 거래대금
            market_cap=int(data.get("hts_avls", "0")) if data.get("hts_avls") else None  # 시가총액
        )


class AskingPrice(BaseModel):
    """호가 정보"""
    
    price: float = Field(..., description="호가")
    quantity: int = Field(..., description="잔량")


class StockAskingPrices(BaseModel):
    """주식 호가 정보"""
    
    symbol: str = Field(..., description="종목 코드")
    name: str = Field(..., description="종목명")
    price: float = Field(..., description="현재가")
    asks: List[AskingPrice] = Field(..., description="매도호가")
    bids: List[AskingPrice] = Field(..., description="매수호가")
    total_ask_quantity: int = Field(..., description="총 매도호가 잔량")
    total_bid_quantity: int = Field(..., description="총 매수호가 잔량")
    
    @classmethod
    def from_api_response(cls, output1: Dict[str, Any], output2: List[Dict[str, Any]]) -> "StockAskingPrices":
        """API 응답으로부터 StockAskingPrices 객체를 생성합니다."""
        
        # 매도호가 및 매수호가 추출
        asks = []
        bids = []
        
        # 호가 정보 추출
        for i in range(1, 11):
            # 매도호가
            ask_price = float(output1.get(f"askp{i}", "0"))
            ask_quantity = int(output1.get(f"askp_rsqn{i}", "0"))
            if ask_price > 0:
                asks.append(AskingPrice(price=ask_price, quantity=ask_quantity))
            
            # 매수호가
            bid_price = float(output1.get(f"bidp{i}", "0"))
            bid_quantity = int(output1.get(f"bidp_rsqn{i}", "0"))
            if bid_price > 0:
                bids.append(AskingPrice(price=bid_price, quantity=bid_quantity))
        
        # 매도호가는 가격 오름차순으로 정렬
        asks.sort(key=lambda x: x.price)
        
        # 매수호가는 가격 내림차순으로 정렬
        bids.sort(key=lambda x: x.price, reverse=True)
        
        return cls(
            symbol=output1.get("stck_shrn_iscd", ""),  # 종목 코드
            name=output1.get("stck_prpr_itms_name", ""),  # 종목명
            price=float(output1.get("stck_prpr", "0")),  # 현재가
            asks=asks,
            bids=bids,
            total_ask_quantity=int(output1.get("total_askp_rsqn", "0")),  # 총 매도호가 잔량
            total_bid_quantity=int(output1.get("total_bidp_rsqn", "0"))  # 총 매수호가 잔량
        )


class RealtimeStockPrice(BaseModel):
    """실시간 주식 시세 정보"""
    
    symbol: str = Field(..., description="종목 코드")
    time: str = Field(..., description="체결 시간")
    price: float = Field(..., description="현재가")
    change: float = Field(..., description="전일 대비")
    change_rate: float = Field(..., description="전일 대비율")
    volume: int = Field(..., description="거래량")
    trade_value: int = Field(..., description="거래대금")
    open: float = Field(..., description="시가")
    high: float = Field(..., description="고가")
    low: float = Field(..., description="저가")
    ask_price: float = Field(..., description="매도호가")
    bid_price: float = Field(..., description="매수호가")
    
    @classmethod
    def from_websocket_data(cls, data: Dict[str, Any]) -> "RealtimeStockPrice":
        """WebSocket 데이터로부터 RealtimeStockPrice 객체를 생성합니다."""
        
        body = data.get("body", {})
        
        return cls(
            symbol=body.get("mksc_shrn_iscd", ""),  # 종목 코드
            time=body.get("stck_cntg_hour", ""),  # 체결 시간
            price=float(body.get("stck_prpr", "0")),  # 현재가
            change=float(body.get("prdy_vrss", "0")),  # 전일 대비
            change_rate=float(body.get("prdy_ctrt", "0")),  # 전일 대비율
            volume=int(body.get("cntg_vol", "0")),  # 거래량
            trade_value=int(body.get("acml_tr_pbmn", "0")),  # 거래대금
            open=float(body.get("stck_oprc", "0")),  # 시가
            high=float(body.get("stck_hgpr", "0")),  # 고가
            low=float(body.get("stck_lwpr", "0")),  # 저가
            ask_price=float(body.get("askp1", "0")),  # 매도호가
            bid_price=float(body.get("bidp1", "0"))  # 매수호가
        )


class RealtimeAskingPrice(BaseModel):
    """실시간 호가 정보"""
    
    symbol: str = Field(..., description="종목 코드")
    time: str = Field(..., description="시간")
    asks: List[AskingPrice] = Field(..., description="매도호가")
    bids: List[AskingPrice] = Field(..., description="매수호가")
    total_ask_quantity: int = Field(..., description="총 매도호가 잔량")
    total_bid_quantity: int = Field(..., description="총 매수호가 잔량")
    expected_price: float = Field(..., description="예상 체결가")
    expected_quantity: int = Field(..., description="예상 체결량")
    
    @classmethod
    def from_websocket_data(cls, data: Dict[str, Any]) -> "RealtimeAskingPrice":
        """WebSocket 데이터로부터 RealtimeAskingPrice 객체를 생성합니다."""
        
        body = data.get("body", {})
        
        # 매도호가 및 매수호가 추출
        asks = []
        bids = []
        
        # 호가 정보 추출
        for i in range(1, 11):
            # 매도호가
            ask_price = float(body.get(f"askp{i}", "0"))
            ask_quantity = int(body.get(f"askp_rsqn{i}", "0"))
            if ask_price > 0:
                asks.append(AskingPrice(price=ask_price, quantity=ask_quantity))
            
            # 매수호가
            bid_price = float(body.get(f"bidp{i}", "0"))
            bid_quantity = int(body.get(f"bidp_rsqn{i}", "0"))
            if bid_price > 0:
                bids.append(AskingPrice(price=bid_price, quantity=bid_quantity))
        
        # 매도호가는 가격 오름차순으로 정렬
        asks.sort(key=lambda x: x.price)
        
        # 매수호가는 가격 내림차순으로 정렬
        bids.sort(key=lambda x: x.price, reverse=True)
        
        return cls(
            symbol=body.get("mksc_shrn_iscd", ""),  # 종목 코드
            time=body.get("bsop_hour", ""),  # 시간
            asks=asks,
            bids=bids,
            total_ask_quantity=int(body.get("total_askp_rsqn", "0")),  # 총 매도호가 잔량
            total_bid_quantity=int(body.get("total_bidp_rsqn", "0")),  # 총 매수호가 잔량
            expected_price=float(body.get("antc_cnpr", "0")),  # 예상 체결가
            expected_quantity=int(body.get("antc_cnqn", "0"))  # 예상 체결량
        )


class SymbolRequest(BaseModel):
    """종목 코드 요청"""
    
    symbol: str = Field(..., description="종목 코드")


class WebSocketMessage(BaseModel):
    """WebSocket 메시지"""
    
    type: str = Field(..., description="메시지 타입")
    data: Dict[str, Any] = Field(..., description="메시지 데이터")


class WebSocketResponse(BaseModel):
    """WebSocket 응답"""
    
    type: str = Field(..., description="메시지 타입")
    data: Dict[str, Any] = Field(..., description="메시지 데이터")
    timestamp: datetime = Field(default_factory=datetime.now, description="타임스탬프")