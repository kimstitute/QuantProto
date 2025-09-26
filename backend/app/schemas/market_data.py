import datetime as dt
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StockPrice(BaseModel):
    """Latest price snapshot returned from the KIS price endpoint."""

    symbol: str = Field(..., description="Ticker symbol")
    name: str = Field(..., description="Instrument name")
    price: float = Field(..., description="Last traded price")
    change: float = Field(..., description="Day-over-day absolute change")
    change_rate: float = Field(..., description="Day-over-day percentage change")
    open: float = Field(..., description="Session open price")
    high: float = Field(..., description="Session high price")
    low: float = Field(..., description="Session low price")
    volume: int = Field(..., description="Accumulated volume")
    trade_value: int = Field(..., description="Accumulated trade value")
    market_cap: Optional[int] = Field(None, description="Market capitalisation")

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "StockPrice":
        """Map raw API payload into the internal schema."""

        return cls(
            symbol=data.get("stck_shrn_iscd", ""),
            name=data.get("stck_prpr_itms_name", ""),
            price=float(data.get("stck_prpr", "0")),
            change=float(data.get("prdy_vrss", "0")),
            change_rate=float(data.get("prdy_ctrt", "0")),
            open=float(data.get("stck_oprc", "0")),
            high=float(data.get("stck_hgpr", "0")),
            low=float(data.get("stck_lwpr", "0")),
            volume=int(data.get("acml_vol", "0")),
            trade_value=int(data.get("acml_tr_pbmn", "0")),
            market_cap=int(data.get("hts_avls", "0")) if data.get("hts_avls") else None,
        )


class StockCandle(BaseModel):
    """Daily OHLCV data point."""

    date: dt.date = Field(..., description="Trading date")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    change: float = Field(..., description="Absolute change from previous session")
    change_rate: float = Field(..., description="Percentage change from previous session")
    volume: int = Field(..., description="Session volume")
    trade_value: int = Field(..., description="Session trade value")

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "StockCandle":
        raw = data.get("stck_bsop_date", "")
        trade_date = datetime.strptime(raw, "%Y%m%d").date() if raw else dt.date.today()
        return cls(
            date=trade_date,
            open=float(data.get("stck_oprc", "0")),
            high=float(data.get("stck_hgpr", "0")),
            low=float(data.get("stck_lwpr", "0")),
            close=float(data.get("stck_clpr", "0")),
            change=float(data.get("prdy_vrss", "0")),
            change_rate=float(data.get("prdy_ctrt", "0")),
            volume=int(data.get("acml_vol", "0")),
            trade_value=int(data.get("acml_tr_pbmn", "0")),
        )


class StockPriceHistory(BaseModel):
    """Daily price series for a given symbol."""

    symbol: str = Field(..., description="Ticker symbol")
    name: Optional[str] = Field(None, description="Instrument name")
    candles: List[StockCandle] = Field(..., description="Daily OHLCV data")

    @classmethod
    def from_api_response(
        cls,
        symbol: str,
        name: Optional[str],
        raw_candles: List[Dict[str, Any]],
    ) -> "StockPriceHistory":
        return cls(
            symbol=symbol,
            name=name,
            candles=[StockCandle.from_api_response(item) for item in raw_candles],
        )


class AskingPrice(BaseModel):
    """Single depth level for either side of the order book."""

    price: float = Field(..., description="Quoted price")
    quantity: int = Field(..., description="Quoted quantity")


class StockAskingPrices(BaseModel):
    """Order-book snapshot from the KIS asking price endpoint."""

    symbol: str = Field(..., description="Ticker symbol")
    name: str = Field(..., description="Instrument name")
    price: float = Field(..., description="Last traded price")
    asks: List[AskingPrice] = Field(..., description="Ask levels")
    bids: List[AskingPrice] = Field(..., description="Bid levels")
    total_ask_quantity: int = Field(..., description="Total ask-side quantity")
    total_bid_quantity: int = Field(..., description="Total bid-side quantity")

    @classmethod
    def from_api_response(cls, output1: Dict[str, Any], output2: List[Dict[str, Any]]) -> "StockAskingPrices":
        asks: List[AskingPrice] = []
        bids: List[AskingPrice] = []

        for level in range(1, 11):
            ask_price = float(output1.get(f"askp{level}", "0"))
            ask_qty = int(output1.get(f"askp_rsqn{level}", "0"))
            if ask_price > 0:
                asks.append(AskingPrice(price=ask_price, quantity=ask_qty))

            bid_price = float(output1.get(f"bidp{level}", "0"))
            bid_qty = int(output1.get(f"bidp_rsqn{level}", "0"))
            if bid_price > 0:
                bids.append(AskingPrice(price=bid_price, quantity=bid_qty))

        asks.sort(key=lambda item: item.price)
        bids.sort(key=lambda item: item.price, reverse=True)

        return cls(
            symbol=output1.get("stck_shrn_iscd", ""),
            name=output1.get("stck_prpr_itms_name", ""),
            price=float(output1.get("stck_prpr", "0")),
            asks=asks,
            bids=bids,
            total_ask_quantity=int(output1.get("total_askp_rsqn", "0")),
            total_bid_quantity=int(output1.get("total_bidp_rsqn", "0")),
        )


