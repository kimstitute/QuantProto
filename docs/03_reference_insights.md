# 03. Reference Insights

## 1. Overview
Summary of reusable ideas extracted from the cloned references. Each bullet includes how it will influence our implementation plan.

## 2. Repository Highlights
### 2.1 open-trading-api
- `examples_llm/` groups REST and WebSocket calls per feature; we will mirror this structure in `app/services/market_data.py`.
- `kis_auth.py` encapsulates API key, token refresh, and environment switching; plan to add a similar helper inside `app/config.py`.
- WebSocket samples emit clean JSON payloads that can flow through Redis Pub/Sub; adopt the same schema for our real-time streams.

### 2.2 FinanceDataReader
- Single `DataReader` entry point supports multiple markets (KRX, NASDAQ, etc.); HistoricalDataService will expose a comparable multi-market interface.
- Listing helpers such as `StockListing` supply universe metadata; reuse for initial symbol/sector ingestion jobs.

### 2.3 FinRL
- Clear `train-test-trade` pipeline (see `finrl/applications`) inspires three Celery task types: `train`, `backtest`, `deploy`.
- Configuration split between Python modules and YAML; strategy definitions will allow JSON/YAML templates.

### 2.4 tradingview/lightweight-charts
- Official examples add candlestick/overlay/volume as separate series; React wrapper will manage series lifecycle via hooks.
- Axis customization APIs enable HTS-style layouts (indicator sub-panels, split views); collect required options for our chart component.

### 2.5 NextTrade
- MERN repo separates `client` (React) and `app` (API) while sharing types; supports our monorepo layout with clear backend/frontend boundaries.
- Strategy builder uses modular cards (conditions, portfolios, backtests); reuse the vertical panel + modal interaction pattern.

### 2.6 StockSharp
- Even though it is C#, the platform splits data ingestion, execution, analytics; mirror this by isolating Python modules for `data`, `execution`, `analysis`.
- Broker connectors follow a common interface; define a `BrokerAdapter` protocol for future multi-broker support.

### 2.7 openalgo
- ZeroMQ + WebSocket proxy normalises broker adapters behind uniform REST endpoints; reinforces the adapter abstraction mentioned above.
- Analyzer UI visualises API requests/responses; plan an internal admin/debug page for observing order flow.

### 2.8 actual
- Local-first sync (client cache + sync server) suggests adding optional offline cache (IndexedDB) for SPA resilience.
- Modular packages (`loot-core`, `desktop-client`) separate domain logic from UI; strategy logic can live in a dedicated Python package.

### 2.9 study-clone-toss-stock & htsCodeFrontend
- Storybook + Chromatic pipeline showcases HTS widgets; consider adopting Storybook for chart/order-book component snapshots.
- Ant Design tables/trees display hierarchical search results; apply similar UX to sector/industry navigation.

### 2.10 ChatGPT-Micro-Cap-Experiment, QuantAgent, TradingAgents
- LLM-driven experiments log prompts and results to CSV/Markdown; standardise FinRL output artifacts (metrics + narrative) in the same formats.
- TradingAgents demonstrates LangGraph-based multi-agent debates; keep this in mind for future strategy explanation modules.

## 3. Action Items for Our Plan
1. **Service Layering**: Use patterns from open-trading-api, StockSharp, openalgo to define FastAPI services and broker adapters explicitly.
2. **Data Layer**: Base HistoricalDataService scope on FinanceDataReader capabilities (initially Korea/US equities, indices, ETF).
3. **Frontend Layout**: Combine NextTrade, study-clone-toss-stock, htsCodeFrontend, lightweight-charts ideas to design the main HTS dashboard (chart + order-book + order panel).
4. **AI Pipeline**: Model Celery job flow (train -> backtest -> signal) after FinRL/QuantAgent/TradingAgents and agree on CSV/JSON/Markdown result formats.
5. **Operational Tooling**: Borrow openalgo's analyzer concept and actual's local-first approach to plan admin diagnostics and optional offline caching.

## 4. Next Steps
- Draft broker adapter protocol.
- Define first market/timeframe coverage for HistoricalDataService.
- Sketch React wireframes for dashboard, symbol view, order panel.
- Design Celery job schema (task types, payloads, outputs).
- List requirements for internal analyzer/admin page.
