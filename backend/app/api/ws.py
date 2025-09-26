import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from ..services.market_data_service import market_data_service
from ..schemas.market_data import RealtimeStockPrice, RealtimeAskingPrice, WebSocketMessage, WebSocketResponse

router = APIRouter(
    prefix="/ws",
    tags=["websocket"],
)

logger = logging.getLogger("uvicorn.error")

# 연결된 WebSocket 클라이언트 관리
class ConnectionManager:
    def __init__(self):
        # 모든 활성 연결
        self.active_connections: List[WebSocket] = []
        # 종목별 구독자
        self.symbol_subscribers: Dict[str, Set[WebSocket]] = {}
        # 사용자별 구독 종목
        self.user_subscriptions: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """클라이언트 연결 수락"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_subscriptions[websocket] = set()
    
    def disconnect(self, websocket: WebSocket):
        """클라이언트 연결 해제"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # 사용자 구독 정리
        if websocket in self.user_subscriptions:
            symbols = self.user_subscriptions[websocket]
            for symbol in symbols:
                if symbol in self.symbol_subscribers and websocket in self.symbol_subscribers[symbol]:
                    self.symbol_subscribers[symbol].remove(websocket)
            
            del self.user_subscriptions[websocket]
    
    async def subscribe(self, websocket: WebSocket, symbol: str, data_type: str = "price"):
        """종목 구독"""
        # 종목 구독자 목록에 추가
        if symbol not in self.symbol_subscribers:
            self.symbol_subscribers[symbol] = set()
            
            # 실시간 데이터 구독 시작
            if data_type == "price":
                await market_data_service.subscribe_stock_price(symbol, self.broadcast_price)
            elif data_type == "asking":
                await market_data_service.subscribe_asking_price(symbol, self.broadcast_asking_price)
        
        self.symbol_subscribers[symbol].add(websocket)
        
        # 사용자 구독 목록에 추가
        if websocket not in self.user_subscriptions:
            self.user_subscriptions[websocket] = set()
        
        self.user_subscriptions[websocket].add(symbol)
        
        # 구독 확인 메시지 전송
        await self.send_personal_message(
            WebSocketResponse(
                type="subscribe_confirm",
                data={"symbol": symbol, "data_type": data_type}
            ).dict(),
            websocket
        )
    
    async def unsubscribe(self, websocket: WebSocket, symbol: str):
        """종목 구독 해제"""
        # 종목 구독자 목록에서 제거
        if symbol in self.symbol_subscribers and websocket in self.symbol_subscribers[symbol]:
            self.symbol_subscribers[symbol].remove(websocket)
            
            # 구독자가 없으면 실시간 데이터 구독 해제
            if not self.symbol_subscribers[symbol]:
                await market_data_service.unsubscribe_stock_price(symbol)
                await market_data_service.unsubscribe_asking_price(symbol)
                del self.symbol_subscribers[symbol]
        
        # 사용자 구독 목록에서 제거
        if websocket in self.user_subscriptions and symbol in self.user_subscriptions[websocket]:
            self.user_subscriptions[websocket].remove(symbol)
        
        # 구독 해제 확인 메시지 전송
        await self.send_personal_message(
            WebSocketResponse(
                type="unsubscribe_confirm",
                data={"symbol": symbol}
            ).dict(),
            websocket
        )
    
    async def broadcast_price(self, data: Dict[str, Any]):
        """실시간 시세 데이터 브로드캐스트"""
        try:
            # 데이터에서 종목 코드 추출
            symbol = data.get("body", {}).get("mksc_shrn_iscd", "")
            if not symbol:
                return
            
            # 종목 구독자에게 데이터 전송
            if symbol in self.symbol_subscribers:
                # 데이터 변환
                price_data = RealtimeStockPrice.from_websocket_data(data)
                
                # 응답 생성
                response = WebSocketResponse(
                    type="stock_price",
                    data=price_data.dict()
                ).dict()
                
                # 구독자에게 전송
                for websocket in self.symbol_subscribers[symbol]:
                    await self.send_personal_message(response, websocket)
        except Exception as e:
            logger.error(f"브로드캐스트 오류: {e}")
    
    async def broadcast_asking_price(self, data: Dict[str, Any]):
        """실시간 호가 데이터 브로드캐스트"""
        try:
            # 데이터에서 종목 코드 추출
            symbol = data.get("body", {}).get("mksc_shrn_iscd", "")
            if not symbol:
                return
            
            # 종목 구독자에게 데이터 전송
            if symbol in self.symbol_subscribers:
                # 데이터 변환
                asking_data = RealtimeAskingPrice.from_websocket_data(data)
                
                # 응답 생성
                response = WebSocketResponse(
                    type="asking_price",
                    data=asking_data.dict()
                ).dict()
                
                # 구독자에게 전송
                for websocket in self.symbol_subscribers[symbol]:
                    await self.send_personal_message(response, websocket)
        except Exception as e:
            logger.error(f"브로드캐스트 오류: {e}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """개인 메시지 전송"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"메시지 전송 오류: {e}")
            # 연결 오류 시 연결 해제 처리
            self.disconnect(websocket)


# 연결 관리자 인스턴스
manager = ConnectionManager()


@router.websocket("/market")
async def websocket_endpoint(websocket: WebSocket):
    """
    실시간 시장 데이터 WebSocket 엔드포인트
    
    클라이언트는 다음과 같은 메시지를 보낼 수 있습니다:
    - {"type": "subscribe", "data": {"symbol": "005930", "data_type": "price"}}
    - {"type": "unsubscribe", "data": {"symbol": "005930"}}
    - {"type": "ping", "data": {}}
    
    서버는 다음과 같은 메시지를 보냅니다:
    - {"type": "subscribe_confirm", "data": {"symbol": "005930", "data_type": "price"}}
    - {"type": "unsubscribe_confirm", "data": {"symbol": "005930"}}
    - {"type": "stock_price", "data": {...}}
    - {"type": "asking_price", "data": {...}}
    - {"type": "pong", "data": {}}
    - {"type": "error", "data": {"message": "오류 메시지"}}
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            
            try:
                # JSON 파싱
                message = json.loads(data)
                message_type = message.get("type", "")
                message_data = message.get("data", {})
                
                # 메시지 타입에 따른 처리
                if message_type == "subscribe":
                    symbol = message_data.get("symbol", "")
                    data_type = message_data.get("data_type", "price")
                    
                    if not symbol:
                        await manager.send_personal_message(
                            WebSocketResponse(
                                type="error",
                                data={"message": "종목 코드가 필요합니다."}
                            ).dict(),
                            websocket
                        )
                        continue
                    
                    await manager.subscribe(websocket, symbol, data_type)
                
                elif message_type == "unsubscribe":
                    symbol = message_data.get("symbol", "")
                    
                    if not symbol:
                        await manager.send_personal_message(
                            WebSocketResponse(
                                type="error",
                                data={"message": "종목 코드가 필요합니다."}
                            ).dict(),
                            websocket
                        )
                        continue
                    
                    await manager.unsubscribe(websocket, symbol)
                
                elif message_type == "ping":
                    # 핑-퐁 메시지 처리
                    await manager.send_personal_message(
                        WebSocketResponse(
                            type="pong",
                            data={}
                        ).dict(),
                        websocket
                    )
                
                else:
                    # 알 수 없는 메시지 타입
                    await manager.send_personal_message(
                        WebSocketResponse(
                            type="error",
                            data={"message": f"알 수 없는 메시지 타입: {message_type}"}
                        ).dict(),
                        websocket
                    )
            
            except json.JSONDecodeError:
                # JSON 파싱 오류
                await manager.send_personal_message(
                    WebSocketResponse(
                        type="error",
                        data={"message": "잘못된 JSON 형식입니다."}
                    ).dict(),
                    websocket
                )
            
            except Exception as e:
                # 기타 오류
                logger.error(f"메시지 처리 오류: {e}")
                await manager.send_personal_message(
                    WebSocketResponse(
                        type="error",
                        data={"message": f"오류: {str(e)}"}
                    ).dict(),
                    websocket
                )
    
    except WebSocketDisconnect:
        # 연결 해제
        manager.disconnect(websocket)
    
    except Exception as e:
        # 기타 오류
        logger.error(f"WebSocket 오류: {e}")
        manager.disconnect(websocket)