class RealtimeStockPrice(BaseModel):
    """Realtime trade tick received over WebSocket."""

    symbol: str = Field(..., description="Ticker symbol")
    time: str = Field(..., description="Execution time (HHMMSS)")
    price: float = Field(..., description="Last traded price")
    change: float = Field(..., description="Day-over-day absolute change")
    change_rate: float = Field(..., description="Day-over-day percentage change")
    volume: int = Field(..., description="Execution volume")
    trade_value: int = Field(..., description="Accumulated trade value")
    open: float = Field(..., description="Session open price")
    high: float = Field(..., description="Session high price")
    low: float = Field(..., description="Session low price")
    ask_price: float = Field(..., description="Best ask price")
    bid_price: float = Field(..., description="Best bid price")

    @classmethod
    def from_websocket_data(cls, data: Dict[str, Any]) -> "RealtimeStockPrice":
        body = data.get("body", {})
        return cls(
            symbol=body.get("mksc_shrn_iscd", ""),
            time=body.get("stck_cntg_hour", ""),
            price=float(body.get("stck_prpr", "0")),
            change=float(body.get("prdy_vrss", "0")),
            change_rate=float(body.get("prdy_ctrt", "0")),
            volume=int(body.get("cntg_vol", "0")),
            trade_value=int(body.get("acml_tr_pbmn", "0")),
            open=float(body.get("stck_oprc", "0")),
            high=float(body.get("stck_hgpr", "0")),
            low=float(body.get("stck_lwpr", "0")),
            ask_price=float(body.get("askp1", "0")),
            bid_price=float(body.get("bidp1", "0")),
        )


class RealtimeAskingPrice(BaseModel):
    """Realtime order book snapshot received over WebSocket."""

    symbol: str = Field(..., description="Ticker symbol")
    time: str = Field(..., description="Server timestamp")
    asks: List[AskingPrice] = Field(..., description="Top ask levels")
    bids: List[AskingPrice] = Field(..., description="Top bid levels")
    total_ask_quantity: int = Field(..., description="Total ask-side quantity")
    total_bid_quantity: int = Field(..., description="Total bid-side quantity")
    expected_price: float = Field(..., description="Indicative match price")
    expected_quantity: int = Field(..., description="Indicative match quantity")

    @classmethod
    def from_websocket_data(cls, data: Dict[str, Any]) -> "RealtimeAskingPrice":
        body = data.get("body", {})
        asks: List[AskingPrice] = []
        bids: List[AskingPrice] = []

        for level in range(1, 11):
            ask_price = float(body.get(f"askp{level}", "0"))
            ask_qty = int(body.get(f"askp_rsqn{level}", "0"))
            if ask_price > 0:
                asks.append(AskingPrice(price=ask_price, quantity=ask_qty))

            bid_price = float(body.get(f"bidp{level}", "0"))
            bid_qty = int(body.get(f"bidp_rsqn{level}", "0"))
            if bid_price > 0:
                bids.append(AskingPrice(price=bid_price, quantity=bid_qty))

        asks.sort(key=lambda item: item.price)
        bids.sort(key=lambda item: item.price, reverse=True)

        return cls(
            symbol=body.get("mksc_shrn_iscd", ""),
            time=body.get("bsop_hour", ""),
            asks=asks,
            bids=bids,
            total_ask_quantity=int(body.get("total_askp_rsqn", "0")),
            total_bid_quantity=int(body.get("total_bidp_rsqn", "0")),
            expected_price=float(body.get("antc_cnpr", "0")),
            expected_quantity=int(body.get("antc_cnqn", "0")),
        )


class SymbolRequest(BaseModel):
    """Request payload used by WebSocket subscription endpoints."""

    symbol: str = Field(..., description="Ticker symbol")


class WebSocketMessage(BaseModel):
    """Inbound WebSocket message."""

    type: str = Field(..., description="Message type identifier")
    data: Dict[str, Any] = Field(..., description="Payload data")


class WebSocketResponse(BaseModel):
    """Outbound WebSocket message."""

    type: str = Field(..., description="Message type identifier")
    data: Dict[str, Any] = Field(..., description="Payload data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Server timestamp")
