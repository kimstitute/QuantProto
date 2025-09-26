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
    실시간 금융 데이터 서비스
    
    한국투자증권 Open API를 통해 실시간 시세 데이터를 가져오는 서비스입니다.
    """
    
    def __init__(self):
        """
        MarketDataService 클래스 초기화
        """
        self.ws_connections = {}  # 웹소켓 연결 저장
        self.subscribers = {}  # 구독자 저장
        self.symbol_subscribers = {}  # 종목별 구독자 저장
    
    async def connect_websocket(self, tr_id: str) -> None:
        """
        WebSocket 연결을 생성합니다.
        
        Args:
            tr_id (str): 거래 ID
        """
        if tr_id in self.ws_connections and self.ws_connections[tr_id] is not None:
            return
        
        # 인증 정보 가져오기
        app_key, access_token = kis_auth.auth_ws()
        ws_url = kis_auth.get_ws_url()
        
        try:
            # WebSocket 연결
            websocket = await websockets.connect(ws_url)
            
            # 헤더 전송
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
            
            # 응답 확인
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("header", {}).get("result_code") == "0":
                logger.info(f"WebSocket 연결 성공: {tr_id}")
                self.ws_connections[tr_id] = websocket
                
                # 메시지 수신 루프 시작
                asyncio.create_task(self._receive_messages(tr_id, websocket))
            else:
                logger.error(f"WebSocket 연결 실패: {response_data}")
                await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket 연결 오류: {e}")
    
    async def _receive_messages(self, tr_id: str, websocket) -> None:
        """
        WebSocket으로부터 메시지를 수신하는 루프입니다.
        
        Args:
            tr_id (str): 거래 ID
            websocket: WebSocket 연결 객체
        """
        try:
            while True:
                message = await websocket.recv()
                
                try:
                    data = json.loads(message)
                    
                    # 메시지 처리
                    await self._process_message(tr_id, data)
                except json.JSONDecodeError:
                    logger.warning(f"JSON 디코딩 실패: {message}")
                except Exception as e:
                    logger.error(f"메시지 처리 오류: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket 연결 종료: {tr_id}")
        except Exception as e:
            logger.error(f"WebSocket 수신 오류: {e}")
        finally:
            # 연결 정리
            self.ws_connections[tr_id] = None
    
    async def _process_message(self, tr_id: str, data: Dict[str, Any]) -> None:
        """
        수신된 메시지를 처리합니다.
        
        Args:
            tr_id (str): 거래 ID
            data (Dict[str, Any]): 수신된 데이터
        """
        # 헤더 확인
        header = data.get("header", {})
        if header.get("result_code") != "0":
            logger.warning(f"오류 메시지 수신: {data}")
            return
        
        # 바디 확인
        body = data.get("body", {})
        if not body:
            logger.warning(f"빈 바디 수신: {data}")
            return
        
        # 종목 코드 확인
        symbol = body.get("symbol", "")
        if not symbol:
            logger.warning(f"종목 코드 없음: {data}")
            return
        
        # 구독자에게 데이터 전달
        if symbol in self.symbol_subscribers:
            for callback in self.symbol_subscribers[symbol]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"콜백 실행 오류: {e}")
    
    async def subscribe_stock_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        주식 실시간 시세를 구독합니다.
        
        Args:
            symbol (str): 종목 코드
            callback (Callable): 데이터 수신 시 호출할 콜백 함수
        
        Returns:
            bool: 구독 성공 여부
        """
        # 인증 확인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("인증 실패")
                return False
        
        # 거래 ID 설정
        tr_id = "H0STCNT0"  # 국내주식 실시간체결가 (KRX)
        
        # WebSocket 연결
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # 구독 요청
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket 연결 없음: {tr_id}")
            return False
        
        try:
            # 구독 요청 데이터
            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: 구독, 0: 해지
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # 구독자 등록
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"실시간 시세 구독 성공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"실시간 시세 구독 오류: {e}")
            return False
    
    async def unsubscribe_stock_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        주식 실시간 시세 구독을 해지합니다.
        
        Args:
            symbol (str): 종목 코드
            callback (Optional[Callable]): 해지할 특정 콜백 함수 (None이면 모든 콜백 해지)
        
        Returns:
            bool: 해지 성공 여부
        """
        # 거래 ID 설정
        tr_id = "H0STCNT0"  # 국내주식 실시간체결가 (KRX)
        
        # WebSocket 연결 확인
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket 연결 없음: {tr_id}")
            return False
        
        try:
            # 구독 해지 요청 데이터
            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: 구독, 0: 해지
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # 구독자 제거
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # 모든 콜백 제거
                    self.symbol_subscribers[symbol] = []
                else:
                    # 특정 콜백만 제거
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"실시간 시세 구독 해지 성공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"실시간 시세 구독 해지 오류: {e}")
            return False
    
    async def subscribe_asking_price(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """
        주식 실시간 호가를 구독합니다.
        
        Args:
            symbol (str): 종목 코드
            callback (Callable): 데이터 수신 시 호출할 콜백 함수
        
        Returns:
            bool: 구독 성공 여부
        """
        # 인증 확인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("인증 실패")
                return False
        
        # 거래 ID 설정
        tr_id = "H0STASP0"  # 국내주식 실시간호가 (KRX)
        
        # WebSocket 연결
        if tr_id not in self.ws_connections or self.ws_connections[tr_id] is None:
            await self.connect_websocket(tr_id)
        
        # 구독 요청
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket 연결 없음: {tr_id}")
            return False
        
        try:
            # 구독 요청 데이터
            subscribe_data = {
                "header": {
                    "tr_type": "1",  # 1: 구독, 0: 해지
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(subscribe_data))
            
            # 구독자 등록
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = []
            
            self.symbol_subscribers[symbol].append(callback)
            
            logger.info(f"실시간 호가 구독 성공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"실시간 호가 구독 오류: {e}")
            return False
    
    async def unsubscribe_asking_price(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        주식 실시간 호가 구독을 해지합니다.
        
        Args:
            symbol (str): 종목 코드
            callback (Optional[Callable]): 해지할 특정 콜백 함수 (None이면 모든 콜백 해지)
        
        Returns:
            bool: 해지 성공 여부
        """
        # 거래 ID 설정
        tr_id = "H0STASP0"  # 국내주식 실시간호가 (KRX)
        
        # WebSocket 연결 확인
        websocket = self.ws_connections.get(tr_id)
        if not websocket:
            logger.error(f"WebSocket 연결 없음: {tr_id}")
            return False
        
        try:
            # 구독 해지 요청 데이터
            unsubscribe_data = {
                "header": {
                    "tr_type": "0",  # 1: 구독, 0: 해지
                    "tr_id": tr_id,
                    "tr_key": symbol
                }
            }
            
            await websocket.send(json.dumps(unsubscribe_data))
            
            # 구독자 제거
            if symbol in self.symbol_subscribers:
                if callback is None:
                    # 모든 콜백 제거
                    self.symbol_subscribers[symbol] = []
                else:
                    # 특정 콜백만 제거
                    self.symbol_subscribers[symbol] = [
                        cb for cb in self.symbol_subscribers[symbol] if cb != callback
                    ]
            
            logger.info(f"실시간 호가 구독 해지 성공: {symbol}")
            return True
        except Exception as e:
            logger.error(f"실시간 호가 구독 해지 오류: {e}")
            return False
    
    async def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        주식 현재가 시세를 조회합니다.
        
        Args:
            symbol (str): 종목 코드
        
        Returns:
            Dict[str, Any]: 주식 시세 정보
        """
        # 인증 확인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("인증 실패")
                return {"error": "인증 실패"}
        
        # URL 설정
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        # 헤더 설정
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010100"  # 주식 현재가 시세 조회
        
        # 파라미터 설정
        params = {
            "fid_cond_mrkt_div_code": "J",  # 주식, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API 요청
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # 응답 확인
            if data.get("rt_cd") == "0":
                return data.get("output", {})
            else:
                logger.error(f"API 오류: {data}")
                return {"error": data.get("msg_cd", "알 수 없는 오류")}
        except Exception as e:
            logger.error(f"API 요청 오류: {e}")
            return {"error": str(e)}
    
    async def get_stock_asking_price(self, symbol: str) -> Dict[str, Any]:
        """
        주식 호가 정보를 조회합니다.
        
        Args:
            symbol (str): 종목 코드
        
        Returns:
            Dict[str, Any]: 주식 호가 정보
        """
        # 인증 확인
        if not kis_auth.access_token:
            if not kis_auth.auth():
                logger.error("인증 실패")
                return {"error": "인증 실패"}
        
        # URL 설정
        base_url = "https://openapi.koreainvestment.com:9443" if kis_auth.env == "prod" else "https://openapivts.koreainvestment.com:29443"
        url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        
        # 헤더 설정
        headers = kis_auth.get_headers()
        headers["tr_id"] = "FHKST01010200"  # 주식 현재가 호가 조회
        
        # 파라미터 설정
        params = {
            "fid_cond_mrkt_div_code": "J",  # 주식, ETF, ETN
            "fid_input_iscd": symbol
        }
        
        try:
            # API 요청
            import requests
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # 응답 확인
            if data.get("rt_cd") == "0":
                return {
                    "output1": data.get("output1", {}),  # 종목 정보
                    "output2": data.get("output2", [])   # 호가 정보
                }
            else:
                logger.error(f"API 오류: {data}")
                return {"error": data.get("msg_cd", "알 수 없는 오류")}
        except Exception as e:
            logger.error(f"API 요청 오류: {e}")
            return {"error": str(e)}
    
    async def close_all_connections(self) -> None:
        """
        모든 WebSocket 연결을 종료합니다.
        """
        for tr_id, websocket in self.ws_connections.items():
            if websocket:
                try:
                    await websocket.close()
                    logger.info(f"WebSocket 연결 종료: {tr_id}")
                except Exception as e:
                    logger.error(f"WebSocket 종료 오류: {e}")
        
        self.ws_connections = {}
        self.symbol_subscribers = {}


# 싱글톤 인스턴스
market_data_service = MarketDataService()