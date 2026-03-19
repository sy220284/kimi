"""
API模块 - FastAPI服务层

提供RESTful接口:
- POST /api/v1/analysis/wave      - 波浪分析
- POST /api/v1/analysis/technical - 技术分析
- POST /api/v1/analysis/rotation  - 行业轮动分析
- GET  /api/v1/stocks/search      - 股票搜索
- GET  /health                    - 健康检查

使用示例:
    from api import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

try:
    from .main import app
    __all__ = ['app']
except ImportError as e:
    # FastAPI未安装时的降级处理
    import warnings
    warnings.warn(f"API模块导入失败: {e}. 运行 'pip install fastapi uvicorn' 安装依赖")
    app = None
    __all__ = []
