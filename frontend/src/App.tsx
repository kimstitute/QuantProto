import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';

// Types
interface PortfolioSummary {
  ticker: string;
  shares: number;
  current_price: number | null;
  current_value: number | null;
  buy_price: number;
  cost_basis: number;
  pnl: number | null;
  pnl_percent: number | null;
  stop_loss: number | null;
}

interface TradingEngineStatus {
  is_running: boolean;
  check_interval: number;
  market_hours: {
    start: string;
    end: string;
  };
  cached_portfolio: any;
}

interface TradingSettings {
  llm_auto_trading: boolean;
  stop_loss_monitoring: boolean;
  max_daily_trades: number;
  max_position_size: number;
  trading_mode: string;
  daily_trade_count: number;
  daily_limit_reached: boolean;
}

interface DailyPerformance {
  id: number;
  date: string;
  total_equity: number;
  cash_balance: number;
  total_pnl: number;
  portfolio_value: number;
  created_at: string;
}

interface LLMAnalysisResult {
  success: boolean;
  message: string;
  llm_response: {
    analysis: string;
    confidence: number;
    reasoning: string;
    trade_count: number;
  };
  execution_result: {
    total_trades: number;
    successful_trades: number;
    failed_trades: number;
    execution_rate: number;
    execution_results: Array<{
      trade: {
        action: string;
        ticker: string;
        shares: number;
        price: number;
        stop_loss?: number;
        reason: string;
        confidence: number;
      };
      result: {
        success: boolean;
        message: string;
      };
    }>;
  };
  dry_run: boolean;
}

