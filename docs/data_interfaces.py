#!/usr/bin/env python3
"""
智能体系统行情数据接口清单

使用方式:
    from data import get_db_manager
    from data.ths_adapter import ThsAdapter
"""

# ============================================================
# 1. 同花顺数据源适配器 (ths_adapter.py)
# ============================================================

class ThsAdapterInterfaces:
    """同花顺Web接口"""
    
    # 日线数据
    def get_daily_kline(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票日线数据"""
        pass
    
    # 实时行情
    def get_realtime_quote(self, symbol: str) -> dict:
        """获取股票实时行情"""
        pass
    
    # 股票列表
    def get_stock_list(self) -> pd.DataFrame:
        """获取同花顺股票列表"""
        pass
    
    # 行业指数(同花顺格式88xxxx)
    def get_industry_index(self, symbol: str) -> pd.DataFrame:
        """获取同花顺行业指数"""
        pass
    
    # 行业列表
    def get_industry_list(self) -> pd.DataFrame:
        """获取同花顺行业列表"""
        pass
    
    # K线数据(支持不同周期)
    def get_kline_data(self, symbol: str, period: str = 'day') -> pd.DataFrame:
        """
        获取K线数据
        period: day/week/month
        """
        pass
    
    # 概念板块
    def get_concept_list(self) -> pd.DataFrame:
        """获取概念板块列表"""
        pass
    
    # 完整历史
    def get_full_history(self, symbol: str, years: int = 5) -> pd.DataFrame:
        """获取股票完整历史数据(多年)"""
        pass


# ============================================================
# 2. 数据库管理器 (db_manager.py)
# ============================================================

class DatabaseManagerInterfaces:
    """PostgreSQL数据库接口"""
    
    # 查询股票数据
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据库查询股票历史数据"""
        pass
    
    # 获取完整历史
    def get_full_history(self, symbol: str, years: int = 5) -> pd.DataFrame:
        """获取股票完整历史(自动补充缺失数据)"""
        pass
    
    # 同步单只股票
    def sync_symbol(self, symbol: str, years: int = 5) -> int:
        """同步单只股票到数据库"""
        pass
    
    # 获取已存储股票
    def get_stored_symbols(self) -> list[str]:
        """获取数据库中已存储的股票代码列表"""
        pass
    
    # 执行SQL
    def execute_query(self, query: str, params: tuple = None) -> list:
        """执行SQL查询"""
        pass


# ============================================================
# 3. 并发数据管理器 (concurrent_data_manager.py)
# ============================================================

class ConcurrentDataManagerInterfaces:
    """6线程并发数据获取"""
    
    # 并发获取多股
    def fetch_multi_stocks(self, symbols: list, max_workers: int = 6) -> dict:
        """
        并发获取多只股票数据
        max_workers: 并发线程数(默认6)
        """
        pass
    
    # 批量更新
    def update_stocks_batch(self, symbols: list, batch_size: int = 100) -> dict:
        """批量更新股票数据到数据库"""
        pass
    
    # 并行同步
    def parallel_sync(self, symbols: list, workers: int = 6) -> dict:
        """并行同步多只股票"""
        pass


# ============================================================
# 4. 数据同步脚本 (scripts/data_sync/)
# ============================================================

"""
sw_industry_fetch.py      - 申万行业指数拉取(akshare)
  • 6线程并发
  • 支持增量/全量更新
  • 用法: python sw_industry_fetch.py [--full] [--workers N]

ths_industry_fetch.py     - 同花顺行业指数拉取(备用)
  • 6线程并发
  • 仅返回最近140个交易日

incremental_update.py     - 股票增量更新(THS)
  • 6线程并发
  • 自动跳过已更新日期
  • 节假日判断

incremental_update_ths.py - 股票增量更新(THS，旧版)
  • 单线程版本

full_reload_optimized.py  - 全量重拉(优化版)
  • 并发拉取所有股票历史

fill_missing_data.py      - 缺失数据补全
  • 检测并补充缺失的股票数据
"""


# ============================================================
# 5. 数据表结构
# ============================================================

"""
market_data - 股票行情数据
  • symbol: 股票代码(如 000001.SZ)
  • date: 日期
  • open/high/low/close: 开高低收
  • volume: 成交量
  • amount: 成交额
  • 时间范围: 1990-12-19 ~ 2026-03-19
  • 数据量: 645只股票, 228万条记录

sw_industry_index - 申万行业指数
  • industry_code: 行业代码(如 801125)
  • industry_name: 行业名称
  • date: 日期
  • open/high/low/close: 开高低收
  • volume/amount: 成交量/额
  • 时间范围: 1999-12-30 ~ 2026-03-19
  • 数据量: 123个行业, 39万条记录
"""


# ============================================================
# 6. 使用示例
# ============================================================

if __name__ == '__main__':
    # 示例1: 从数据库查询股票数据
    """
    from data import get_db_manager
    
    db = get_db_manager()
    df = db.get_stock_data('000001.SZ', '2024-01-01', '2024-12-31')
    print(df)
    """
    
    # 示例2: 使用同花顺适配器获取实时行情
    """
    from data.ths_adapter import ThsAdapter
    
    ths = ThsAdapter({})
    quote = ths.get_realtime_quote('000001.SZ')
    print(quote)
    """
    
    # 示例3: 并发获取多只股票
    """
    from data.concurrent_data_manager import ConcurrentDataManager
    
    mgr = ConcurrentDataManager()
    symbols = ['000001.SZ', '600519.SH', '000858.SZ']
    results = mgr.fetch_multi_stocks(symbols, max_workers=6)
    """
    
    # 示例4: 执行SQL查询
    """
    from data import get_db_manager
    
    db = get_db_manager()
    result = db.execute_query(
        "SELECT * FROM market_data WHERE symbol = %s ORDER BY date DESC LIMIT 10",
        ('000001.SZ',)
    )
    """
    
    pass
