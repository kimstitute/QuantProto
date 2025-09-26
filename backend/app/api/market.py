from fastapi import APIRouter, HTTPException, Query

from ..schemas.market_data import StockAskingPrices, StockPrice, StockPriceHistory
from ..services.market_data_service import market_data_service

router = APIRouter(
    prefix="/api/market",
    tags=["market"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stock/price/{symbol}", response_model=StockPrice)
async def get_stock_price(symbol: str) -> StockPrice:
    """Return the latest price snapshot for the requested symbol."""

    try:
        data = await market_data_service.get_stock_price(symbol)
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])
        return StockPrice.from_api_response(data)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stock/history/{symbol}", response_model=StockPriceHistory)
async def get_stock_price_history(
    symbol: str,
    days: int = Query(30, ge=1, le=120, description="Number of sessions to fetch"),
) -> StockPriceHistory:
    """Return up to ``days`` daily candles for the requested symbol."""

    try:
        payload = await market_data_service.get_stock_price_history(symbol, days)
        if isinstance(payload, dict) and "error" in payload:
            raise HTTPException(status_code=400, detail=payload["error"])

        return StockPriceHistory.from_api_response(
            symbol=payload.get("symbol", symbol),
            name=payload.get("name"),
            raw_candles=payload.get("candles", []),
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stock/asking-price/{symbol}", response_model=StockAskingPrices)
async def get_stock_asking_price(symbol: str) -> StockAskingPrices:
    """Return the current order-book snapshot with top ask/bid levels."""

    try:
        data = await market_data_service.get_stock_asking_price(symbol)
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])
        return StockAskingPrices.from_api_response(data["output1"], data["output2"])
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/auth")
async def authenticate() -> dict[str, bool | str]:
    """Explicitly refresh the trading API access token (paper environment)."""

    from ..services.kis_auth import kis_auth

    try:
        success = kis_auth.auth()
        return {"success": success, "message": "Authentication succeeded" if success else "Authentication failed"}
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/auth/prod")
async def authenticate_prod() -> dict[str, bool | str]:
    """Refresh the access token for the production environment."""

    from ..services.kis_auth import kis_auth

    try:
        success = kis_auth.auth(svr="prod")
        return {"success": success, "message": "Production authentication succeeded" if success else "Production authentication failed"}
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/auth/vps")
async def authenticate_vps() -> dict[str, bool | str]:
    """Refresh the access token for the VPS (virtual trading) environment."""

    from ..services.kis_auth import kis_auth

    try:
        success = kis_auth.auth(svr="vps")
        return {"success": success, "message": "VPS authentication succeeded" if success else "VPS authentication failed"}
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc
