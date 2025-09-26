import json
import logging
import asyncio
import websockets
import datetime as dt
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union, Tuple
from datetime import datetime

from .kis_auth import kis_auth

logger = logging.getLogger("uvicorn.error")

class MarketDataService:
    """
    ?ㅼ떆媛?湲덉쑖 ?곗씠???쒕퉬??
    
    ?쒓뎅?ъ옄利앷텒 Open API瑜??듯빐 ?ㅼ떆媛??쒖꽭 ?곗씠?곕? 媛?몄삤???쒕퉬?ㅼ엯?덈떎.
    """
    
    def __init__(self):
        """
        MarketDataService ?대옒??珥덇린??
        """
        self.ws_connections = {}  # ?뱀냼耳??곌껐 ???
        self.subscribers = {}  # 援щ룆?????
        self.symbol_subscribers = {}  # 醫낅ぉ蹂?援щ룆?????
    
    async def connect_websocket(self, tr_id: str) -> None:
        """
        WebSocket ?곌껐???앹꽦?⑸땲??
        
        Args:
            tr_id (str): 嫄곕옒 ID
        """
        if tr_id in self.ws_connections and self.ws_connections[tr_id] is not None:
            return
        
        # ?몄쬆 ?뺣낫 媛?몄삤湲?
        app_key, access_token = kis_auth.auth_ws()
        ws_url = kis_auth.get_ws_url()
        
        try:
            # WebSocket ?곌껐
            websocket = await websockets.connect(ws_url)
            
            # ?ㅻ뜑 ?꾩넚
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
            
            # ?묐떟 ?뺤씤
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("header", {}).get("result_code") == "0":
                logger.info(f"WebSocket ?곌껐 ?깃났: {tr_id}")
                self.ws_connections[tr_id] = websocket
                
                # 硫붿떆吏 ?섏떊 猷⑦봽 ?쒖옉
                asyncio.create_task(self._receive_messages(tr_id, websocket))
            else:
                logger.error(f"WebSocket ?곌껐 ?ㅽ뙣: {response_data}")
                await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket ?곌껐 ?ㅻ쪟: {e}")
    
    async def _receive_messages(self, tr_id: str, websocket) -> None:
        """
        WebSocket?쇰줈遺??硫붿떆吏瑜??섏떊?섎뒗 猷⑦봽?낅땲??
        
        Args:
            tr_id (str): 嫄곕옒 ID
            websocket: WebSocket ?곌껐 媛앹껜
        """
        try:
            while True:
                message = await websocket.recv()
                
                try:
                    data = json.loads(message)
                    
                    # 硫붿떆吏 泥섎━
                    await self._process_message(tr_id, data)
                except json.JSONDecodeError:
                    logger.warning(f"JSON ?붿퐫???ㅽ뙣: {message}")
                except Exception as e:
                    logger.error(f"硫붿떆吏 泥섎━ ?ㅻ쪟: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket ?곌껐 醫낅즺: {tr_id}")
        except Exception as e:
            logger.error(f"WebSocket ?섏떊 ?ㅻ쪟: {e}")
        finally:
            # ?곌껐 ?뺣━
            self.ws_connections[tr_id] = None
    
    async def _process_message(self, tr_id: str, data: Dict[str, Any]) -> None:
        """
        ?섏떊??硫붿떆吏瑜?泥섎━?⑸땲??
        
        Args:
            tr_id (str): 嫄곕옒 ID
            data (Dict[str, Any]): ?섏떊???곗씠??
        """
        # ?ㅻ뜑 ?뺤씤
        header = data.get("header", {})
        if header.get("result_code") != "0":
            logger.warning(f"?ㅻ쪟 硫붿떆吏 ?섏떊: {data}")
            return
        
        # 諛붾뵒 ?뺤씤
        body = data.get("body", {})
        if not body:
            logger.warning(f"鍮?諛붾뵒 ?섏떊: {data}")
            return
        
        # 醫낅ぉ 肄붾뱶 ?뺤씤
        symbol = body.get("symbol", "")
        if not symbol:
            logger.warning(f"醫낅ぉ 肄붾뱶 ?놁쓬: {data}")
            return
        
        # 援щ룆?먯뿉寃??곗씠???꾨떖
        if symbol in self.symbol_subscribers:
            for callback in self.symbol_subscribers[symbol]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"肄쒕갚 ?ㅽ뻾 ?ㅻ쪟: {e}")
    
    async def subscribe_stock_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        二쇱떇 ?ㅼ떆媛??쒖꽭瑜?援щ룆?⑸땲??
        
        Args:
            symbol (str): 醫낅ぉ 肄붾뱶
            callback (Callable): ?곗씠???섏떊 ???몄텧??肄쒕갚 ?⑥닔
        
        Returns:
            bool: 援щ룆 ?깃났 ?щ?
        """
        # ?몄쬆 ?뺤씤
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?몄쬆 ?ㅽ뙣")
                return False
        
        # 嫄곕옒 ID ?ㅼ젙
        tr_id = "H0STCNT0"  # 援?궡二쇱떇 ?ㅼ떆媛꾩껜寃곌? (KRX)
        
        # WebSocket ?곌껐
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # 援щ룆 ?붿껌
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?곌껐 ?놁쓬: {tr_id}")
            return False
        
        try:
            # 援щ룆 ?붿껌 ?곗씠??
            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: 援щ룆, 0: ?댁?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # 援щ룆???깅줉
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"?ㅼ떆媛??쒖꽭 援щ룆 ?깃났: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?ㅼ떆媛??쒖꽭 援щ룆 ?ㅻ쪟: {e}")
            return False
    
    async def unsubscribe_stock_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        二쇱떇 ?ㅼ떆媛??쒖꽭 援щ룆???댁??⑸땲??
        
        Args:
            symbol (str): 醫낅ぉ 肄붾뱶
            callback (Optional[Callable]): ?댁????뱀젙 肄쒕갚 ?⑥닔 (None?대㈃ 紐⑤뱺 肄쒕갚 ?댁?)
        
        Returns:
            bool: ?댁? ?깃났 ?щ?
        """
        # 嫄곕옒 ID ?ㅼ젙
        tr_id = "H0STCNT0"  # 援?궡二쇱떇 ?ㅼ떆媛꾩껜寃곌? (KRX)
        
        # WebSocket ?곌껐 ?뺤씤
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?곌껐 ?놁쓬: {tr_id}")
            return False
        
        try:
            # 援щ룆 ?댁? ?붿껌 ?곗씠??
            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: 援щ룆, 0: ?댁?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # 援щ룆???쒓굅
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # 紐⑤뱺 肄쒕갚 ?쒓굅
                    self.symbol_subscribers[symbol] = []
                else:
                    # ?뱀젙 肄쒕갚留??쒓굅
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"?ㅼ떆媛??쒖꽭 援щ룆 ?댁? ?깃났: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?ㅼ떆媛??쒖꽭 援щ룆 ?댁? ?ㅻ쪟: {e}")
            return False
    
    async def subscribe_asking_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        二쇱떇 ?ㅼ떆媛??멸?瑜?援щ룆?⑸땲??
        
        Args:
            symbol (str): 醫낅ぉ 肄붾뱶
            callback (Callable): ?곗씠???섏떊 ???몄텧??肄쒕갚 ?⑥닔
        
        Returns:
            bool: 援щ룆 ?깃났 ?щ?
        """
        # ?몄쬆 ?뺤씤
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?몄쬆 ?ㅽ뙣")
                return False
        
        # 嫄곕옒 ID ?ㅼ젙
        tr_id = "H0STASP0"  # 援?궡二쇱떇 ?ㅼ떆媛꾪샇媛 (KRX)
        
        # WebSocket ?곌껐
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # 援щ룆 ?붿껌
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?곌껐 ?놁쓬: {tr_id}")
            return False
        
        try:
            # 援щ룆 ?붿껌 ?곗씠??
            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: 援щ룆, 0: ?댁?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # 援щ룆???깅줉
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"?ㅼ떆媛??멸? 援щ룆 ?깃났: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?ㅼ떆媛??멸? 援щ룆 ?ㅻ쪟: {e}")
            return False
    
    async def unsubscribe_asking_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        二쇱떇 ?ㅼ떆媛??멸? 援щ룆???댁??⑸땲??
        
        Args:
            symbol (str): 醫낅ぉ 肄붾뱶
            callback (Optional[Callable]): ?댁????뱀젙 肄쒕갚 ?⑥닔 (None?대㈃ 紐⑤뱺 肄쒕갚 ?댁?)
        
        Returns:
            bool: ?댁? ?깃났 ?щ?
        """
        # 嫄곕옒 ID ?ㅼ젙
        tr_id = "H0STASP0"  # 援?궡二쇱떇 ?ㅼ떆媛꾪샇媛 (KRX)
        
        # WebSocket ?곌껐 ?뺤씤
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?곌껐 ?놁쓬: {tr_id}")
            return False
        
        try:
            # 援щ룆 ?댁? ?붿껌 ?곗씠??
            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: 援щ룆, 0: ?댁?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # 援щ룆???쒓굅
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # 紐⑤뱺 肄쒕갚 ?쒓굅
                    self.symbol_subscribers[symbol] = []
                else:
                    # ?뱀젙 肄쒕갚留??쒓굅
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"?ㅼ떆媛??멸? 援щ룆 ?댁? ?깃났: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?ㅼ떆媛??멸? 援щ룆 ?댁? ?ㅻ쪟: {e}")
            return False
    
    async def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        二쇱떇 ?꾩옱媛 ?쒖꽭瑜?議고쉶?⑸땲??
        
        Args:
            symbol (str): 醫낅ぉ 肄붾뱶
        
        Returns:
            Dict[str, Any]: 二쇱떇 ?쒖꽭 ?뺣낫
        """
        # ?몄쬆 ?뺤씤
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?몄쬆 ?ㅽ뙣")
                return {"error": "?몄쬆 ?ㅽ뙣"}
        
        # URL ?ㅼ젙
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        # ?ㅻ뜑 ?ㅼ젙
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010100"  # 二쇱떇 ?꾩옱媛 ?쒖꽭 議고쉶
        
        # ?뚮씪誘명꽣 ?ㅼ젙
        params = {
            "fid_cond_mrkt_div_code": "J",  # 二쇱떇, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API ?붿껌
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # ?묐떟 ?뺤씤
            if data.get("rt_cd") == "0":
                return data.get("output", {})
            else:
                logger.error(f"API ?ㅻ쪟: {data}")
                return {"error": data.get("msg_cd", "?????녿뒗 ?ㅻ쪟")}
        except Exception as e:
            logger.error(f"API ?붿껌 ?ㅻ쪟: {e}")
            return {"error": str(e)}
    
    async def get_stock_asking_price(self, symbol: str) -> Dict[str, Any]:
        """
        二쇱떇 ?멸? ?뺣낫瑜?議고쉶?⑸땲??
        
        Args:
            symbol (str): 醫낅ぉ 肄붾뱶
        
        Returns:
            Dict[str, Any]: 二쇱떇 ?멸? ?뺣낫
        """
        # ?몄쬆 ?뺤씤
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?몄쬆 ?ㅽ뙣")
                return {"error": "?몄쬆 ?ㅽ뙣"}
        
        # URL ?ㅼ젙
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        
        # ?ㅻ뜑 ?ㅼ젙
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010200"  # 二쇱떇 ?꾩옱媛 ?멸? 議고쉶
        
        # ?뚮씪誘명꽣 ?ㅼ젙
        params = {
            "fid_cond_mrkt_div_code": "J",  # 二쇱떇, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API ?붿껌
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # ?묐떟 ?뺤씤
            if data.get("rt_cd") == "0":
                return {
                    "output1": data.get("output1", {}),  # 醫낅ぉ ?뺣낫
                    "output2": data.get("output2", [])   # ?멸? ?뺣낫
                }
            else:
                logger.error(f"API ?ㅻ쪟: {data}")
                return {"error": data.get("msg_cd", "?????녿뒗 ?ㅻ쪟")}
        except Exception as e:
            logger.error(f"API ?붿껌 ?ㅻ쪟: {e}")
            return {"error": str(e)}
    

    async def get_stock_price_history(self, symbol: str, count: int = 30) -> Dict[str, Any]:
        """Fetch daily price history for the requested symbol."""
        if count <= 0:
            count = 1

        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("Authentication failed")
                return {"error": "Authentication failed"}

        today = dt.date.today()
        end_date = today.strftime("%Y%m%d")
        lookback_days = max(count * 2, 60)
        start_date = (today - dt.timedelta(days=lookback_days)).strftime("%Y%m%d")

        base_url = (
            "https://openapi.koreainvestment.com:9443"
            if kis_auth.env == "prod"
            else "https://openapivts.koreainvestment.com:29443"
        )
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"

        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010400"  # Daily price lookup

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": symbol,
            "fid_input_date_1": start_date,
            "fid_input_date_2": end_date,
            "fid_period_div_code": "D",
            "fid_org_adj_prc": "0",
        }

        try:
            import requests

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("rt_cd") != "0":
                logger.error(f"API error: {data}")
                return {"error": data.get("msg_cd", "Unknown error")}

            candles = data.get("output1") or data.get("output", [])
            if not candles:
                return {"error": "No data returned"}

            candles_sorted = sorted(
                candles,
                key=lambda item: item.get("stck_bsop_date", ""),
            )
            limited = candles_sorted[-count:]

            info = data.get("output2") or {}
            return {
                "symbol": symbol,
                "name": info.get("hts_kor_isnm", ""),
                "candles": limited,
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"API request error: {exc}")
            return {"error": str(exc)}


    async def close_all_connections(self) -> None:
        """
        紐⑤뱺 WebSocket ?곌껐??醫낅즺?⑸땲??
        """
        for tr_id, websocket in self.ws_connections.items():
            if websocket:
                try:
                    await websocket.close()
                    logger.info(f"WebSocket ?곌껐 醫낅즺: {tr_id}")
                except Exception as e:
                    logger.error(f"WebSocket 醫낅즺 ?ㅻ쪟: {e}")
        
        self.ws_connections = {}
        self.symbol_subscribers = {}


# ?깃????몄뒪?댁뒪
market_data_service = MarketDataService()
