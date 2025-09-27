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
    Market data service helper.
    
    Provides integrations with the KIS OpenAPI for realtime and historical data.
    """
    
    def __init__(self):
        """
        Initialize MarketDataService resources.
        """
        self.ws_connections = {}  # Active websocket connections
        self.subscribers = {}  # Registered general subscribers
        self.symbol_subscribers = {}  # Subscribers per symbol
    
    async def connect_websocket(self, tr_id: str) -> None:
        """
        Establish websocket connection if required.
        
        Args:
            tr_id (str): Transaction identifier
        """
        if tr_id in self.ws_connections and self.ws_connections[tr_id] is not None:
            return
        
        # Acquire authentication tokens
        app_key, access_token = kis_auth.auth_ws()
        ws_url = kis_auth.get_ws_url()
        
        try:
            # Create websocket connection
            websocket = await websockets.connect(ws_url)
            
            # Validate response
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
            
            # Validate response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("header", {}).get("result_code") == "0":
                logger.info(f"WebSocket connected: {tr_id}")
                self.ws_connections[tr_id] = websocket
                
                # Start background message loop
                asyncio.create_task(self._receive_messages(tr_id, websocket))
            else:
                logger.error(f"WebSocket connection failed: {response_data}")
                await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
    
    async def _receive_messages(self, tr_id: str, websocket) -> None:
        """
        Receive messages from the websocket feed.
        
        Args:
            tr_id (str): Transaction identifier
            websocket: WebSocket connection instance
        """
        try:
            while True:
                message = await websocket.recv()
                
                try:
                    data = json.loads(message)
                    
                    #  
                    await self._process_message(tr_id, data)
                except json.JSONDecodeError:
                    logger.warning(f"JSON decode failed: {message}")
                except Exception as e:
                    logger.error(f"Message handling error: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed: {tr_id}")
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
        finally:
            # Validate response
            self.ws_connections[tr_id] = None
    
    async def _process_message(self, tr_id: str, data: Dict[str, Any]) -> None:
        """
        Handle incoming websocket message.
        
        Args:
            tr_id (str): Transaction identifier
            data (Dict[str, Any]): Message payload
        """
        # Build query parameters
        header = data.get("header", {})
        if header.get("result_code") != "0":
            logger.warning(f"Error message received: {data}")
            return
        
        # Issue subscription request
        body = data.get("body", {})
        if not body:
            logger.warning(f"Empty body received: {data}")
            return
        
        # Ensure symbol exists
        symbol = body.get("symbol", "")
        if not symbol:
            logger.warning(f"Missing symbol in payload: {data}")
            return
        
        # Dispatch to subscribers
        if symbol in self.symbol_subscribers:
            for callback in self.symbol_subscribers[symbol]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Subscriber callback error: {e}")
    
    async def subscribe_stock_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        Subscribe to realtime order book feed.
        
        Args:
            symbol (str): Instrument code
            callback (Callable): Async callback for updates
        
        Returns:
            bool: True if subscription succeeded
        """
        # Build query parameters
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("Authentication failed")
                return False
        
        # Determine transaction identifier
        tr_id = "H0STCNT0"  # Domestic stock realtime trade feed (KRX)
        
        # Ensure websocket connection
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # Issue subscription request
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket connection missing: {tr_id}")
            return False
        
        try:
            # Build subscription payload
            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: subscribe, 0: unsubscribe
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # Register subscriber
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"Subscribed to realtime price: {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe price feed: {e}")
            return False
    
    async def unsubscribe_stock_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Unsubscribe from realtime price feed.
        
        Args:
            symbol (str): Instrument code
            callback (Optional[Callable]): Specific callback to remove (None removes all)
        
        Returns:
            bool: True if unsubscribe succeeded
        """
        # Determine transaction identifier
        tr_id = "H0STCNT0"  # Domestic stock realtime trade feed (KRX)
        
        # Confirm websocket connection
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket connection missing: {tr_id}")
            return False
        
        try:
            # Build unsubscribe payload
            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: subscribe, 0: unsubscribe
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # Update subscriber list
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # Clear all callbacks
                    self.symbol_subscribers[symbol] = []
                else:
                    # Remove matching callback
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"Unsubscribed from price feed: {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe price feed: {e}")
            return False
    
    async def subscribe_asking_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        Subscribe to realtime order book feed.
        
        Args:
            symbol (str): Instrument code
            callback (Callable): Async callback for updates
        
        Returns:
            bool: True if subscription succeeded
        """
        # Build query parameters
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("Authentication failed")
                return False
        
        # Determine transaction identifier
        tr_id = "H0STASP0"  # Domestic stock realtime order book (KRX)
        
        # Ensure websocket connection
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # Issue subscription request
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket connection missing: {tr_id}")
            return False
        
        try:
            # Build subscription payload
            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: subscribe, 0: unsubscribe
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # Register subscriber
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"Subscribed to order book: {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe order book: {e}")
            return False
    
    async def unsubscribe_asking_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Unsubscribe from realtime order book feed.
        
        Args:
            symbol (str): Instrument code
            callback (Optional[Callable]): Specific callback to remove (None removes all)
        
        Returns:
            bool: True if unsubscribe succeeded
        """
        # Determine transaction identifier
        tr_id = "H0STASP0"  # Domestic stock realtime order book (KRX)
        
        # Confirm websocket connection
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket connection missing: {tr_id}")
            return False
        
        try:
            # Build unsubscribe payload
            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: subscribe, 0: unsubscribe
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # Update subscriber list
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # Clear all callbacks
                    self.symbol_subscribers[symbol] = []
                else:
                    # Remove matching callback
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"Unsubscribed from order book: {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe order book: {e}")
            return False
    
    async def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current stock price details.
        
        Args:
            symbol (str): Instrument code
        
        Returns:
            Dict[str, Any]: Stock price payload
        """
        # Build query parameters
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("Authentication failed")
                return {"error": "Authentication failed"}
        
        # Configure endpoint URL
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        # Build query parameters
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010100"  # Realtime price inquiry
        
        # Build query parameters
        params = {
            "fid_cond_mrkt_div_code": "J",  # , ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # Call API
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response
            if data.get("rt_cd") == "0":
                return data.get("output", {})
            else:
                logger.error(f"API error: {data}")
                return {"error": data.get("msg_cd", "Unknown error")}
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {"error": str(e)}
    
    async def get_stock_asking_price(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current order book snapshot.
        
        Args:
            symbol (str): Instrument code
        
        Returns:
            Dict[str, Any]: Order book payload
        """
        # Build query parameters
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("Authentication failed")
                return {"error": "Authentication failed"}
        
        # Configure endpoint URL
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        
        # Build query parameters
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010200"  # Realtime order book inquiry
        
        # Build query parameters
        params = {
            "fid_cond_mrkt_div_code": "J",  # , ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # Call API
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response
            if data.get("rt_cd") == "0":
                return {
                    "output1": data.get("output1", {}),  # Instrument info
                    "output2": data.get("output2", [])   # Depth levels
                }
            else:
                logger.error(f"API error: {data}")
                return {"error": data.get("msg_cd", "Unknown error")}
        except Exception as e:
            logger.error(f"API request error: {e}")
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
        Close all websocket connections.
        """
        for tr_id, websocket in self.ws_connections.items():
            if websocket:
                try:
                    await websocket.close()
                    logger.info(f"WebSocket connection closed: {tr_id}")
                except Exception as e:
                    logger.error(f"Error while closing websocket: {e}")
        
        self.ws_connections = {}
        self.symbol_subscribers = {}


# Singleton service instance
market_data_service = MarketDataService()
