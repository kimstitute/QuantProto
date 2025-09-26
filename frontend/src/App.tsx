import {
  createChart,
  ColorType,
  LineSeries,
  type BusinessDay,
  type ISeriesApi,
} from "lightweight-charts";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
  change_rate: number;
  volume: number;
  trade_value: number;
};

type StockHistory = {
  symbol: string;
  name?: string;
  candles: Candle[];
};

type LineSeriesApi = ISeriesApi<"Line">;

const API_BASE = "http://localhost:8000";
const DEFAULT_DAYS = 30;

function toBusinessDay(input: string): BusinessDay {
  const [year, month, day] = input.split("-").map(Number);
  return { year, month, day } as BusinessDay;
}

function App() {
  const [symbolInput, setSymbolInput] = useState("005930");
  const [history, setHistory] = useState<Candle[]>([]);
  const [meta, setMeta] = useState<{ symbol: string; name?: string }>({
    symbol: "",
    name: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartSeriesRef = useRef<LineSeriesApi | null>(null);

  const latestCandle = useMemo(
    () => (history.length ? history[history.length - 1] : null),
    [history],
  );

  const previousCandle = useMemo(
    () => (history.length > 1 ? history[history.length - 2] : null),
    [history],
  );

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) {
      return;
    }

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#1f2933",
      },
      grid: {
        vertLines: { color: "#f0f3fa" },
        horzLines: { color: "#f0f3fa" },
      },
      rightPriceScale: { borderColor: "#dfe2e8" },
      timeScale: { borderColor: "#dfe2e8" },
      crosshair: { mode: 1 },
    });

    chartSeriesRef.current = chart.addSeries(LineSeries, {
      color: "#2962ff",
      lineWidth: 2,
    });

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      chart.applyOptions({ width: entry.contentRect.width });
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartSeriesRef.current = null;
    };
  }, []);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const resp = await fetch(
        `${API_BASE}/api/market/stock/history/${symbolInput}?days=${DEFAULT_DAYS}`,
      );
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const data: StockHistory = await resp.json();
      const candles = data.candles ?? [];

      setMeta({
        symbol: data.symbol ?? symbolInput,
        name: data.name ?? "",
      });
      setHistory(candles);

      if (chartSeriesRef.current) {
        const chartData = candles.map((candle) => ({
          time: toBusinessDay(candle.date),
          value: candle.close,
        }));
        chartSeriesRef.current.setData(chartData);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [symbolInput]);

  useEffect(() => {
    if (chartSeriesRef.current) {
      chartSeriesRef.current.setData([]);
    }

    fetchHistory();
    const interval = setInterval(fetchHistory, 30000);
    return () => clearInterval(interval);
  }, [fetchHistory]);

  const displayChange = useMemo(() => {
    if (!latestCandle) {
      return { change: 0, rate: 0 };
    }

    if (latestCandle.change !== undefined && latestCandle.change_rate !== undefined) {
      return {
        change: latestCandle.change,
        rate: latestCandle.change_rate,
      };
    }

    if (previousCandle) {
      const change = latestCandle.close - previousCandle.close;
      const rate = previousCandle.close
        ? (change / previousCandle.close) * 100
        : 0;
      return { change, rate };
    }

    return { change: 0, rate: 0 };
  }, [latestCandle, previousCandle]);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", maxWidth: 900 }}>
      <h1>HTS Prototype · Daily Chart</h1>

      <section style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem" }}>
          Symbol
          <input
            value={symbolInput}
            onChange={(event) => setSymbolInput(event.target.value.trim())}
            style={{
              display: "block",
              width: "100%",
              marginTop: "0.25rem",
              padding: "0.5rem 0.75rem",
              fontSize: "1rem",
            }}
          />
        </label>
        <button
          onClick={fetchHistory}
          disabled={loading || !symbolInput}
          style={{ padding: "0.5rem 1rem" }}
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
        {error && (
          <p style={{ color: "red", marginTop: "0.75rem" }}>Error: {error}</p>
        )}
      </section>

      <section style={{ marginBottom: "1.5rem" }}>
        <div ref={chartContainerRef} style={{ width: "100%", minHeight: 360 }} />
      </section>

      {latestCandle && (
        <section style={{ marginBottom: "2rem" }}>
          <h2>
            {meta.name ? `${meta.name} (${meta.symbol || symbolInput})` : meta.symbol || symbolInput}
          </h2>
          <p>Close: {latestCandle.close.toLocaleString()} KRW</p>
          <p>
            Change: {displayChange.change.toLocaleString(undefined, { maximumFractionDigits: 2 })} (
            {displayChange.rate.toFixed(2)}%)
          </p>
          <p>
            Open: {latestCandle.open.toLocaleString()} / High: {latestCandle.high.toLocaleString()} /
            Low: {latestCandle.low.toLocaleString()}
          </p>
          <p>Volume: {latestCandle.volume.toLocaleString()}</p>
          <p>Trade value: {latestCandle.trade_value.toLocaleString()}</p>
        </section>
      )}

      {history.length > 0 && (
        <section>
          <h3>Recent {Math.min(history.length, DEFAULT_DAYS)} sessions</h3>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.95rem",
              }}
            >
              <thead>
                <tr>
                  {[
                    "Date",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Change",
                    "Change %",
                    "Volume",
                    "Trade Value",
                  ].map((header) => (
                    <th
                      key={header}
                      style={{
                        textAlign: "right",
                        padding: "0.5rem",
                        borderBottom: "1px solid #e5e7eb",
                      }}
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...history]
                  .sort((a, b) => (a.date < b.date ? 1 : -1))
                  .map((candle) => (
                    <tr key={candle.date}>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>{candle.date}</td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.open.toLocaleString()}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.high.toLocaleString()}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.low.toLocaleString()}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.close.toLocaleString()}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.change.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.change_rate.toFixed(2)}%
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.volume.toLocaleString()}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right" }}>
                        {candle.trade_value.toLocaleString()}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

export default App;
