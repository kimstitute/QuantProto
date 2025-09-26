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
    ?¤ì‹œê°?ê¸ˆìœµ ?°ì´???œë¹„??    
    ?œêµ­?¬ìžì¦ê¶Œ Open APIë¥??µí•´ ?¤ì‹œê°??œì„¸ ?°ì´?°ë? ê°€?¸ì˜¤???œë¹„?¤ìž…?ˆë‹¤.
    """
    
    def __init__(self):
        """
        MarketDataService ?´ëž˜??ì´ˆê¸°??        """
        self.ws_connections = {}  # ?¹ì†Œì¼??°ê²° ?€??        self.subscribers = {}  # êµ¬ë…???€??        self.symbol_subscribers = {}  # ì¢…ëª©ë³?êµ¬ë…???€??    
    async def connect_websocket(self, tr_id: str) -> None:
        """
        WebSocket ?°ê²°???ì„±?©ë‹ˆ??
        
        Args:
            tr_id (str): ê±°ëž˜ ID
        """
        if tr_id in self.ws_connections and self.ws_connections[tr_id] is not None:
            return
        
        # ?¸ì¦ ?•ë³´ ê°€?¸ì˜¤ê¸?        app_key, access_token = kis_auth.auth_ws()
        ws_url = kis_auth.get_ws_url()
        
        try:
            # WebSocket ?°ê²°
            websocket = await websockets.connect(ws_url)
            
            # ?¤ë” ?„ì†¡
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
            
            # ?‘ë‹µ ?•ì¸
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("header", {}).get("result_code") == "0":
                logger.info(f"WebSocket ?°ê²° ?±ê³µ: {tr_id}")
                self.ws_connections[tr_id] = websocket
                
                # ë©”ì‹œì§€ ?˜ì‹  ë£¨í”„ ?œìž‘
                asyncio.create_task(self._receive_messages(tr_id, websocket))
            else:
                logger.error(f"WebSocket ?°ê²° ?¤íŒ¨: {response_data}")
                await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket ?°ê²° ?¤ë¥˜: {e}")
    
    async def _receive_messages(self, tr_id: str, websocket) -> None:
        """
        WebSocket?¼ë¡œë¶€??ë©”ì‹œì§€ë¥??˜ì‹ ?˜ëŠ” ë£¨í”„?…ë‹ˆ??
        
        Args:
            tr_id (str): ê±°ëž˜ ID
            websocket: WebSocket ?°ê²° ê°ì²´
        """
        try:
            while True:
                message = await websocket.recv()
                
                try:
                    data = json.loads(message)
                    
                    # ë©”ì‹œì§€ ì²˜ë¦¬
                    await self._process_message(tr_id, data)
                except json.JSONDecodeError:
                    logger.warning(f"JSON ?”ì½”???¤íŒ¨: {message}")
                except Exception as e:
                    logger.error(f"ë©”ì‹œì§€ ì²˜ë¦¬ ?¤ë¥˜: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket ?°ê²° ì¢…ë£Œ: {tr_id}")
        except Exception as e:
            logger.error(f"WebSocket ?˜ì‹  ?¤ë¥˜: {e}")
        finally:
            # ?°ê²° ?•ë¦¬
            self.ws_connections[tr_id] = None
    
    async def _process_message(self, tr_id: str, data: Dict[str, Any]) -> None:
        """
        ?˜ì‹ ??ë©”ì‹œì§€ë¥?ì²˜ë¦¬?©ë‹ˆ??
        
        Args:
            tr_id (str): ê±°ëž˜ ID
            data (Dict[str, Any]): ?˜ì‹ ???°ì´??        """
        # ?¤ë” ?•ì¸
        header = data.get("header", {})
        if header.get("result_code") != "0":
            logger.warning(f"?¤ë¥˜ ë©”ì‹œì§€ ?˜ì‹ : {data}")
            return
        
        # ë°”ë”” ?•ì¸
        body = data.get("body", {})
        if not body:
            logger.warning(f"ë¹?ë°”ë”” ?˜ì‹ : {data}")
            return
        
        # ì¢…ëª© ì½”ë“œ ?•ì¸
        symbol = body.get("symbol", "")
        if not symbol:
            logger.warning(f"ì¢…ëª© ì½”ë“œ ?†ìŒ: {data}")
            return
        
        # êµ¬ë…?ì—ê²??°ì´???„ë‹¬
        if symbol in self.symbol_subscribers:
            for callback in self.symbol_subscribers[symbol]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"ì½œë°± ?¤í–‰ ?¤ë¥˜: {e}")
    
    async def subscribe_stock_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        ì£¼ì‹ ?¤ì‹œê°??œì„¸ë¥?êµ¬ë…?©ë‹ˆ??
        
        Args:
            symbol (str): ì¢…ëª© ì½”ë“œ
            callback (Callable): ?°ì´???˜ì‹  ???¸ì¶œ??ì½œë°± ?¨ìˆ˜
        
        Returns:
            bool: êµ¬ë… ?±ê³µ ?¬ë?
        """
        # ?¸ì¦ ?•ì¸
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?¸ì¦ ?¤íŒ¨")
                return False
        
        # ê±°ëž˜ ID ?¤ì •
        tr_id = "H0STCNT0"  # êµ?‚´ì£¼ì‹ ?¤ì‹œê°„ì²´ê²°ê? (KRX)
        
        # WebSocket ?°ê²°
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # êµ¬ë… ?”ì²­
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?°ê²° ?†ìŒ: {tr_id}")
            return False
        
        try:
            # êµ¬ë… ?”ì²­ ?°ì´??            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: êµ¬ë…, 0: ?´ì?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # êµ¬ë…???±ë¡
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"?¤ì‹œê°??œì„¸ êµ¬ë… ?±ê³µ: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?¤ì‹œê°??œì„¸ êµ¬ë… ?¤ë¥˜: {e}")
            return False
    
    async def unsubscribe_stock_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        ì£¼ì‹ ?¤ì‹œê°??œì„¸ êµ¬ë…???´ì??©ë‹ˆ??
        
        Args:
            symbol (str): ì¢…ëª© ì½”ë“œ
            callback (Optional[Callable]): ?´ì????¹ì • ì½œë°± ?¨ìˆ˜ (None?´ë©´ ëª¨ë“  ì½œë°± ?´ì?)
        
        Returns:
            bool: ?´ì? ?±ê³µ ?¬ë?
        """
        # ê±°ëž˜ ID ?¤ì •
        tr_id = "H0STCNT0"  # êµ?‚´ì£¼ì‹ ?¤ì‹œê°„ì²´ê²°ê? (KRX)
        
        # WebSocket ?°ê²° ?•ì¸
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?°ê²° ?†ìŒ: {tr_id}")
            return False
        
        try:
            # êµ¬ë… ?´ì? ?”ì²­ ?°ì´??            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: êµ¬ë…, 0: ?´ì?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # êµ¬ë…???œê±°
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # ëª¨ë“  ì½œë°± ?œê±°
                    self.symbol_subscribers[symbol] = []
                else:
                    # ?¹ì • ì½œë°±ë§??œê±°
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"?¤ì‹œê°??œì„¸ êµ¬ë… ?´ì? ?±ê³µ: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?¤ì‹œê°??œì„¸ êµ¬ë… ?´ì? ?¤ë¥˜: {e}")
            return False
    
    async def subscribe_asking_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        ì£¼ì‹ ?¤ì‹œê°??¸ê?ë¥?êµ¬ë…?©ë‹ˆ??
        
        Args:
            symbol (str): ì¢…ëª© ì½”ë“œ
            callback (Callable): ?°ì´???˜ì‹  ???¸ì¶œ??ì½œë°± ?¨ìˆ˜
        
        Returns:
            bool: êµ¬ë… ?±ê³µ ?¬ë?
        """
        # ?¸ì¦ ?•ì¸
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?¸ì¦ ?¤íŒ¨")
                return False
        
        # ê±°ëž˜ ID ?¤ì •
        tr_id = "H0STASP0"  # êµ?‚´ì£¼ì‹ ?¤ì‹œê°„í˜¸ê°€ (KRX)
        
        # WebSocket ?°ê²°
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # êµ¬ë… ?”ì²­
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?°ê²° ?†ìŒ: {tr_id}")
            return False
        
        try:
            # êµ¬ë… ?”ì²­ ?°ì´??            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: êµ¬ë…, 0: ?´ì?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # êµ¬ë…???±ë¡
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"?¤ì‹œê°??¸ê? êµ¬ë… ?±ê³µ: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?¤ì‹œê°??¸ê? êµ¬ë… ?¤ë¥˜: {e}")
            return False
    
    async def unsubscribe_asking_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        ì£¼ì‹ ?¤ì‹œê°??¸ê? êµ¬ë…???´ì??©ë‹ˆ??
        
        Args:
            symbol (str): ì¢…ëª© ì½”ë“œ
            callback (Optional[Callable]): ?´ì????¹ì • ì½œë°± ?¨ìˆ˜ (None?´ë©´ ëª¨ë“  ì½œë°± ?´ì?)
        
        Returns:
            bool: ?´ì? ?±ê³µ ?¬ë?
        """
        # ê±°ëž˜ ID ?¤ì •
        tr_id = "H0STASP0"  # êµ?‚´ì£¼ì‹ ?¤ì‹œê°„í˜¸ê°€ (KRX)
        
        # WebSocket ?°ê²° ?•ì¸
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket ?°ê²° ?†ìŒ: {tr_id}")
            return False
        
        try:
            # êµ¬ë… ?´ì? ?”ì²­ ?°ì´??            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: êµ¬ë…, 0: ?´ì?
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # êµ¬ë…???œê±°
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # ëª¨ë“  ì½œë°± ?œê±°
                    self.symbol_subscribers[symbol] = []
                else:
                    # ?¹ì • ì½œë°±ë§??œê±°
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"?¤ì‹œê°??¸ê? êµ¬ë… ?´ì? ?±ê³µ: {symbol}")
            return True
        except Exception as e:
            logger.error(f"?¤ì‹œê°??¸ê? êµ¬ë… ?´ì? ?¤ë¥˜: {e}")
            return False
    
    async def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        ì£¼ì‹ ?„ìž¬ê°€ ?œì„¸ë¥?ì¡°íšŒ?©ë‹ˆ??
        
        Args:
            symbol (str): ì¢…ëª© ì½”ë“œ
        
        Returns:
            Dict[str, Any]: ì£¼ì‹ ?œì„¸ ?•ë³´
        """
        # ?¸ì¦ ?•ì¸
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?¸ì¦ ?¤íŒ¨")
                return {"error": "?¸ì¦ ?¤íŒ¨"}
        
        # URL ?¤ì •
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        # ?¤ë” ?¤ì •
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010100"  # ì£¼ì‹ ?„ìž¬ê°€ ?œì„¸ ì¡°íšŒ
        
        # ?Œë¼ë¯¸í„° ?¤ì •
        params = {
            "fid_cond_mrkt_div_code": "J",  # ì£¼ì‹, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API ?”ì²­
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # ?‘ë‹µ ?•ì¸
            if data.get("rt_cd") == "0":
                return data.get("output", {})
            else:
                logger.error(f"API ?¤ë¥˜: {data}")
                return {"error": data.get("msg_cd", "?????†ëŠ” ?¤ë¥˜")}
        except Exception as e:
            logger.error(f"API ?”ì²­ ?¤ë¥˜: {e}")
            return {"error": str(e)}
    
    async def get_stock_asking_price(self, symbol: str) -> Dict[str, Any]:
        """
        ì£¼ì‹ ?¸ê? ?•ë³´ë¥?ì¡°íšŒ?©ë‹ˆ??
        
        Args:
            symbol (str): ì¢…ëª© ì½”ë“œ
        
        Returns:
            Dict[str, Any]: ì£¼ì‹ ?¸ê? ?•ë³´
        """
        # ?¸ì¦ ?•ì¸
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("?¸ì¦ ?¤íŒ¨")
                return {"error": "?¸ì¦ ?¤íŒ¨"}
        
        # URL ?¤ì •
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        
        # ?¤ë” ?¤ì •
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010200"  # ì£¼ì‹ ?„ìž¬ê°€ ?¸ê? ì¡°íšŒ
        
        # ?Œë¼ë¯¸í„° ?¤ì •
        params = {
            "fid_cond_mrkt_div_code": "J",  # ì£¼ì‹, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API ?”ì²­
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # ?‘ë‹µ ?•ì¸
            if data.get("rt_cd") == "0":
                return {
                    "output1": data.get("output1", {}),  # ì¢…ëª© ?•ë³´
                    "output2": data.get("output2", [])   # ?¸ê? ?•ë³´
                }
            else:
                logger.error(f"API ?¤ë¥˜: {data}")
                return {"error": data.get("msg_cd", "?????†ëŠ” ?¤ë¥˜")}
        except Exception as e:
            logger.error(f"API ?”ì²­ ?¤ë¥˜: {e}")
            return {"error": str(e)}
    
    async def close_all_connections(self) -> None:
        """
        ëª¨ë“  WebSocket ?°ê²°??ì¢…ë£Œ?©ë‹ˆ??
        """
        for tr_id, websocket in self.ws_connections.items():
            if websocket:
                try:
                    await websocket.close()
                    logger.info(f"WebSocket ?°ê²° ì¢…ë£Œ: {tr_id}")
                except Exception as e:
                    logger.error(f"WebSocket ì¢…ë£Œ ?¤ë¥˜: {e}")
        
        self.ws_connections = {}
        self.symbol_subscribers = {}


# ?±ê????¸ìŠ¤?´ìŠ¤
market_data_service = MarketDataService()
