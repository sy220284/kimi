"""
api/main.py — A股量化分析 REST API v2.0

端点：
  GET  /                       健康检查
  GET  /health                 服务状态
  POST /api/v1/regime          市场状态识别
  POST /api/v1/factors         多因子评分
  POST /api/v1/analyze         单股完整分析
  POST /api/v1/scan            批量扫描选股
  POST /api/v1/backtest        单股回测
  POST /api/v1/backtest/batch  批量回测
"""
import os, time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from agents.ashare_agent import AShareAgent
from analysis.regime.market_regime import AShareMarketRegime
from analysis.factors.multi_factor import AShareMultiFactor
from analysis.strategy.ashare_strategy import AShareStrategy
from analysis.strategy.ashare_backtester import AShareBacktester
from analysis.strategy.ashare_batch import AShareBatchBacktester
from utils.config_loader import load_config
from utils.logger import get_logger

logger = get_logger(__name__)
config = load_config()

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_rate_limit: dict[str, list[float]] = defaultdict(list)


def _get_valid_keys() -> set[str]:
    raw = os.environ.get("API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    if not keys:
        logger.warning("API_KEYS 未配置，开发模式")
    return keys


async def require_auth(request: Request, api_key: str | None = Depends(_API_KEY_HEADER)):
    valid_keys = _get_valid_keys()
    if valid_keys and api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="无效 API Key")
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < 60]
    if len(_rate_limit[ip]) >= 60:
        raise HTTPException(status_code=429, detail="请求过于频繁")
    _rate_limit[ip].append(now)


_dm = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dm
    try:
        from data.optimized_data_manager import get_optimized_data_manager
        _dm = get_optimized_data_manager()
        _dm.load_all_data()
        logger.info(f"数据加载完成: {_dm.get_stats()}")
    except Exception as e:
        logger.warning(f"数据预加载失败: {e}")
    yield


def get_dm():
    global _dm
    if _dm is None:
        from data.optimized_data_manager import get_optimized_data_manager
        _dm = get_optimized_data_manager()
        _dm.load_all_data()
    return _dm


def get_df(symbol: str):
    df = get_dm().get_stock_data(symbol)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 无数据")
    return df


