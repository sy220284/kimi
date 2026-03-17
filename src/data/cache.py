"""
数据缓存系统 - 避免重复请求THS接口
支持: 内存缓存 + 本地文件缓存
"""
import pandas as pd
import hashlib
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import threading


class DataCache:
    """数据缓存管理器"""
    
    def __init__(self, cache_dir: str = ".cache", ttl_hours: int = 4):
        """
        初始化缓存
        
        Args:
            cache_dir: 缓存文件目录
            ttl_hours: 缓存有效期（小时）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self._memory_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
    def _get_cache_key(self, symbol: str, start_date: str, end_date: str, ktype: str) -> str:
        """生成缓存键"""
        key_str = f"{symbol}_{start_date}_{end_date}_{ktype}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def get(self, symbol: str, start_date: str, end_date: str, ktype: str = "day") -> Optional[pd.DataFrame]:
        """
        获取缓存数据
        
        Returns:
            DataFrame or None (缓存不存在或已过期)
        """
        cache_key = self._get_cache_key(symbol, start_date, end_date, ktype)
        
        # 1. 检查内存缓存
        with self._lock:
            if cache_key in self._memory_cache:
                cached_time, df = self._memory_cache[cache_key]
                if datetime.now() - cached_time < self.ttl:
                    return df.copy()
                else:
                    del self._memory_cache[cache_key]
        
        # 2. 检查文件缓存
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                
                cached_time = cached_data['timestamp']
                if datetime.now() - cached_time < self.ttl:
                    df = cached_data['data']
                    # 加载到内存缓存
                    with self._lock:
                        self._memory_cache[cache_key] = (cached_time, df)
                    return df.copy()
                else:
                    # 删除过期缓存
                    cache_path.unlink()
            except Exception:
                # 缓存损坏，删除
                if cache_path.exists():
                    cache_path.unlink()
        
        return None
    
    def set(self, df: pd.DataFrame, symbol: str, start_date: str, end_date: str, ktype: str = "day"):
        """设置缓存"""
        if df is None or df.empty:
            return
            
        cache_key = self._get_cache_key(symbol, start_date, end_date, ktype)
        now = datetime.now()
        
        # 1. 保存到内存
        with self._lock:
            self._memory_cache[cache_key] = (now, df.copy())
        
        # 2. 保存到文件
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump({
                    'timestamp': now,
                    'data': df,
                    'metadata': {
                        'symbol': symbol,
                        'start_date': start_date,
                        'end_date': end_date,
                        'ktype': ktype,
                        'rows': len(df)
                    }
                }, f)
        except Exception as e:
            print(f"缓存保存失败: {e}")
    
    def clear_expired(self):
        """清理过期缓存"""
        now = datetime.now()
        
        # 清理内存缓存
        with self._lock:
            expired_keys = [
                k for k, (t, _) in self._memory_cache.items() 
                if now - t >= self.ttl
            ]
            for k in expired_keys:
                del self._memory_cache[k]
        
        # 清理文件缓存
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                if now - cached_data['timestamp'] >= self.ttl:
                    cache_file.unlink()
            except Exception:
                cache_file.unlink()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        memory_count = len(self._memory_cache)
        
        file_count = len(list(self.cache_dir.glob("*.pkl")))
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.pkl"))
        
        return {
            'memory_entries': memory_count,
            'file_entries': file_count,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'cache_dir': str(self.cache_dir)
        }


# 全局缓存实例
_global_cache = None

def get_cache(cache_dir: str = ".cache", ttl_hours: int = 4) -> DataCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = DataCache(cache_dir, ttl_hours)
    return _global_cache
