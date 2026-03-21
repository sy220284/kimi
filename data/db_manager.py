"""
data/db_manager.py — 数据库数据管理器

新系统数据层：纯 PostgreSQL 访问，无 THS/东财 外部依赖。
数据写入通过 scripts/data_sync/ 的运维脚本离线完成，
运行时只读取 market_data 表。

Redis 作为可选二级缓存（加速高频查询）。
"""
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from utils.db_connector import PostgresConnector, RedisConnector
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseDataManager:
    """
    数据库数据管理器

    读取策略：
      1. Redis 缓存命中 → 直接返回
      2. 查询 PostgreSQL market_data 表
      3. 写入 Redis 缓存（可选）

    不再包含任何外部 API 拉取逻辑。
    数据通过 scripts/data_sync/ 运维脚本离线写入。
    """

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "quant_analysis",
        pg_username: Optional[str] = None,
        pg_password: Optional[str] = None,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        enable_cache: bool = True,
        cache_ttl: int = 14400,
    ):
        _user = pg_username or os.environ.get("PG_USERNAME", "quant_user")
        _pass = pg_password or os.environ.get("PG_PASSWORD", "quant_password")
        self.pg = PostgresConnector(
            host=pg_host, port=pg_port, database=pg_database,
            username=_user, password=_pass,
        )
        self.pg.connect()

        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self.redis: Optional[RedisConnector] = None
        if enable_cache:
            try:
                self.redis = RedisConnector(host=redis_host, port=redis_port)
                self.redis.connect()
            except Exception as e:
                logger.warning(f"Redis 连接失败，禁用缓存: {e}")
                self.redis = None

    def get_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取股票历史行情（只从 PostgreSQL 读取）。

        Returns:
            DataFrame 列：date/open/high/low/close/volume/amount
            无数据时返回空 DataFrame
        """
        today = datetime.now().strftime("%Y-%m-%d")
        end_date   = end_date   or today
        start_date = start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        cache_key = f"stock:{symbol}:{start_date}:{end_date}"
        if self.enable_cache and self.redis:
            try:
                cached = self.redis.get_cache(cache_key)
                if cached:
                    return pd.DataFrame(cached)
            except Exception:
                pass

        df = self._query(symbol, start_date, end_date)

        if not df.empty and self.enable_cache and self.redis:
            try:
                self.redis.set_cache(cache_key, df.to_dict("records"), self.cache_ttl)
            except Exception:
                pass

        return df

    def get_full_history(
        self,
        symbol: str,
        start_year: int = 2018,
        end_year: Optional[int] = None,
    ) -> pd.DataFrame:
        """获取完整历史（从 start_year 到 end_year）"""
        ey = end_year or datetime.now().year
        return self.get_stock_data(symbol, f"{start_year}-01-01", f"{ey}-12-31")

    def get_stored_symbols(self) -> list[str]:
        """返回数据库中已有行情的股票代码列表"""
        try:
            rows = self.pg.execute(
                "SELECT DISTINCT symbol FROM market_data ORDER BY symbol",
                fetch=True,
            )
            return [r["symbol"] for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """返回该股票数据库中最新的交易日期"""
        try:
            rows = self.pg.execute(
                "SELECT MAX(date) AS d FROM market_data WHERE symbol = %s",
                (symbol,), fetch=True,
            )
            if rows and rows[0].get("d"):
                return str(rows[0]["d"])
        except Exception:
            pass
        return None

    def count_records(self, symbol: Optional[str] = None) -> int:
        """统计记录数（可指定股票）"""
        try:
            if symbol:
                rows = self.pg.execute(
                    "SELECT COUNT(*) AS n FROM market_data WHERE symbol = %s",
                    (symbol,), fetch=True,
                )
            else:
                rows = self.pg.execute("SELECT COUNT(*) AS n FROM market_data", fetch=True)
            return int(rows[0]["n"]) if rows else 0
        except Exception:
            return 0

    def execute_query(self, query: str, params: Optional[tuple] = None) -> Optional[list]:
        """执行任意 SELECT 查询"""
        try:
            return self.pg.execute(query, params, fetch=True)
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return None

    def save_stock_data(self, symbol: str, df: pd.DataFrame) -> int:
        """
        批量写入行情数据（供运维脚本调用）。
        Returns: 成功写入的记录数
        """
        if df.empty:
            return 0
        count = 0
        for _, row in df.iterrows():
            try:
                self.pg.insert_market_data(
                    symbol=symbol,
                    date=str(row["date"]),
                    open_price=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                    amount=float(row.get("amount", 0)),
                    source="manual",
                )
                count += 1
            except Exception as e:
                logger.warning(f"写入 {symbol} {row.get('date')} 失败: {e}")
        if self.enable_cache and self.redis:
            try:
                for key in self.redis.scan_keys(f"stock:{symbol}:*"):
                    self.redis.delete(key)
            except Exception:
                pass
        logger.info(f"写入 {symbol}: {count}/{len(df)} 条")
        return count

    def invalidate_cache(self, symbol: Optional[str] = None):
        """清除缓存（不指定则清全部）"""
        if not (self.enable_cache and self.redis):
            return
        try:
            pattern = f"stock:{symbol}:*" if symbol else "stock:*"
            for key in self.redis.scan_keys(pattern):
                self.redis.delete(key)
        except Exception as e:
            logger.warning(f"清除缓存失败: {e}")

    def _query(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """内部：查询并标准化返回"""
        sql = """
            SELECT date, open, high, low, close, volume, amount
            FROM market_data
            WHERE symbol = %s AND date BETWEEN %s AND %s
            ORDER BY date
        """
        try:
            rows = self.pg.execute(sql, (symbol, start_date, end_date), fetch=True)
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            for col in ("open", "high", "low", "close", "amount"):
                if col in df.columns:
                    df[col] = df[col].astype(float)
            if "volume" in df.columns:
                df["volume"] = df["volume"].astype(float)
            df["date"] = df["date"].astype(str)
            return df
        except Exception as e:
            logger.error(f"查询 {symbol} 失败: {e}")
            return pd.DataFrame()

    def close(self):
        """关闭连接"""
        try: self.pg.disconnect()
        except Exception: pass
        if self.redis:
            try: self.redis.disconnect()
            except Exception: pass

    def __repr__(self) -> str:
        return f"DatabaseDataManager(cache={'on' if self.enable_cache else 'off'})"


_db_manager: Optional[DatabaseDataManager] = None


def get_db_manager() -> DatabaseDataManager:
    """获取全局单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseDataManager()
    return _db_manager