app = FastAPI(
    title="A股量化分析 API",
    description="四层架构：市场状态 + 多因子选股 + A股适配策略",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class OHLCVRow(BaseModel):
    date: str; open: float; high: float; low: float; close: float; volume: float

class SymbolRequest(BaseModel):
    symbol: str
    rows: list[OHLCVRow] | None = None

class RegimeRequest(BaseModel):
    symbol: str | None = None
    rows: list[OHLCVRow] | None = None

class ScanRequest(BaseModel):
    symbols: list[str]
    top_n: int = Field(10, ge=1, le=50)
    min_grade: str = "B"

class BacktestRequest(BaseModel):
    symbol: str
    initial_capital: float = 100_000
    max_stop_pct: float = 0.09

class BatchBacktestRequest(BaseModel):
    symbols: list[str]
    initial_capital: float = 100_000
    max_workers: int = Field(4, ge=1, le=8)

class HealthResponse(BaseModel):
    status: str; version: str; timestamp: str; data_loaded: bool

class RegimeResponse(BaseModel):
    regime: str; label: str; confidence: float
    max_position: float; max_positions: int
    description: str; scores: dict[str, float]

class FactorResponse(BaseModel):
    symbol: str; total_score: float; grade: str
    passed_filter: bool; filter_reason: str
    details: dict[str, float]

class SignalInfo(BaseModel):
    signal_type: str; entry_price: float; stop_loss: float
    target_price: float; rr_ratio: float; confidence: float; position_pct: float

class AnalyzeResponse(BaseModel):
    symbol: str; date: str; price: float
    action: str; reason: str; confidence: float
    regime: RegimeResponse; factor: FactorResponse; signal: SignalInfo | None

class BacktestResponse(BaseModel):
    symbol: str; total_trades: int; win_rate: float
    total_return_pct: float; max_drawdown_pct: float
    sharpe_ratio: float; calmar_ratio: float; profit_factor: float
    target_reached_pct: float; hard_stop_pct: float
    signal_type_counts: dict[str, int]; exit_reason_counts: dict[str, int]

class BatchSummaryResponse(BaseModel):
    symbols_total: int; symbols_ok: int
    avg_win_rate: float; avg_return_pct: float
    avg_drawdown_pct: float; avg_sharpe: float
    avg_target_reached_pct: float; avg_hard_stop_pct: float
    best_symbol: str; best_return: float
    worst_symbol: str; worst_return: float
    profitable_pct: float; total_trades: int; elapsed_sec: float


def _rows_to_df(rows):
    import pandas as pd
    return pd.DataFrame([r.model_dump() for r in rows])

def _regime_to_resp(r) -> RegimeResponse:
    return RegimeResponse(
        regime=r.regime.value, label=r.label, confidence=r.confidence,
        max_position=r.max_position, max_positions=r.max_positions,
        description=r.description,
        scores={"trend": r.trend_score, "volume": r.volume_score,
                "momentum": r.momentum_score, "breadth": r.breadth_score, "risk": r.risk_score})

def _factor_to_resp(f) -> FactorResponse:
    return FactorResponse(
        symbol=f.symbol, total_score=f.total_score, grade=f.grade,
        passed_filter=f.passed_filter, filter_reason=f.filter_reason,
        details={"momentum": f.momentum_score, "turnover": f.turnover_score,
                 "trend": f.trend_score, "rsi": f.rsi_score,
                 "vol_price": f.vol_price_score, "cost": f.cost_score})

def _sig_to_resp(r) -> AnalyzeResponse:
    sig_resp = None
    if r.signal and r.signal.is_valid:
        s = r.signal
        sig_resp = SignalInfo(signal_type=s.signal_type.value, entry_price=s.entry_price,
            stop_loss=s.stop_loss, target_price=s.target_price, rr_ratio=s.rr_ratio,
            confidence=s.confidence, position_pct=s.position_pct)
    return AnalyzeResponse(
        symbol=r.symbol, date=r.date, price=r.price,
        action=r.action, reason=r.reason, confidence=r.confidence,
        regime=_regime_to_resp(r.regime), factor=_factor_to_resp(r.factor_score), signal=sig_resp)


@app.get("/", response_model=HealthResponse, tags=["系统"])
async def root():
    return HealthResponse(status="ok", version="2.0.0",
        timestamp=datetime.now().isoformat(), data_loaded=_dm is not None)

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health():
    return HealthResponse(status="ok", version="2.0.0",
        timestamp=datetime.now().isoformat(), data_loaded=_dm is not None)

@app.post("/api/v1/regime", response_model=RegimeResponse,
          dependencies=[Depends(require_auth)], tags=["分析"], summary="市场状态识别")
async def regime_endpoint(req: RegimeRequest):
    df = _rows_to_df(req.rows) if req.rows else (get_df(req.symbol) if req.symbol else None)
    if df is None:
        raise HTTPException(status_code=400, detail="需提供 symbol 或 rows")
    return _regime_to_resp(AShareMarketRegime().detect(df))

@app.post("/api/v1/factors", response_model=FactorResponse,
          dependencies=[Depends(require_auth)], tags=["分析"], summary="多因子评分")
async def factors_endpoint(req: SymbolRequest):
    df = _rows_to_df(req.rows) if req.rows else get_df(req.symbol)
    return _factor_to_resp(AShareMultiFactor().score(req.symbol, df))

@app.post("/api/v1/analyze", response_model=AnalyzeResponse,
          dependencies=[Depends(require_auth)], tags=["分析"], summary="单股完整分析")
async def analyze_endpoint(req: SymbolRequest):
    df = _rows_to_df(req.rows) if req.rows else get_df(req.symbol)
    return _sig_to_resp(AShareAgent().analyze(req.symbol, df))

@app.post("/api/v1/scan", response_model=list[AnalyzeResponse],
          dependencies=[Depends(require_auth)], tags=["选股"], summary="批量扫描选股")
async def scan_endpoint(req: ScanRequest):
    dm = get_dm()
    sdfs = {s: df for s in req.symbols if (df := dm.get_stock_data(s)) is not None and not df.empty}
    return [_sig_to_resp(r) for r in AShareAgent().scan(sdfs, top_n=req.top_n, min_grade=req.min_grade)]

@app.post("/api/v1/backtest", response_model=BacktestResponse,
          dependencies=[Depends(require_auth)], tags=["回测"], summary="单股回测")
async def backtest_endpoint(req: BacktestRequest):
    bt = AShareBacktester(strategy=AShareStrategy(initial_capital=req.initial_capital, max_stop_pct=req.max_stop_pct))
    r = bt.run(req.symbol, get_df(req.symbol))
    ex = r.exit_reason_counts; total = r.total_trades or 1
    return BacktestResponse(symbol=r.symbol, total_trades=r.total_trades, win_rate=r.win_rate,
        total_return_pct=r.total_return_pct, max_drawdown_pct=r.max_drawdown_pct,
        sharpe_ratio=r.sharpe_ratio, calmar_ratio=r.calmar_ratio,
        profit_factor=min(r.profit_factor, 999.99),
        target_reached_pct=ex.get("target_reached", 0)/total*100,
        hard_stop_pct=ex.get("stop_loss", 0)/total*100,
        signal_type_counts=r.signal_type_counts, exit_reason_counts=r.exit_reason_counts)

@app.post("/api/v1/backtest/batch", response_model=BatchSummaryResponse,
          dependencies=[Depends(require_auth)], tags=["回测"], summary="批量回测")
async def backtest_batch_endpoint(req: BatchBacktestRequest):
    dm = get_dm()
    bt = AShareBatchBacktester(strategy=AShareStrategy(initial_capital=req.initial_capital),
                               max_workers=req.max_workers)
    s, _ = bt.run(req.symbols, data_loader=dm.get_stock_data)
    return BatchSummaryResponse(
        symbols_total=s.symbols_total, symbols_ok=s.symbols_ok,
        avg_win_rate=s.avg_win_rate, avg_return_pct=s.avg_return_pct,
        avg_drawdown_pct=s.avg_drawdown_pct, avg_sharpe=s.avg_sharpe,
        avg_target_reached_pct=s.avg_target_reached_pct, avg_hard_stop_pct=s.avg_hard_stop_pct,
        best_symbol=s.best_symbol, best_return=s.best_return,
        worst_symbol=s.worst_symbol, worst_return=s.worst_return,
        profitable_pct=s.profitable_pct, total_trades=s.total_trades, elapsed_sec=s.elapsed_sec)
