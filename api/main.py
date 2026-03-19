"""
FastAPI服务层 - 量化分析API
提供RESTful接口供外部调用
"""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.base_agent import AgentInput
from agents.rotation_analyst import RotationAnalystAgent
from agents.tech_analyst import TechAnalystAgent
from agents.wave_analyst import WaveAnalystAgent
from utils.config_loader import load_config
from utils.logger import get_logger

logger = get_logger(__name__)

# 全局配置
config = load_config()

# 智能体实例（懒加载）
_wave_agent: WaveAnalystAgent | None = None
_tech_agent: TechAnalystAgent | None = None
_rotation_agent: RotationAnalystAgent | None = None


def get_wave_agent() -> WaveAnalystAgent:
    """获取波浪分析智能体（单例）"""
    global _wave_agent
    if _wave_agent is None:
        use_ai = config.get('agents.wave_analyst.use_ai', False)
        model = config.get('agents.wave_analyst.model', 'deepseek/deepseek-reasoner')
        _wave_agent = WaveAnalystAgent(use_ai=use_ai, ai_model=model)
    return _wave_agent


def get_tech_agent() -> TechAnalystAgent:
    """获取技术分析智能体（单例）"""
    global _tech_agent
    if _tech_agent is None:
        use_ai = config.get('agents.technical_analyst.use_ai', False)
        model = config.get('agents.technical_analyst.model', 'deepseek/deepseek-chat')
        _tech_agent = TechAnalystAgent(use_ai=use_ai, ai_model=model)
    return _tech_agent


