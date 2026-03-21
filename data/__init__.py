"""
数据层初始化 — 新系统只需 db_manager 和 optimized_data_manager
"""
from .db_manager import DatabaseDataManager, get_db_manager
from .optimized_data_manager import OptimizedDataManager, get_optimized_data_manager

__all__ = [
    'DatabaseDataManager',
    'get_db_manager',
    'OptimizedDataManager',
    'get_optimized_data_manager',
]
