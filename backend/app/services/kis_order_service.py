import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import requests

from app.config import settings
from app.schemas.order import (
    MockCancelRequest,
    MockCancelResponse,
    MockCashOrderRequest,
    MockCashOrderResponse,
    OrderSide,
)
from .kis_auth import kis_auth

logger = logging.getLogger("uvicorn.error")


class KISOrderService:
    """Service wrapper around KIS mock trading order APIs."""

    ORDER_CASH_ENDPOINT = "/uapi/domestic-stock/v1/trading/order-cash"
    ORDER_CANCEL_ENDPOINT = "/uapi/domestic-stock/v1/trading/order-rvsecncl"

    def __init__(self) -> None:
        self.default_exchange = settings.kis_default_exchange or "KRX"
        self.env = settings.kis_trade_environment or "vps"

    def _resolve_account(self, request_account: Optional[str], request_product: Optional[str]) -> tuple[str, str]:
        """Pick account number/product code from request overrides, settings or config."""
        base_number = request_account or settings.kis_account_number or kis_auth.config.get("my_paper_stock", "")
        product_code = request_product or settings.kis_account_product_code or kis_auth.product or "01"

        if not base_number:
            raise ValueError("Account number is not configured. Set KIS_ACCOUNT_NUMBER or update kis_devlp.yaml.")

        return base_number, product_code

    def _ensure_auth(self, product_code: str) -> None:
        if not kis_auth.auth(self.env, product_code):
            raise RuntimeError("Failed to authenticate with KIS OpenAPI.")

    def _create_headers(self, payload: Dict[str, Any], tr_id: str) -> Dict[str, str]:
        headers = kis_auth.get_headers()
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        hash_value = kis_auth.create_hashkey(payload)
        if hash_value:
            headers["hashkey"] = hash_value
        return headers

    def _post(self, path: str, tr_id: str, payload: Dict[str, Any], product_code: str) -> Dict[str, Any]:
        self._ensure_auth(product_code)
        base_url = kis_auth.base_url.get(self.env)
        if not base_url:
            raise RuntimeError(f"Unsupported KIS environment: {self.env}")

        headers = self._create_headers(payload, tr_id)
        url = f"{base_url}{path}"
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        try:
            response.raise_for_status()
        except Exception as exc:
            logger.error("Order API request failed: %s", exc)
            raise

        data = response.json()
        return data

    @staticmethod
    def _format_price(price: Optional[Decimal]) -> str:
        if price is None:
            return "0"
        quantized = price.quantize(Decimal("0.01"))
        # strip trailing zeros and decimal if possible
        return format(quantized.normalize(), "f") if quantized % 1 else str(int(quantized))

    def place_cash_order(self, payload: MockCashOrderRequest) -> MockCashOrderResponse:
        account_base, product_code = self._resolve_account(payload.account_number, payload.product_code)

        tr_id = self._resolve_tr_id(payload.side)
        body = {
            "CANO": account_base,
            "ACNT_PRDT_CD": product_code,
            "PDNO": payload.symbol,
            "ORD_DVSN": payload.order_division,
            "ORD_QTY": str(payload.quantity),
            "ORD_UNPR": self._format_price(payload.price),
            "EXCG_ID_DVSN_CD": payload.exchange_code or self.default_exchange,
            "SLL_TYPE": "",
            "CNDT_PRIC": "",
        }

        data = self._post(self.ORDER_CASH_ENDPOINT, tr_id, body, product_code)
        return self._build_cash_order_response(data)

    def cancel_cash_order(self, payload: MockCancelRequest) -> MockCancelResponse:
        account_base, product_code = self._resolve_account(payload.account_number, payload.product_code)

        tr_id = "VTTC0013U" if self.env != "prod" else "TTTC0013U"
        body = {
            "CANO": account_base,
            "ACNT_PRDT_CD": product_code,
            "KRX_FWDG_ORD_ORGNO": payload.forwarding_org_number,
            "ORGN_ODNO": payload.original_order_number,
            "ORD_DVSN": payload.order_division,
            "RVSE_CNCL_DVSN_CD": payload.cancel_division,
            "ORD_QTY": str(payload.quantity),
            "ORD_UNPR": self._format_price(payload.price),
            "QTY_ALL_ORD_YN": "Y" if payload.full_quantity else "N",
            "EXCG_ID_DVSN_CD": payload.exchange_code or self.default_exchange,
        }

        data = self._post(self.ORDER_CANCEL_ENDPOINT, tr_id, body, product_code)
        return self._build_cancel_response(data)

    def _resolve_tr_id(self, side: OrderSide) -> str:
        if self.env == "prod":
            return "TTTC0012U" if side == OrderSide.BUY else "TTTC0011U"
        return "VTTC0012U" if side == OrderSide.BUY else "VTTC0011U"

    @staticmethod
    def _build_cash_order_response(data: Dict[str, Any]) -> MockCashOrderResponse:
        code = data.get("rt_cd", "")
        message = data.get("msg1", "")
        output = data.get("output") or data.get("output1") or {}

        if code != "0":
            logger.error("Mock order failed: %s - %s", data.get("msg_cd"), message)
            raise RuntimeError(message or "Order request failed")

        if isinstance(output, dict):
            cleaned_output = output
        else:
            cleaned_output = {}

        return MockCashOrderResponse(code=code, message=message, output=cleaned_output)

    @staticmethod
    def _build_cancel_response(data: Dict[str, Any]) -> MockCancelResponse:
        code = data.get("rt_cd", "")
        message = data.get("msg1", "")
        output = data.get("output") or data.get("output1") or {}

        if code != "0":
            logger.error("Mock cancel failed: %s - %s", data.get("msg_cd"), message)
            raise RuntimeError(message or "Cancel request failed")

        cleaned_output = output if isinstance(output, dict) else {}
        return MockCancelResponse(code=code, message=message, output=cleaned_output)


kis_order_service = KISOrderService()
