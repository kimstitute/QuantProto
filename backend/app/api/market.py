from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any

from ..services.market_data_service import market_data_service
from ..schemas.market_data import StockPrice, StockAskingPrices, SymbolRequest

router = APIRouter(
    prefix="/api/market",
    tags=["market"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stock/price/{symbol}", response_model=StockPrice)
async def get_stock_price(symbol: str):
    """
    주식 현재가 시세를 조회합니다.
    
    Args:
        symbol (str): 종목 코드
    
    Returns:
        StockPrice: 주식 시세 정보
    """
    try:
        data = await market_data_service.get_stock_price(symbol)
        
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])
        
        return StockPrice.from_api_response(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/asking-price/{symbol}", response_model=StockAskingPrices)
async def get_stock_asking_price(symbol: str):
    """
    주식 호가 정보를 조회합니다.
    
    Args:
        symbol (str): 종목 코드
    
    Returns:
        StockAskingPrices: 주식 호가 정보
    """
    try:
        data = await market_data_service.get_stock_asking_price(symbol)
        
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])
        
        return StockAskingPrices.from_api_response(data["output1"], data["output2"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth")
async def authenticate():
    """
    한국투자증권 Open API 인증을 수행합니다.
    
    Returns:
        Dict[str, Any]: 인증 결과
    """
    from ..services.kis_auth import kis_auth
    
    try:
        result = kis_auth.auth()
        
        return {
            "success": result,
            "message": "인증 성공" if result else "인증 실패"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/prod")
async def authenticate_prod():
    """
    한국투자증권 Open API 실전투자 인증을 수행합니다.
    
    Returns:
        Dict[str, Any]: 인증 결과
    """
    from ..services.kis_auth import kis_auth
    
    try:
        result = kis_auth.auth(svr="prod")
        
        return {
            "success": result,
            "message": "실전투자 인증 성공" if result else "실전투자 인증 실패"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/vps")
async def authenticate_vps():
    """
    한국투자증권 Open API 모의투자 인증을 수행합니다.
    
    Returns:
        Dict[str, Any]: 인증 결과
    """
    from ..services.kis_auth import kis_auth
    
    try:
        result = kis_auth.auth(svr="vps")
        
        return {
            "success": result,
            "message": "모의투자 인증 성공" if result else "모의투자 인증 실패"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))