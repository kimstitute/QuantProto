# 02. Architecture

## 1. 전체 시스템 개요
```
┌────────────┐      REST/WebSocket      ┌─────────────┐
│  React SPA │  <-------------------->  │  FastAPI    │
│  (Vite)    │                         │  Backend    │
└─────┬──────┘                          └─────┬───────┘
      │     Chart/Data Requests               │
      │                                       │
      │                          ┌────────────▼──────────────┐
      │                          │  Services / Modules       │
      │                          │  - MarketDataService       │
      │                          │  - OrderSimulationService  │
      │                          │  - HistoricalDataService   │
      │                          │  - StrategyService (후속) │
      │                          └────────────┬──────────────┘
      │                                       │
      │    WebSocket Stream (Redis PubSub)    │ Task Queue
      │                                       │
┌─────▼──────┐                          ┌─────▼───────┐
│  Redis     │ <----------------------> │  Celery     │ (백그라운드 작업)
│  Cache/WS  │                          └─────┬───────┘
└────────────┘                                │
                                              │ ETL / Training Jobs
                                              │
                                     ┌────────▼────────┐
                                     │  PostgreSQL RDS │
                                     │  (ORM: SQLAlchemy)
                                     └─────────────────┘
```

## 2. 백엔드 구조 (FastAPI)
- `app/main.py`: FastAPI 인스턴스, 라우터 등록.
- `app/api/`: REST 및 WebSocket 라우터.
  - `market.py`: 시세/차트/종목 엔드포인트.
  - `orders.py`: 주문 시뮬레이션 API.
  - `strategies.py`: 전략/AI 관련(후속).
- `app/models/`: SQLAlchemy 모델 (종목, 계좌, 주문, 체결, 전략).
- `app/schemas/`: Pydantic 스키마.
- `app/services/`: 도메인 로직 (실시간 데이터, 히스토리컬 데이터, 주문 로직).
- `app/db/`: DB 세션, Alembic 마이그레이션 설정.
- `app/tasks/`: Celery 작업 정의 (데이터 수집, 학습/백테스트).
- `app/config.py`: 환경 변수/설정 로딩.

### 데이터 흐름 예시
1. **실시간 시세**: FastAPI가 `open-trading-api` 어댑터를 통해 WebSocket 연결 → Redis PubSub를 통해 SPA에 스트림.
2. **주문 시뮬레이션**: REST 요청 → OrderSimulationService → 주문 기록 DB 저장 → 결과 응답.
3. **히스토리컬 데이터**: FinanceDataReader 래퍼 → Celery 작업으로 주기적 수집 → RDS 저장 → API 조회.
4. **전략 학습**: Celery 작업으로 FinRL 실행 → 결과(RL 모델 파라미터, 성과 지표)를 RDS/S3에 저장 → REST API로 제공.

## 3. 프론트엔드 구조 (React)
- `src/App.tsx`: 라우팅/레이아웃.
- `src/pages/`:
  - `DashboardPage`: 시장 개요, 종목 리스트.
  - `SymbolPage`: 차트, 호가, 주문 패널.
  - `StrategyPage`: 전략 관리/결과(후속).
  - `SettingsPage`: API 키, 사용자 설정.
- `src/components/`:
  - `charts/PriceChart` (lightweight-charts 래퍼).
  - `market/OrderBook`, `market/TradeTape`.
  - `orders/OrderPanel`.
  - `account/PositionsTable`, `OrdersTable`.
- `src/state/`:
  - `useMarketStore` (Zustand) – 현재 선택 종목, UI 상태.
  - React Query를 통해 서버 데이터(fetcher, mutation) 관리.
- `src/services/`:
  - `apiClient.ts`: REST 호출 래퍼.
  - `wsClient.ts`: WebSocket 연결 관리.

## 4. 데이터 모델 초기안
- `symbols`: 종목 코드, 이름, 시장, 섹터 등 메타 정보.
- `quotes`: 시세 스냅샷, 업데이트 타임스탬프.
- `candles`: 히스토리컬 OHLCV (종목, 타임프레임, 시작/종료 시각, open/high/low/close/volume).
- `orders`: 주문 ID, 사용자, 종목, 수량, 가격, 상태.
- `trades`: 체결 기록(주문 연결, 체결가, 체결량, 체결 시간).
- `positions`: 계좌, 종목, 보유 수량, 평균 단가.
- `strategies` (후속): 전략 메타, 모델 경로, 성과.
- `jobs`: 백그라운드 작업 상태(타입, 파라미터, 진행도, 결과 경로).

## 5. 통신 및 인프라
- **REST API**: `/api/v1/market`, `/api/v1/orders`, `/api/v1/historical`, `/api/v1/strategies` 등 Prefix 구성.
- **WebSocket**: `/ws/quotes/{symbol}`, `/ws/orders` 등 채널.
- **인증**: 초기엔 비활성, 차후 JWT/세션 도입.
- **배포 고려**: Docker 기반 컨테이너화, AWS ECS 혹은 EC2 + Nginx Reverse Proxy.
- **CI/CD**: GitHub Actions(테스트, 린트, 빌드), Terraform/CDK로 인프라 관리(후속).

## 6. 모듈 연계 참고
- 실시간: `open-trading-api` 코드에서 요청/토큰 관리 참고 → `MarketDataService` 어댑터 구현.
- 히스토리컬: `FinanceDataReader` API → Celery task에서 호출, DB 저장.
- 강화학습: `FinRL` 파이프라인을 `StrategyService`에 단계적으로 이식.
- UI 레퍼런스: OpenBB(페이지 구조), StockSharp/NextTrade(호가/주문 UI), lightweight-charts 예제.

## 7. 향후 확장 포인트
- 사용자 인증/권한, 다중 계좌/전략 지원.
- 실거래 브로커 연동(추가 API 어댑터) 및 주문 라우팅.
- Timestream/Redshift 등 시계열/분석용 DB 분리.
- 이벤트 드리븐 아키텍처(Kinesis/Kafka) 도입 가능성 검토.
