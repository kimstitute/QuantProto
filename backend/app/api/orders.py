from fastapi import APIRouter, HTTPException

from app.schemas.order import (
    MockCancelRequest,
    MockCancelResponse,
    MockCashOrderRequest,
    MockCashOrderResponse,
)
from app.services.kis_order_service import kis_order_service

router = APIRouter(
    prefix="/api/orders/mock",
    tags=["orders"],
)


@router.post("/cash", response_model=MockCashOrderResponse)
async def place_cash_order(payload: MockCashOrderRequest) -> MockCashOrderResponse:
    """Place a mock (paper) cash order for domestic stocks."""
    try:
        result = kis_order_service.place_cash_order(payload)
        return result
    except RuntimeError as exc:  # e.g. business level failure
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cash/cancel", response_model=MockCancelResponse)
async def cancel_cash_order(payload: MockCancelRequest) -> MockCancelResponse:
    """Cancel or revise a previously submitted mock cash order."""
    try:
        result = kis_order_service.cancel_cash_order(payload)
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