function App() {
  // State
  const [portfolio, setPortfolio] = useState<PortfolioSummary[]>([]);
  const [cashBalance, setCashBalance] = useState(0);
  const [totalEquity, setTotalEquity] = useState(0);
  const [engineStatus, setEngineStatus] = useState<TradingEngineStatus | null>(null);
  const [performanceData, setPerformanceData] = useState<DailyPerformance[]>([]);
  const [llmResult, setLlmResult] = useState<LLMAnalysisResult | null>(null);
  const [tradingSettings, setTradingSettings] = useState<TradingSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  // Manual trading form
  const [tradeForm, setTradeForm] = useState({
    action: 'buy',
    ticker: '',
    shares: '',
    price: '',
    stop_loss: ''
  });

  // LLM Analysis form
  const [llmForm, setLlmForm] = useState({
    custom_instructions: '',
    dry_run: true
  });

  // API 호출 함수들
  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/portfolio/summary`);
      if (response.ok) {
        const data = await response.json();
        setPortfolio(data);
      }
    } catch (err) {
      console.error('포트폴리오 조회 실패:', err);
    }
  }, []);

  const fetchCashBalance = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/portfolio/cash-balance`);
      if (response.ok) {
        const data = await response.json();
        setCashBalance(data.cash_balance);
      }
    } catch (err) {
      console.error('현금 잔고 조회 실패:', err);
    }
  }, []);

  const fetchEngineStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/trading/engine/status`);
      if (response.ok) {
        const data = await response.json();
        setEngineStatus(data);
      }
    } catch (err) {
      console.error('엔진 상태 조회 실패:', err);
    }
  }, []);

  const fetchTradingSettings = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/trading/settings`);
      if (response.ok) {
        const data = await response.json();
        setTradingSettings(data.settings);
      }
    } catch (err) {
      console.error('트레이딩 설정 조회 실패:', err);
    }
  }, []);

  const fetchPerformance = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/portfolio/performance/daily?limit=30`);
      if (response.ok) {
        const data = await response.json();
        setPerformanceData(data.reverse()); // 날짜 순으로 정렬
      }
    } catch (err) {
      console.error('성과 데이터 조회 실패:', err);
    }
  }, []);

  // 초기 데이터 로드 및 정기 업데이트
  useEffect(() => {
    const loadData = () => {
      fetchPortfolio();
      fetchCashBalance();
      fetchEngineStatus();
      fetchPerformance();
      fetchTradingSettings();
    };

    loadData();
    const interval = setInterval(loadData, 10000); // 10초마다 업데이트
    return () => clearInterval(interval);
  }, [fetchPortfolio, fetchCashBalance, fetchEngineStatus, fetchPerformance, fetchTradingSettings]);

  // 총 자산 계산
  useEffect(() => {
    const portfolioValue = portfolio.reduce((sum, pos) => sum + (pos.current_value || 0), 0);
    setTotalEquity(cashBalance + portfolioValue);
  }, [portfolio, cashBalance]);

  // 수동 거래 실행
  const handleManualTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const endpoint = tradeForm.action === 'buy' ? '/portfolio/buy' : '/portfolio/sell';
      const body = {
        ticker: tradeForm.ticker,
        shares: parseFloat(tradeForm.shares),
        price: parseFloat(tradeForm.price),
        ...(tradeForm.action === 'buy' && tradeForm.stop_loss && { stop_loss: parseFloat(tradeForm.stop_loss) })
      };

      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (response.ok) {
        const result = await response.json();
        alert(`거래 성공: ${result.message}`);
        setTradeForm({ action: 'buy', ticker: '', shares: '', price: '', stop_loss: '' });
        fetchPortfolio();
        fetchCashBalance();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || '거래 실행 실패');
      }
    } catch (err) {
      setError('거래 실행 중 오류 발생');
    } finally {
      setLoading(false);
    }
  };

  // LLM 분석 실행
  const handleLLMAnalysis = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/llm-trading/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(llmForm)
      });

      if (response.ok) {
        const result = await response.json();
        setLlmResult(result);
        if (!llmForm.dry_run) {
          fetchPortfolio();
          fetchCashBalance();
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'LLM 분석 실패');
      }
    } catch (err) {
      setError('LLM 분석 중 오류 발생');
    } finally {
      setLoading(false);
    }
  };

  // 엔진 제어
  const toggleEngine = async () => {
    try {
      const endpoint = engineStatus?.is_running ? '/trading/engine/stop' : '/trading/engine/start';
      const response = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      
      if (response.ok) {
        setTimeout(fetchEngineStatus, 1000); // 1초 후 상태 업데이트
      }
    } catch (err) {
      console.error('엔진 제어 실패:', err);
    }
  };

  // 긴급 중지
  const emergencyStop = async () => {
    if (confirm('🚨 모든 자동매매를 긴급 중지하시겠습니까?')) {
      try {
        const response = await fetch(`${API_BASE}/trading/emergency-stop`, { method: 'POST' });
        if (response.ok) {
          alert('모든 자동매매가 중지되었습니다.');
          fetchTradingSettings();
          fetchEngineStatus();
        }
      } catch (err) {
        console.error('긴급 중지 실패:', err);
      }
    }
  };

  // 트레이딩 모드 변경
  const changeTradingMode = async (newMode: string) => {
    const modeText = newMode === 'prod' ? '실전투자' : '모의투자';
    if (confirm(`${modeText} 모드로 변경하시겠습니까?`)) {
      try {
        const response = await fetch(`${API_BASE}/trading/mode`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newMode)
        });
        
        if (response.ok) {
          const result = await response.json();
          alert(result.message);
          fetchTradingSettings();
        }
      } catch (err) {
        console.error('모드 변경 실패:', err);
      }
    }
  };

  // 자동매매 토글
  const toggleAutoTrading = async () => {
    if (!tradingSettings) return;
    
    try {
      const newSettings = {
        ...tradingSettings,
        llm_auto_trading: !tradingSettings.llm_auto_trading
      };
      
      const response = await fetch(`${API_BASE}/trading/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings)
      });
      
      if (response.ok) {
        fetchTradingSettings();
      }
    } catch (err) {
      console.error('자동매매 설정 변경 실패:', err);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#f8fafc', 
      padding: '16px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* 헤더 */}
        <header style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          padding: '24px',
          marginBottom: '24px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1 style={{ fontSize: '2rem', fontWeight: 'bold', margin: '0 0 8px 0', color: '#1a202c' }}>
                QuantProto Dashboard
              </h1>
              <p style={{ color: '#718096', margin: 0 }}>LLM 기반 자동 트레이딩 시스템</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              {/* 트레이딩 모드 표시 */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '16px',
                backgroundColor: tradingSettings?.trading_mode === 'prod' ? '#fee2e2' : '#f0f9ff',
                color: tradingSettings?.trading_mode === 'prod' ? '#b91c1c' : '#1e40af',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                <span>{tradingSettings?.trading_mode === 'prod' ? '⚠️' : '🎮'}</span>
                <span>{tradingSettings?.trading_mode === 'prod' ? '실전투자' : '모의투자'}</span>
              </div>

              {/* 자동매매 상태 */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '16px',
                backgroundColor: tradingSettings?.llm_auto_trading ? '#f0fff4' : '#fef5e7',
                color: tradingSettings?.llm_auto_trading ? '#22543d' : '#744210',
                fontSize: '12px',
                fontWeight: '500'
              }}>
                <span>{tradingSettings?.llm_auto_trading ? '🤖' : '⏹️'}</span>
                <span>{tradingSettings?.llm_auto_trading ? 'LLM 자동매매' : 'LLM 중지됨'}</span>
              </div>

              {/* 엔진 상태 */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '16px',
                backgroundColor: engineStatus?.is_running ? '#f0fff4' : '#fef5e7',
                color: engineStatus?.is_running ? '#22543d' : '#744210',
                fontSize: '12px',
                fontWeight: '500'
              }}>
                <span style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: engineStatus?.is_running ? '#38a169' : '#ed8936'
                }} />
                <span>{engineStatus?.is_running ? '엔진 실행 중' : '엔진 중지됨'}</span>
              </div>

              {/* 거래 한도 표시 */}
              {tradingSettings && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 12px',
                  borderRadius: '16px',
                  backgroundColor: tradingSettings.daily_limit_reached ? '#fee2e2' : '#f8fafc',
                  color: tradingSettings.daily_limit_reached ? '#b91c1c' : '#4b5563',
                  fontSize: '12px',
                  fontWeight: '500'
                }}>
                  <span>📊</span>
                  <span>{tradingSettings.daily_trade_count}/{tradingSettings.max_daily_trades} 거래</span>
                </div>
              )}

              {/* 제어 버튼들 */}
              <button
                onClick={toggleAutoTrading}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: tradingSettings?.llm_auto_trading ? '#fbbf24' : '#10b981',
                  color: 'white',
                  fontSize: '12px',
                  fontWeight: '500',
                  cursor: 'pointer'
                }}
              >
                {tradingSettings?.llm_auto_trading ? '🤖 자동매매 OFF' : '🤖 자동매매 ON'}
              </button>

              <button
                onClick={() => changeTradingMode(tradingSettings?.trading_mode === 'prod' ? 'vps' : 'prod')}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid #d1d5db',
                  backgroundColor: 'white',
                  color: '#374151',
                  fontSize: '12px',
                  fontWeight: '500',
                  cursor: 'pointer'
                }}
              >
                {tradingSettings?.trading_mode === 'prod' ? '🎮 모의투자로' : '⚠️ 실전투자로'}
              </button>

              <button
                onClick={toggleEngine}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontWeight: '500',
                  cursor: 'pointer',
                  fontSize: '12px',
                  backgroundColor: engineStatus?.is_running ? '#e53e3e' : '#38a169',
                  color: 'white'
                }}
              >
                <span>{engineStatus?.is_running ? '⏸' : '▶'}</span>
                <span>{engineStatus?.is_running ? '중지' : '시작'}</span>
              </button>

              <button
                onClick={emergencyStop}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontWeight: '500',
                  cursor: 'pointer',
                  fontSize: '12px',
                  backgroundColor: '#dc2626',
                  color: 'white'
                }}
              >
                🚨 긴급중지
              </button>
            </div>
          </div>
        </header>

        {/* 자산 현황 카드 */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
          gap: '24px',
          marginBottom: '24px'
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                padding: '8px',
                backgroundColor: '#ebf8ff',
                borderRadius: '8px',
                marginRight: '16px'
              }}>
                <span style={{ color: '#2b6cb0', fontSize: '24px' }}>💰</span>
              </div>
              <div>
                <p style={{ margin: '0 0 4px 0', fontSize: '14px', color: '#718096', fontWeight: '500' }}>
                  총 자산
                </p>
                <p style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#1a202c' }}>
                  ₩{totalEquity.toLocaleString()}
                </p>
              </div>
            </div>
          </div>

          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                padding: '8px',
                backgroundColor: '#f0fff4',
                borderRadius: '8px',
                marginRight: '16px'
              }}>
                <span style={{ color: '#22543d', fontSize: '24px' }}>📊</span>
              </div>
              <div>
                <p style={{ margin: '0 0 4px 0', fontSize: '14px', color: '#718096', fontWeight: '500' }}>
                  포트폴리오 가치
                </p>
                <p style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#1a202c' }}>
                  ₩{portfolio.reduce((sum, pos) => sum + (pos.current_value || 0), 0).toLocaleString()}
                </p>
              </div>
            </div>
          </div>

          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                padding: '8px',
                backgroundColor: '#fffbf0',
                borderRadius: '8px',
                marginRight: '16px'
              }}>
                <span style={{ color: '#744210', fontSize: '24px' }}>💵</span>
              </div>
              <div>
                <p style={{ margin: '0 0 4px 0', fontSize: '14px', color: '#718096', fontWeight: '500' }}>
                  현금 잔고
                </p>
                <p style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#1a202c' }}>
                  ₩{cashBalance.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '24px' }}>
          
          {/* 포트폴리오 테이블 */}
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <div style={{
              padding: '24px 24px 16px 24px',
              borderBottom: '1px solid #e2e8f0'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600', color: '#1a202c' }}>보유 종목</h2>
                <span style={{
                  fontSize: '12px',
                  color: '#6b7280',
                  backgroundColor: '#f3f4f6',
                  padding: '4px 8px',
                  borderRadius: '12px'
                }}>
                  {portfolio.length}개 보유
                </span>
              </div>
            </div>
            <div style={{ padding: '24px' }}>
              {portfolio.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f7fafc' }}>
                        <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: '500', color: '#718096', textTransform: 'uppercase' }}>종목</th>
                        <th style={{ padding: '12px 8px', textAlign: 'right', fontSize: '12px', fontWeight: '500', color: '#718096', textTransform: 'uppercase' }}>수량</th>
                        <th style={{ padding: '12px 8px', textAlign: 'right', fontSize: '12px', fontWeight: '500', color: '#718096', textTransform: 'uppercase' }}>현재가</th>
                        <th style={{ padding: '12px 8px', textAlign: 'right', fontSize: '12px', fontWeight: '500', color: '#718096', textTransform: 'uppercase' }}>손익</th>
                        <th style={{ padding: '12px 8px', textAlign: 'right', fontSize: '12px', fontWeight: '500', color: '#718096', textTransform: 'uppercase' }}>수익률</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.map((position, index) => (
                        <tr key={position.ticker} style={{
                          borderTop: index > 0 ? '1px solid #e2e8f0' : 'none',
                          backgroundColor: index % 2 === 0 ? '#ffffff' : '#f9fafb'
                        }}>
                          <td style={{ padding: '12px 8px' }}>
                            <div>
                              <div style={{ fontSize: '14px', fontWeight: '600', color: '#1a202c' }}>
                                {position.ticker}
                              </div>
                              {position.stop_loss && (
                                <div style={{ fontSize: '11px', color: '#dc2626', marginTop: '2px' }}>
                                  🛡️ 손절: ₩{position.stop_loss.toLocaleString()}
                                </div>
                              )}
                            </div>
                          </td>
                          <td style={{ padding: '12px 8px', fontSize: '14px', color: '#1a202c', textAlign: 'right' }}>
                            {position.shares.toLocaleString()}주
                          </td>
                          <td style={{ padding: '12px 8px', textAlign: 'right' }}>
                            <div>
                              <div style={{ fontSize: '14px', fontWeight: '500', color: '#1a202c' }}>
                                ₩{position.current_price?.toLocaleString() || 'N/A'}
                              </div>
                              <div style={{ fontSize: '11px', color: '#6b7280' }}>
                                평균: ₩{position.buy_price.toLocaleString()}
                              </div>
                            </div>
                          </td>
                          <td style={{
                            padding: '12px 8px',
                            textAlign: 'right'
                          }}>
                            {position.pnl !== null ? (
                              <div>
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'flex-end',
                                  fontSize: '14px',
                                  fontWeight: '600',
                                  color: position.pnl >= 0 ? '#059669' : '#dc2626'
                                }}>
                                  <span>{position.pnl >= 0 ? '📈' : '📉'}</span>
                                  <span style={{ marginLeft: '4px' }}>₩{position.pnl.toLocaleString()}</span>
                                </div>
                                <div style={{ fontSize: '11px', color: '#6b7280', textAlign: 'right' }}>
                                  평가액: ₩{position.current_value?.toLocaleString()}
                                </div>
                              </div>
                            ) : (
                              <span style={{ color: '#9ca3af' }}>N/A</span>
                            )}
                          </td>
                          <td style={{
                            padding: '12px 8px',
                            textAlign: 'right'
                          }}>
                            {position.pnl_percent !== null ? (
                              <span style={{
                                fontSize: '14px',
                                fontWeight: '600',
                                color: position.pnl_percent >= 0 ? '#059669' : '#dc2626',
                                padding: '4px 8px',
                                backgroundColor: position.pnl_percent >= 0 ? '#ecfdf5' : '#fef2f2',
                                borderRadius: '4px'
                              }}>
                                {position.pnl_percent >= 0 ? '+' : ''}{position.pnl_percent.toFixed(2)}%
                              </span>
                            ) : (
                              <span style={{ color: '#9ca3af' }}>N/A</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: '#718096', textAlign: 'center', padding: '32px 0' }}>보유 종목이 없습니다</p>
              )}
            </div>
          </div>

          {/* 성과 요약 */}
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <div style={{
              padding: '24px 24px 16px 24px',
              borderBottom: '1px solid #e2e8f0'
            }}>
              <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600', color: '#1a202c' }}>최근 성과</h2>
            </div>
            <div style={{ padding: '24px' }}>
              {performanceData.length > 0 ? (
                <div>
                  {performanceData.slice(-5).map((perf, index) => (
                    <div key={perf.id} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '8px 0',
                      borderBottom: index < 4 ? '1px solid #f1f5f9' : 'none'
                    }}>
                      <span style={{ fontSize: '14px', color: '#718096' }}>{perf.date}</span>
                      <span style={{ fontSize: '14px', fontWeight: '500', color: '#1a202c' }}>
                        ₩{perf.total_equity.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: '#718096', textAlign: 'center', padding: '32px 0' }}>성과 데이터가 없습니다</p>
              )}
            </div>
          </div>
        </div>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', 
          gap: '24px',
          marginTop: '24px'
        }}>
          
          {/* 수동 거래 */}
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <div style={{
              padding: '24px 24px 16px 24px',
              borderBottom: '1px solid #e2e8f0'
            }}>
              <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600', color: '#1a202c' }}>수동 거래</h2>
            </div>
            <div style={{ padding: '24px' }}>
              <form onSubmit={handleManualTrade} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', gap: '16px' }}>
                  <label style={{ display: 'flex', alignItems: 'center' }}>
                    <input
                      type="radio"
                      value="buy"
                      checked={tradeForm.action === 'buy'}
                      onChange={(e) => setTradeForm(prev => ({ ...prev, action: e.target.value }))}
                      style={{ marginRight: '8px' }}
                    />
                    매수
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center' }}>
                    <input
                      type="radio"
                      value="sell"
                      checked={tradeForm.action === 'sell'}
                      onChange={(e) => setTradeForm(prev => ({ ...prev, action: e.target.value }))}
                      style={{ marginRight: '8px' }}
                    />
                    매도
                  </label>
                </div>
                
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
                    종목코드
                  </label>
                  <input
                    type="text"
                    value={tradeForm.ticker}
                    onChange={(e) => setTradeForm(prev => ({ ...prev, ticker: e.target.value }))}
                    style={{
                      width: '100%',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      fontSize: '14px',
                      boxSizing: 'border-box'
                    }}
                    placeholder="005930"
                    required
                  />
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
                      수량
                    </label>
                    <input
                      type="number"
                      value={tradeForm.shares}
                      onChange={(e) => setTradeForm(prev => ({ ...prev, shares: e.target.value }))}
                      style={{
                        width: '100%',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '14px',
                        boxSizing: 'border-box'
                      }}
                      required
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
                      가격
                    </label>
                    <input
                      type="number"
                      value={tradeForm.price}
                      onChange={(e) => setTradeForm(prev => ({ ...prev, price: e.target.value }))}
                      style={{
                        width: '100%',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '14px',
                        boxSizing: 'border-box'
                      }}
                      required
                    />
                  </div>
                </div>
                
                {tradeForm.action === 'buy' && (
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
                      스톱로스 (선택)
                    </label>
                    <input
                      type="number"
                      value={tradeForm.stop_loss}
                      onChange={(e) => setTradeForm(prev => ({ ...prev, stop_loss: e.target.value }))}
                      style={{
                        width: '100%',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '14px',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                )}
                
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    width: '100%',
                    backgroundColor: loading ? '#9ca3af' : '#3b82f6',
                    color: 'white',
                    fontWeight: '500',
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: 'none',
                    cursor: loading ? 'not-allowed' : 'pointer'
                  }}
                >
                  {loading ? '처리 중...' : '거래 실행'}
                </button>
              </form>
            </div>
          </div>

          {/* LLM 분석 */}
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <div style={{
              padding: '24px 24px 16px 24px',
              borderBottom: '1px solid #e2e8f0'
            }}>
              <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600', color: '#1a202c' }}>LLM 자동 분석</h2>
            </div>
            <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
                  추가 지시사항
                </label>
                <textarea
                  value={llmForm.custom_instructions}
                  onChange={(e) => setLlmForm(prev => ({ ...prev, custom_instructions: e.target.value }))}
                  style={{
                    width: '100%',
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    fontSize: '14px',
                    height: '80px',
                    resize: 'vertical' as const,
                    boxSizing: 'border-box'
                  }}
                  placeholder="LLM에게 전달할 추가 지시사항을 입력하세요..."
                />
              </div>
              
              <label style={{ display: 'flex', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={llmForm.dry_run}
                  onChange={(e) => setLlmForm(prev => ({ ...prev, dry_run: e.target.checked }))}
                  style={{ marginRight: '8px' }}
                />
                Dry Run (실제 거래 없이 시뮬레이션만)
              </label>
              
              <button
                onClick={handleLLMAnalysis}
                disabled={loading}
                style={{
                  width: '100%',
                  backgroundColor: loading ? '#9ca3af' : '#8b5cf6',
                  color: 'white',
                  fontWeight: '500',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                <span>{loading ? '🔄' : '⚙️'}</span>
                <span>{loading ? '분석 중...' : 'LLM 분석 시작'}</span>
              </button>
              
              {llmResult && (
                <div style={{
                  marginTop: '16px',
                  padding: '0',
                  backgroundColor: 'transparent'
                }}>
                  {/* LLM 분석 요약 */}
                  <div style={{
                    padding: '16px',
                    backgroundColor: '#f8fafc',
                    borderRadius: '6px',
                    marginBottom: '16px'
                  }}>
                    <h3 style={{ fontWeight: '600', marginBottom: '12px', fontSize: '16px', color: '#1a202c' }}>
                      🤖 LLM 분석 결과
                    </h3>
                    <p style={{ fontSize: '14px', color: '#4b5563', lineHeight: 1.5, marginBottom: '12px' }}>
                      {llmResult.llm_response.analysis}
                    </p>
                    {llmResult.llm_response.reasoning && (
                      <p style={{
                        fontSize: '13px',
                        color: '#6b7280',
                        fontStyle: 'italic',
                        backgroundColor: '#f1f5f9',
                        padding: '8px',
                        borderRadius: '4px',
                        marginBottom: '12px'
                      }}>
                        💡 {llmResult.llm_response.reasoning}
                      </p>
                    )}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '12px',
                      color: '#6b7280',
                      padding: '8px 0',
                      borderTop: '1px solid #e5e7eb'
                    }}>
                      <span>신뢰도: {(llmResult.llm_response.confidence * 100).toFixed(1)}%</span>
                      <span>실행률: {llmResult.execution_result.execution_rate.toFixed(1)}%</span>
                      <span>{llmResult.dry_run ? '🎮 시뮬레이션' : '⚡ 실제 실행'}</span>
                    </div>
                  </div>

                  {/* 추천 거래 상세 목록 */}
                  {llmResult.execution_result.execution_results && llmResult.execution_result.execution_results.length > 0 && (
                    <div style={{
                      backgroundColor: 'white',
                      borderRadius: '6px',
                      border: '1px solid #e5e7eb'
                    }}>
                      <div style={{
                        padding: '12px 16px',
                        borderBottom: '1px solid #e5e7eb',
                        backgroundColor: '#f9fafb'
                      }}>
                        <h4 style={{
                          margin: 0,
                          fontSize: '14px',
                          fontWeight: '600',
                          color: '#374151'
                        }}>
                          🎯 추천 거래 상세 ({llmResult.llm_response.trade_count}건)
                        </h4>
                      </div>
                      <div style={{ padding: '12px' }}>
                        {llmResult.execution_result.execution_results.map((item: any, index: number) => (
                          <div key={index} style={{
                            padding: '12px',
                            backgroundColor: '#f8fafc',
                            borderRadius: '6px',
                            marginBottom: index < llmResult.execution_result.execution_results.length - 1 ? '8px' : '0',
                            border: '1px solid #e5e7eb'
                          }}>
                            {/* 거래 정보 헤더 */}
                            <div style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              marginBottom: '8px'
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{
                                  fontWeight: '700',
                                  color: item.trade.action === 'buy' ? '#059669' : '#dc2626',
                                  fontSize: '14px'
                                }}>
                                  {item.trade.action === 'buy' ? '📈 매수' : '📉 매도'}
                                </span>
                                <span style={{
                                  fontSize: '16px',
                                  fontWeight: '600',
                                  color: '#1a202c'
                                }}>
                                  {item.trade.ticker}
                                </span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{
                                  fontSize: '11px',
                                  padding: '3px 8px',
                                  borderRadius: '12px',
                                  backgroundColor: item.result.success ? '#dcfce7' : '#fee2e2',
                                  color: item.result.success ? '#166534' : '#dc2626',
                                  fontWeight: '600'
                                }}>
                                  {item.result.success ? '✅ 성공' : '❌ 실패'}
                                </span>
                                <span style={{
                                  fontSize: '11px',
                                  padding: '3px 8px',
                                  borderRadius: '12px',
                                  backgroundColor: '#fef3c7',
                                  color: '#92400e',
                                  fontWeight: '500'
                                }}>
                                  신뢰도 {(item.trade.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>

                            {/* 거래 상세 정보 */}
                            <div style={{
                              display: 'grid',
                              gridTemplateColumns: '1fr 1fr 1fr',
                              gap: '12px',
                              marginBottom: '8px'
                            }}>
                              <div>
                                <span style={{ fontSize: '11px', color: '#6b7280', display: 'block' }}>수량</span>
                                <span style={{ fontSize: '14px', fontWeight: '600', color: '#1a202c' }}>
                                  {item.trade.shares.toLocaleString()}주
                                </span>
                              </div>
                              <div>
                                <span style={{ fontSize: '11px', color: '#6b7280', display: 'block' }}>가격</span>
                                <span style={{ fontSize: '14px', fontWeight: '600', color: '#1a202c' }}>
                                  ₩{item.trade.price?.toLocaleString()}
                                </span>
                              </div>
                              {item.trade.stop_loss && (
                                <div>
                                  <span style={{ fontSize: '11px', color: '#6b7280', display: 'block' }}>손절가</span>
                                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#dc2626' }}>
                                    ₩{item.trade.stop_loss.toLocaleString()}
                                  </span>
                                </div>
                              )}
                            </div>

                            {/* 투자 근거 */}
                            <div style={{
                              padding: '8px 12px',
                              backgroundColor: 'white',
                              borderRadius: '4px',
                              border: '1px solid #e5e7eb'
                            }}>
                              <span style={{ fontSize: '11px', color: '#6b7280', fontWeight: '500' }}>💭 투자 근거:</span>
                              <p style={{
                                fontSize: '13px',
                                color: '#374151',
                                margin: '4px 0 0 0',
                                lineHeight: 1.4
                              }}>
                                {item.trade.reason}
                              </p>
                            </div>

                            {/* 실행 결과 메시지 */}
                            {!item.result.success && (
                              <div style={{
                                marginTop: '8px',
                                padding: '6px 8px',
                                backgroundColor: '#fef2f2',
                                borderRadius: '4px',
                                fontSize: '12px',
                                color: '#b91c1c'
                              }}>
                                ⚠️ {item.result.message}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {error && (
          <div style={{
            backgroundColor: '#fee2e2',
            border: '1px solid #fecaca',
            color: '#b91c1c',
            padding: '12px 16px',
            borderRadius: '6px',
            marginTop: '24px'
          }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