def get_rotation_agent() -> RotationAnalystAgent:
    """获取轮动分析智能体（单例）"""
    global _rotation_agent
    if _rotation_agent is None:
        use_ai = config.get('agents.rotation_analyst.use_ai', False)
        model = config.get('agents.rotation_analyst.model', 'deepseek/deepseek-reasoner')
        _rotation_agent = RotationAnalystAgent(use_ai=use_ai, ai_model=model)
    return _rotation_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 量化分析API服务启动")
    yield
    logger.info("🛑 量化分析API服务关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Kimi Quant Analysis API",
    description="量化分析系统API - 波浪分析、技术分析、行业轮动",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
api_config = config.get('api', {})
cors_origins = api_config.get('cors_origins', ['http://localhost:3000'])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ============================================================================
# 数据模型
# ============================================================================

class AnalysisRequest(BaseModel):
    """分析请求"""
    symbol: str = Field(..., description="股票代码，如 600519.SH")
    start_date: str | None = Field(None, description="开始日期，格式 YYYY-MM-DD")
    end_date: str | None = Field(None, description="结束日期，格式 YYYY-MM-DD")
    use_ai: bool = Field(False, description="是否启用AI增强分析")


class WaveAnalysisResponse(BaseModel):
    """波浪分析响应"""
    symbol: str
    status: str
    wave_type: str | None = None
    confidence: float
    current_wave: str | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    ai_analysis: dict | None = None
    execution_time: float


class TechAnalysisResponse(BaseModel):
    """技术分析响应"""
    symbol: str
    status: str
    signals: list[dict]
    combined_signal: dict
    confidence: float
    ai_analysis: dict | None = None
    execution_time: float


class RotationAnalysisResponse(BaseModel):
    """轮动分析响应"""
    status: str
    strong_industries: list[dict]
    weak_industries: list[dict]
    buy_point_industries: list[dict]
    recommendation: str
    ai_analysis: dict | None = None
    confidence: float
    execution_time: float


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    version: str


# ============================================================================
# API路由
# ============================================================================

@app.get('/', response_model=HealthResponse)
async def root():
    """根路径 - 服务信息"""
    return HealthResponse(
        status='ok',
        timestamp=datetime.now().isoformat(),
        version='1.0.0'
    )


@app.get('/health', response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status='ok',
        timestamp=datetime.now().isoformat(),
        version='1.0.0'
    )


@app.post('/api/v1/analysis/wave', response_model=WaveAnalysisResponse)
async def wave_analysis(request: AnalysisRequest):
    """
    波浪分析
    
    分析指定股票的波浪形态，识别推动浪、调整浪等
    """
    try:
        agent = get_wave_agent()
        
        # 临时切换AI模式
        original_use_ai = agent.use_ai
        if request.use_ai != original_use_ai:
            agent.use_ai = request.use_ai
        
        input_data = AgentInput(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        result = agent.analyze(input_data)
        
        # 恢复原始AI设置
        agent.use_ai = original_use_ai
        
        if result.state.value == 'error':
            raise HTTPException(status_code=500, detail=result.error_message)
        
        pattern = result.result.get('patterns', [])
        pattern = pattern[0] if pattern else None
        
        return WaveAnalysisResponse(
            symbol=request.symbol,
            status='success',
            wave_type=pattern.wave_type.value if pattern else None,
            confidence=result.confidence,
            current_wave=pattern.points[-1].wave_num if pattern and pattern.points else None,
            target_price=pattern.target_price if pattern else None,
            stop_loss=pattern.stop_loss if pattern else None,
            ai_analysis=result.result.get('ai_analysis'),
            execution_time=result.execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"波浪分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/v1/analysis/technical', response_model=TechAnalysisResponse)
async def technical_analysis(request: AnalysisRequest):
    """
    技术分析
    
    计算MACD、RSI、KDJ、布林带等技术指标，给出综合信号
    """
    try:
        agent = get_tech_agent()
        
        # 临时切换AI模式
        original_use_ai = agent.use_ai
        if request.use_ai != original_use_ai:
            agent.use_ai = request.use_ai
        
        input_data = AgentInput(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        result = agent.analyze(input_data)
        
        # 恢复原始AI设置
        agent.use_ai = original_use_ai
        
        if result.state.value == 'error':
            raise HTTPException(status_code=500, detail=result.error_message)
        
        return TechAnalysisResponse(
            symbol=request.symbol,
            status='success',
            signals=result.result.get('signals', []),
            combined_signal=result.result.get('combined_signal', {}),
            confidence=result.confidence,
            ai_analysis=result.result.get('ai_analysis'),
            execution_time=result.execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"技术分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/v1/analysis/rotation', response_model=RotationAnalysisResponse)
async def rotation_analysis(use_ai: bool = Query(False, description="是否启用AI增强")):
    """
    行业轮动分析
    
    分析申万行业指数轮动，识别强势/弱势行业，发现买点机会
    """
    try:
        agent = get_rotation_agent()
        
        # 临时切换AI模式
        original_use_ai = agent.use_ai
        if use_ai != original_use_ai:
            agent.use_ai = use_ai
        
        input_data = AgentInput(symbol='MARKET')
        result = agent.analyze(input_data)
        
        # 恢复原始AI设置
        agent.use_ai = original_use_ai
        
        if result.state.value == 'error':
            raise HTTPException(status_code=500, detail=result.error_message)
        
        return RotationAnalysisResponse(
            status='success',
            strong_industries=result.result.get('strong_industries', []),
            weak_industries=result.result.get('weak_industries', []),
            buy_point_industries=result.result.get('buy_point_industries', []),
            recommendation=result.result.get('recommendation', ''),
            ai_analysis=result.result.get('ai_analysis'),
            confidence=result.confidence,
            execution_time=result.execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"轮动分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/v1/stocks/search')
async def search_stocks(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50, description="返回数量限制")
):
    """
    股票搜索
    
    根据关键词搜索股票代码和名称
    """
    # TODO: 实现股票搜索功能
    return {"stocks": [], "keyword": keyword, "total": 0}


# ============================================================================
# 启动入口
# ============================================================================

def main():
    """启动API服务"""
    import uvicorn
    
    api_config = config.get('api', {})
    host = api_config.get('host', '0.0.0.0')
    port = api_config.get('port', 8000)
    
    logger.info(f"🌐 启动API服务: http://{host}:{port}")
    
    uvicorn.run(
        'api.main:app',
        host=host,
        port=port,
        reload=False,
        log_level='info'
    )


if __name__ == '__main__':
    main()
