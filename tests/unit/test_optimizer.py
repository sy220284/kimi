#!/usr/bin/env python3
"""
测试优化器是否生效
"""
import sys

sys.path.insert(0, 'src')

import pandas as pd

from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data import get_db_manager

# 加载一只股票的数据
db = get_db_manager()
df = db.get_stock_data('000063', start_date='2017-01-01', end_date='2024-12-31')
df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
df['date'] = pd.to_datetime(df['date'])

# 检测波浪信号
analyzer = UnifiedWaveAnalyzer()
signals = analyzer.detect(df, mode='all')

print(f"检测到的信号数量: {len(signals)}")
print()

for sig in signals:
    print(f"信号类型: {sig.entry_type.value}")
    print(f"  基础置信度: {sig.confidence:.2f}")
    print(f"  质量评分: {getattr(sig, 'quality_score', 'N/A')}")
    print(f"  量能评分: {getattr(sig, 'volume_score', 'N/A')}")
    print(f"  时间评分: {getattr(sig, 'time_score', 'N/A')}")
    print(f"  是否有效: {sig.is_valid}")
    print()

# 检查优化器是否被调用
print(f"优化器启用状态: {analyzer.use_quality_filter}")
print(f"优化器对象: {analyzer._entry_optimizer}")
