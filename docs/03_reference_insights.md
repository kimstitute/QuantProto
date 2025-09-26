# 03. Reference Insights (updated)

## 1. Overview
Added additional quantitative trading libraries to the references set. Highlights below capture useful patterns or components to reuse in our project.

## 2. Repository Highlights (new additions)
### 2.11 moonshot
- QuantRocket’s vectorized strategy framework focused on pipeline-style factor definitions; good reference for portfolio weighting workflows and result reporting.
- Strong configuration-driven approach (YAML strategy manifests) to replicate for user-defined strategies.

### 2.12 zipline
- Classic event-driven backtester (Quantopian). Offers powerful pipeline API, data ingestion architecture, and benchmark/adjustment handling; useful to study for designing our own backtest engine integration.
- Understands financial calendar management and asset metadata handling—valuable for HistoricalDataService design.

### 2.13 mplfinance
- Matplotlib extension for candlestick and volume charts; template for styling and figure export. Helps build report-generation functionality and alternative chart themes inside our SPA.

### 2.14 ccxt
- Comprehensive cryptocurrency exchange connector library (REST/WebSocket). Reference for building exchange-agnostic adapter interfaces, rate limiting, and error handling patterns.

### 2.15 dart-fss
- Korean DART filing scraper. Provides utilities for corporate disclosures/financial statements—useful for fundamentals enrichment in the HTS (e.g., displaying filings or financial metrics).

### 2.16 pykrx
- Korean Exchange (KRX) data loader. Includes API wrappers for listing, index, derivatives, and macro data; complements FinanceDataReader for domestic market coverage.

## 3. Action Items For Our Plan (additions)
- Expand HistoricalDataService scope to include KRX-specific endpoints via PyKrx and dart-fss for filings fundamentals.
- Document broker/exchange adapter interface requirements referencing CCXT and Moonshot/Zipline patterns (vectorized vs event-driven backtests).
- Plan chart/report export features referencing mplfinance styling templates.

## 4. Next Steps (updated)
- Review Moonshot’s configuration-driven strategy manifests for inspiration in FinRL/strategy management UI.
- Investigate Zipline calendar & asset pipeline for HistoricalDataService schema extensions.
- Evaluate CCXT integration steps for potential crypto market feeds.
