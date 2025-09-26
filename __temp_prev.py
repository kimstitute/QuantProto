import json
import logging
import asyncio
import websockets
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union, Tuple
from datetime import datetime

from .kis_auth import kis_auth

logger = logging.getLogger("uvicorn.error")

class MarketDataService:
    """
    ?�시�?금융 ?�이???�비??    
    ?�국?�자증권 Open API�??�해 ?�시�??�세 ?�이?��? 가?�오???�비?�입?�다.
    """
    
    def __init__(self):
        """
        MarketDataService ?�래??초기??        """
        self.ws_connections = {}  # ?�소�??�결 ?�??        self.subscribers = {}  # 구독???�??        self.symbol_subscribers = {}  # 종목�?구독???�??    
    async def connect_websocket(self, tr_id: str) -> None:
        """
        WebSocket ?�결???�성?�니??
        
        Args:
            tr_id (str): 거래 ID
        """
        if tr_id in self.ws_connections and self.ws_connections[tr_id] is not None:
            return
        
        # ?�증 ?�보 가?�오�?        app_key, access_token = kis_auth.auth_ws()
        ws_url = kis_auth.get_ws_url()
        
        try:
            # WebSocket ?�결
            websocket = await websockets.connect(ws_url)
            
            # ?�더 ?�송
            header_data = {
                "header": {
                    "appkey": app_key,
                    "appsecret": "",
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8"
                },
                "body": {
                    "tr_id": tr_id,
                    "tr_key": ""
                }
            }
            
            await websocket.send(json.dumps(header_data))
            
            # ?�답 ?�인
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("header", {}).get("result_code") == "0":
                logger.info(f"WebSocket ?�결 ?�공: {tr_id}")
                self.ws_connections[tr_id] = websocket
                
                # 메시지 ?�신 루프 ?�작
                asyncio.create_task(self._receive_messages(tr_id, websocket))
            else:
                logger.error(f"WebSocket ?�결 ?�패: {response_data}")
                await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket ?�결 ?�류: {e}")
    
    async def _receive_messages(self, tr_id: str, websocket) -> None:
        """
        WebSocket?�로부??메시지�??�신?�는 루프?�니??
        
        Args:
            tr_id (str): 거래 ID
            websocket: WebSocket ?�결 객체
        """
        try:
            while True:
                message = await websocket.recv()
                
                try:
                    data = json.loads(message)
                    
                    # 메시지 처리
                    await self._process_message(tr_id, data)
                except json.JSONDecodeError:
                    logger.warning(f"JSON ?�코???�패: {message}")
                except Exception as e:
                    logger.error(f"메시지 처리 ?�류: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket ?�결 종료: {tr_id}")
        except Exception as e:
            logger.error(f"WebSocket ?�신 ?�류: {e}")
        finally:
            # ?�결 ?�리
            self.ws_connections[tr_id] = None
    
    async def _process_message(self, tr_id: str, data: Dict[str, Any]) -> None:
        """
        ?�신??메시지�?처리?�니??
        
        Args:
            tr_id (str): 거래 ID
            data (Dict[str, Any]): ?�신???�이??        """
        # ?�더 ?�인
        header = data.get("header", {})
        if header.get("result_code") != "0":
            logger.warning(f"?�류 메시지 ?�신: {data}")
            return
        
        # 바디 ?�인
        body = data.get("body", {})
        if not body:
            logger.warning(f"�?바디 ?�신: {data}")
            return
        
        # 종목 코드 ?�인
        symbol = body.get("symbol", "")
        if not symbol:
            logger.warning(f"종목 코드 ?�음: {data}")
            return
        
        # 구독?�에�??�이???�달
        if symbol in self.symbol_subscribers:
            for callback in self.symbol_subscribers[symbol]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"콜백 ?�행 ?�류: {e}")
    
    async def subscribe_stock_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        주식 ?�시�??�세�?구독?�니??
        
        Args:
            symbol (str): 종목 코드
            callback (Callable): ?�이???�신 ???�출??콜백 ?�수
        
        Returns:
            bool: 구독 ?�공 ?��?
        """
        # ?�증 ?�인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?�증 ?�패")
                return False
        
        # 거래 ID ?�정
        tr_id = "H0STCNT0"  # �?��주식 ?�시간체결�? (KRX)
        
        # WebSocket ?�결
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # 구독 ?�청
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?�결 ?�음: {tr_id}")
            return False
        
        try:
            # 구독 ?�청 ?�이??            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: 구독, 0: ?��?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # 구독???�록
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"?�시�??�세 구독 ?�공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?�시�??�세 구독 ?�류: {e}")
            return False
    
    async def unsubscribe_stock_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        주식 ?�시�??�세 구독???��??�니??
        
        Args:
            symbol (str): 종목 코드
            callback (Optional[Callable]): ?��????�정 콜백 ?�수 (None?�면 모든 콜백 ?��?)
        
        Returns:
            bool: ?��? ?�공 ?��?
        """
        # 거래 ID ?�정
        tr_id = "H0STCNT0"  # �?��주식 ?�시간체결�? (KRX)
        
        # WebSocket ?�결 ?�인
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?�결 ?�음: {tr_id}")
            return False
        
        try:
            # 구독 ?��? ?�청 ?�이??            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: 구독, 0: ?��?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # 구독???�거
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # 모든 콜백 ?�거
                    self.symbol_subscribers[symbol] = []
                else:
                    # ?�정 콜백�??�거
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"?�시�??�세 구독 ?��? ?�공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?�시�??�세 구독 ?��? ?�류: {e}")
            return False
    
    async def subscribe_asking_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        주식 ?�시�??��?�?구독?�니??
        
        Args:
            symbol (str): 종목 코드
            callback (Callable): ?�이???�신 ???�출??콜백 ?�수
        
        Returns:
            bool: 구독 ?�공 ?��?
        """
        # ?�증 ?�인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?�증 ?�패")
                return False
        
        # 거래 ID ?�정
        tr_id = "H0STASP0"  # �?��주식 ?�시간호가 (KRX)
        
        # WebSocket ?�결
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # 구독 ?�청
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?�결 ?�음: {tr_id}")
            return False
        
        try:
            # 구독 ?�청 ?�이??            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: 구독, 0: ?��?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # 구독???�록
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"?�시�??��? 구독 ?�공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?�시�??��? 구독 ?�류: {e}")
            return False
    
    async def unsubscribe_asking_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        주식 ?�시�??��? 구독???��??�니??
        
        Args:
            symbol (str): 종목 코드
            callback (Optional[Callable]): ?��????�정 콜백 ?�수 (None?�면 모든 콜백 ?��?)
        
        Returns:
            bool: ?��? ?�공 ?��?
        """
        # 거래 ID ?�정
        tr_id = "H0STASP0"  # �?��주식 ?�시간호가 (KRX)
        
        # WebSocket ?�결 ?�인
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?�결 ?�음: {tr_id}")
            return False
        
        try:
            # 구독 ?��? ?�청 ?�이??            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: 구독, 0: ?��?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # 구독???�거
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # 모든 콜백 ?�거
                    self.symbol_subscribers[symbol] = []
                else:
                    # ?�정 콜백�??�거
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"?�시�??��? 구독 ?��? ?�공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?�시�??��? 구독 ?��? ?�류: {e}")
            return False
    
    async def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        주식 ?�재가 ?�세�?조회?�니??
        
        Args:
            symbol (str): 종목 코드
        
        Returns:
            Dict[str, Any]: 주식 ?�세 ?�보
        """
        # ?�증 ?�인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?�증 ?�패")
                return {"error": "?�증 ?�패"}
        
        # URL ?�정
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        # ?�더 ?�정
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010100"  # 주식 ?�재가 ?�세 조회
        
        # ?�라미터 ?�정
        params = {
            "fid_cond_mrkt_div_code": "J",  # 주식, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API ?�청
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # ?�답 ?�인
            if data.get("rt_cd") == "0":
                return data.get("output", {})
            else:
                logger.error(f"API ?�류: {data}")
                return {"error": data.get("msg_cd", "?????�는 ?�류")}
        except Exception as e:
            logger.error(f"API ?�청 ?�류: {e}")
            return {"error": str(e)}
    
    async def get_stock_asking_price(self, symbol: str) -> Dict[str, Any]:
        """
        주식 ?��? ?�보�?조회?�니??
        
        Args:
            symbol (str): 종목 코드
        
        Returns:
            Dict[str, Any]: 주식 ?��? ?�보
        """
        # ?�증 ?�인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?�증 ?�패")
                return {"error": "?�증 ?�패"}
        
        # URL ?�정
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        
        # ?�더 ?�정
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010200"  # 주식 ?�재가 ?��? 조회
        
        # ?�라미터 ?�정
        params = {
            "fid_cond_mrkt_div_code": "J",  # 주식, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API ?�청
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # ?�답 ?�인
            if data.get("rt_cd") == "0":
                return {
                    "output1": data.get("output1", {}),  # 종목 ?�보
                    "output2": data.get("output2", [])   # ?��? ?�보
                }
            else:
                logger.error(f"API ?�류: {data}")
                return {"error": data.get("msg_cd", "?????�는 ?�류")}
        except Exception as e:
            logger.error(f"API ?�청 ?�류: {e}")
            return {"error": str(e)}
    
    async def close_all_connections(self) -> None:
        """
        모든 WebSocket ?�결??종료?�니??
        """
        for tr_id, websocket in self.ws_connections.items():
            if websocket:
                try:
                    await websocket.close()
                    logger.info(f"WebSocket ?�결 종료: {tr_id}")
                except Exception as e:
                    logger.error(f"WebSocket 종료 ?�류: {e}")
        
        self.ws_connections = {}
        self.symbol_subscribers = {}


# ?��????�스?�스
market_data_service = MarketDataService()
