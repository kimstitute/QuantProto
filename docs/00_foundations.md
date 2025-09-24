# 00. Project Foundations

## 1. 목표 및 범위
- FastAPI + React 기반 HTS 스타일 SPA 구현.
- Amazon RDS(PostgreSQL) 기반으로 계좌/전략/주문 데이터 영속화.
- 초기 단계에서는 HTS UI와 실시간 시세/주문 시뮬레이션에 집중하고, FinRL 기반 AI는 후속 단계에서 통합.

## 2. 환경 기준
- **클라우드**: AWS (EC2 + RDS + 선택적 ElastiCache/Batch 등).
- **데이터베이스**: Amazon RDS for PostgreSQL (Multi-AZ 여부 추후 결정).
- **애플리케이션 구성**:
  - Backend: FastAPI, SQLAlchemy, Alembic, WebSocket, Celery/Redis(추가 검토).
  - Frontend: React(Vite), TypeScript, React Query/Zustand, lightweight-charts.
  - CI/CD 및 IaC는 후속 단계에서 Terraform/CDK 또는 CloudFormation 검토.
- **개발 환경**:
  - Python 3.11+, Node 20+ 권장.
  - 패키지 관리: uv/poetry + npm(or pnpm) 선호.
  - 공통 스타일: black/ruff + eslint/prettier.

## 3. 참고 저장소 매핑
| 분류 | 저장소 | 활용 포인트 |
|------|---------|-------------|
| HTS UI 아이디어 | OpenBB, StockSharp, NextTrade, study-clone-toss-stock, htsCodeFrontend | 패널 레이아웃, 주문창 UX, 차트 배치 |
| 실시간 데이터 | koreainvestment/open-trading-api | 한국투자 Open API 호출/웹소켓 샘플 |
| 히스토리컬 데이터 | FinanceDataReader | 국내외 주가/지수 크롤링 코드 |
| 차트 컴포넌트 | tradingview/lightweight-charts | React 차트 구현 |
| 알고리즘/AI | FinRL, QuantAgent, TradingAgents, nautilus_trader, backtrader | 강화학습, 에이전트 구조, 백테스트 참고 |
| 운영 플로우 | openalgo, ChatGPT-Micro-Cap-Experiment | 브로커 어댑터, LLM 활용 예 |
| 기타 | actual | 로컬-퍼스트 SPA 구조 벤치마킹 |

## 4. 초기 산출물 계획
1. `docs/01_requirements.md`에 세부 기능 요구사항과 사용자 흐름 정의.
2. `docs/02_architecture.md`에 시스템 구성 다이어그램과 데이터 흐름 정리.
3. `backend/`, `frontend/` 디렉터리 초기화 및 환경 구성.
4. 레퍼런스 분석 시 중요 코드/패턴은 해당 문서에 인용.

## 5. 오픈 과제
- AWS 네트워크 구조(VPC/Subnet/보안그룹) 상세 설계 필요.
- 데이터베이스 스키마 초안(종목, 계좌, 주문, 체결 등) 작성 예정.
- 실시간 데이터 샌드박스 여부 및 API 키 관리 전략 확정 필요.
- AI 모듈 실행 인프라(Fargate, Batch, SageMaker 등) 후보 조사 예정.
