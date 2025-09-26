import os
import yaml
import json
import logging
import requests
import datetime
import hashlib
import base64
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("uvicorn.error")

class KISAuth:
    """
    한국투자증권 Open API 인증 클래스
    
    이 클래스는 한국투자증권 Open API에 대한 인증을 처리하고 토큰을 관리합니다.
    """
    
    def __init__(self):
        """
        KISAuth 클래스 초기화
        
        설정 파일을 로드하고 필요한 디렉토리를 생성합니다.
        """
        self.base_url = {
            "prod": "https://openapi.koreainvestment.com:9443",
            "vps": "https://openapivts.koreainvestment.com:29443"
        }
        self.ws_url = {
            "prod": "ws://ops.koreainvestment.com:21000",
            "vps": "ws://ops.koreainvestment.com:31000"
        }
        
        # 설정 파일 경로
        self.config_path = Path("kis_devlp.yaml")
        
        # 토큰 저장 디렉토리 설정
        self.token_dir = Path("tokens")
        if not self.token_dir.exists():
            self.token_dir.mkdir(parents=True, exist_ok=True)
        
        # 설정 로드
        self.config = self._load_config()
        
        # 환경 설정
        self.env = "vps"  # 기본값은 모의투자
        self.product = "01"  # 기본값은 종합계좌
        
        # 토큰 정보
        self.access_token = None
        self.token_expired_at = None
    
    def _load_config(self) -> Dict[str, Any]:
        """
        설정 파일을 로드합니다.
        
        Returns:
            Dict[str, Any]: 설정 정보
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    def _get_token_path(self) -> Path:
        """
        토큰 파일 경로를 반환합니다.
        
        Returns:
            Path: 토큰 파일 경로
        """
        return self.token_dir / f"token_{self.env}.json"
    
    def _load_token(self) -> bool:
        """
        저장된 토큰을 로드합니다.
        
        Returns:
            bool: 토큰 로드 성공 여부
        """
        token_path = self._get_token_path()
        
        if not token_path.exists():
            return False
        
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            
            self.access_token = token_data.get("access_token")
            self.token_expired_at = token_data.get("expired_at")
            
            # 토큰 만료 확인
            if self.token_expired_at:
                now = datetime.datetime.now().timestamp()
                if now >= self.token_expired_at:
                    logger.info("토큰이 만료되었습니다. 새로운 토큰을 발급합니다.")
                    return False
            
            return bool(self.access_token)
        except Exception as e:
            logger.error(f"토큰 로드 실패: {e}")
            return False
    
    def _save_token(self, token_data: Dict[str, Any]) -> None:
        """
        토큰 정보를 파일에 저장합니다.
        
        Args:
            token_data (Dict[str, Any]): 저장할 토큰 데이터
        """
        token_path = self._get_token_path()
        
        try:
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump(token_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"토큰 저장 실패: {e}")
    
    def auth(self, svr: str = "vps", product: str = "01") -> bool:
        """
        한국투자증권 Open API 인증을 수행합니다.
        
        Args:
            svr (str, optional): 서버 환경 ("prod": 실전투자, "vps": 모의투자). 기본값은 "vps".
            product (str, optional): 상품 코드 ("01": 종합계좌, "03": 국내선물옵션, "08": 해외선물옵션, "22": 연금저축, "29": 퇴직연금). 기본값은 "01".
        
        Returns:
            bool: 인증 성공 여부
        """
        self.env = svr
        self.product = product
        
        # 저장된 토큰이 있으면 로드
        if self._load_token():
            logger.info("저장된 토큰을 로드했습니다.")
            return True
        
        # 앱키, 앱시크릿 설정
        if svr == "prod":
            app_key = self.config.get("my_app", "")
            app_secret = self.config.get("my_sec", "")
        else:
            app_key = self.config.get("paper_app", "")
            app_secret = self.config.get("paper_sec", "")
        
        if not app_key or not app_secret:
            logger.error("앱키 또는 앱시크릿이 설정되지 않았습니다.")
            return False
        
        # 토큰 발급 요청
        url = f"{self.base_url[svr]}/oauth2/tokenP"
        
        headers = {
            "content-type": "application/json"
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            token_data = response.json()
            
            if "access_token" in token_data:
                self.access_token = token_data["access_token"]
                
                # 만료 시간 계산 (1일 - 10분)
                now = datetime.datetime.now()
                expired_at = now + datetime.timedelta(days=1) - datetime.timedelta(minutes=10)
                self.token_expired_at = expired_at.timestamp()
                
                # 토큰 저장
                save_data = {
                    "access_token": self.access_token,
                    "expired_at": self.token_expired_at,
                    "issued_at": now.timestamp()
                }
                self._save_token(save_data)
                
                logger.info("토큰이 성공적으로 발급되었습니다.")
                return True
            else:
                logger.error(f"토큰 발급 실패: {token_data}")
                return False
        except Exception as e:
            logger.error(f"토큰 발급 요청 실패: {e}")
            return False
    
    def get_headers(self, is_content_type: bool = True, is_hash: bool = False, hash_data: str = "") -> Dict[str, str]:
        """
        API 요청에 필요한 헤더를 생성합니다.
        
        Args:
            is_content_type (bool, optional): Content-Type 헤더 포함 여부. 기본값은 True.
            is_hash (bool, optional): 해시 헤더 포함 여부. 기본값은 False.
            hash_data (str, optional): 해시 생성에 사용할 데이터. 기본값은 "".
        
        Returns:
            Dict[str, str]: 헤더 정보
        """
        if self.env == "prod":
            app_key = self.config.get("my_app", "")
            app_secret = self.config.get("my_sec", "")
        else:
            app_key = self.config.get("paper_app", "")
            app_secret = self.config.get("paper_sec", "")
        
        headers = {
            "authorization": f"Bearer {self.access_token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "",
            "custtype": "P"
        }
        
        if is_content_type:
            headers["content-type"] = "application/json"
        
        if is_hash and hash_data:
            # 해시 생성
            timestamp = str(int(time.time() * 1000))
            headers["hashkey"] = self._generate_hash(hash_data)
            headers["timestamp"] = timestamp
        
        return headers
    
    def _generate_hash(self, data: str) -> str:
        """
        해시키를 생성합니다.
        
        Args:
            data (str): 해시 생성에 사용할 데이터
        
        Returns:
            str: 생성된 해시키
        """
        if self.env == "prod":
            app_secret = self.config.get("my_sec", "")
        else:
            app_secret = self.config.get("paper_sec", "")
        
        timestamp = str(int(time.time() * 1000))
        
        # 데이터 준비
        message = data + timestamp + app_secret
        
        # SHA-256 해시 생성
        hash_obj = hashlib.sha256(message.encode())
        hash_bytes = hash_obj.digest()
        
        # Base64 인코딩
        hash_b64 = base64.b64encode(hash_bytes).decode('utf-8')
        
        return hash_b64
    
    def get_account(self) -> str:
        """
        현재 환경에 맞는 계좌번호를 반환합니다.
        
        Returns:
            str: 계좌번호
        """
        if self.env == "prod":
            account = self.config.get("my_acct_stock", "")
        else:
            account = self.config.get("my_paper_stock", "")
        
        return f"{account}{self.product}"
    
    def auth_ws(self) -> Tuple[str, str]:
        """
        WebSocket 연결에 필요한 인증 정보를 반환합니다.
        
        Returns:
            Tuple[str, str]: (앱키, 토큰)
        """
        if self.env == "prod":
            app_key = self.config.get("my_app", "")
        else:
            app_key = self.config.get("paper_app", "")
        
        return app_key, self.access_token
    
    def get_ws_url(self) -> str:
        """
        현재 환경에 맞는 WebSocket URL을 반환합니다.
        
        Returns:
            str: WebSocket URL
        """
        return self.ws_url[self.env]


# 싱글톤 인스턴스
kis_auth = KISAuth()