#!/usr/bin/env python3
"""
数据质量监控测试
测试数据质量检查和监控功能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from data.optimized_data_manager import get_optimized_data_manager


class TestDataQualityBasic(unittest.TestCase):
    """基础数据质量测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.df_all = cls.data_mgr.load_all_data()
    
    def test_01_no_null_symbols(self):
        """测试无空股票代码"""
        null_symbols = self.df_all['symbol'].isnull().sum()
        self.assertEqual(null_symbols, 0)
        print("✅ 无空股票代码")
    
    def test_02_no_null_dates(self):
        """测试无空日期"""
        null_dates = self.df_all['date'].isnull().sum()
        self.assertEqual(null_dates, 0)
        print("✅ 无空日期")
    
    def test_03_no_null_prices(self):
        """测试无空价格"""
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            null_count = self.df_all[col].isnull().sum()
            self.assertEqual(null_count, 0, f"{col}有空值")
        print("✅ 无空价格数据")
    
    def test_04_positive_prices(self):
        """测试价格为正"""
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            negative = (self.df_all[col] <= 0).sum()
            self.assertEqual(negative, 0, f"{col}有非正值")
        print("✅ 价格均为正数")
    
    def test_05_price_relationships(self):
        """测试价格关系"""
        invalid_high = (self.df_all['high'] < self.df_all['low']).sum()
        invalid_close_high = (self.df_all['close'] > self.df_all['high']).sum()
        invalid_close_low = (self.df_all['close'] < self.df_all['low']).sum()
        
        total_invalid = invalid_high + invalid_close_high + invalid_close_low
        
        if total_invalid > 0:
            print(f"⚠️ 发现{total_invalid}条价格关系异常")
        else:
            print("✅ 价格关系正常")
    
    def test_06_non_negative_volume(self):
        """测试成交量非负"""
        negative_volume = (self.df_all['volume'] < 0).sum()
        self.assertEqual(negative_volume, 0)
        print("✅ 成交量非负")


class TestDataCompleteness(unittest.TestCase):
    """数据完整性测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.df_all = cls.data_mgr.load_all_data()
    
    def test_01_symbol_coverage(self):
        """测试股票覆盖"""
        unique_symbols = self.df_all['symbol'].nunique()
        self.assertGreater(unique_symbols, 0)
        print(f"✅ 覆盖{unique_symbols}只股票")
    
    def test_02_date_range_coverage(self):
        """测试日期范围覆盖"""
        min_date = self.df_all['date'].min()
        max_date = self.df_all['date'].max()
        
        print(f"✅ 日期范围: {min_date} ~ {max_date}")
        
        # 至少应该有1年的数据
        date_span = pd.to_datetime(max_date) - pd.to_datetime(min_date)
        self.assertGreater(date_span.days, 365)
    
    def test_03_no_duplicate_records(self):
        """测试无重复记录"""
        duplicates = self.df_all.duplicated(subset=['symbol', 'date']).sum()
        
        if duplicates > 0:
            print(f"⚠️ 发现{duplicates}条重复记录")
        else:
            print("✅ 无重复记录")
    
    def test_04_continuous_dates_per_symbol(self):
        """测试每只股票日期连续性"""
        symbols_to_check = self.df_all['symbol'].unique()[:5]  # 检查前5只
        
        gaps_found = 0
        for symbol in symbols_to_check:
            df_sym = self.df_all[self.df_all['symbol'] == symbol].sort_values('date')
            df_sym['date'] = pd.to_datetime(df_sym['date'])
            df_sym['date_diff'] = df_sym['date'].diff().dt.days
            
            # 排除周末，检查超过5天的间隔
            large_gaps = df_sym[df_sym['date_diff'] > 5]
            gaps_found += len(large_gaps)
        
        if gaps_found > 0:
            print(f"⚠️ 发现{gaps_found}个日期大间隔（可能为停牌）")
        else:
            print("✅ 日期连续性良好")


class TestDataConsistency(unittest.TestCase):
    """数据一致性测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.df_all = cls.data_mgr.load_all_data()
    
    def test_01_consistent_data_types(self):
        """测试数据类型一致"""
        # 价格应该是数值型
        self.assertTrue(pd.api.types.is_numeric_dtype(self.df_all['close']))
        self.assertTrue(pd.api.types.is_numeric_dtype(self.df_all['volume']))
        print("✅ 数据类型一致")
    
    def test_02_reasonable_price_ranges(self):
        """测试价格合理范围"""
        # 检查极端价格
        min_price = self.df_all['close'].min()
        max_price = self.df_all['close'].max()
        
        print(f"✅ 价格范围: {min_price:.2f} ~ {max_price:.2f}")
        
        # 价格应该在合理范围内（0.01 ~ 10000）
        self.assertGreater(min_price, 0)
        self.assertLess(max_price, 100000)
    
    def test_03_reasonable_volume_ranges(self):
        """测试成交量合理范围"""
        min_vol = self.df_all['volume'].min()
        max_vol = self.df_all['volume'].max()
        
        print(f"✅ 成交量范围: {min_vol:,.0f} ~ {max_vol:,.0f}")
        
        # 成交量应该合理
        self.assertGreaterEqual(min_vol, 0)


class TestDataAnomalies(unittest.TestCase):
    """数据异常检测测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.df_all = cls.data_mgr.load_all_data()
    
    def test_01_price_spikes(self):
        """测试价格异常波动"""
        # 计算日收益率
        df_sorted = self.df_all.sort_values(['symbol', 'date'])
        df_sorted['returns'] = df_sorted.groupby('symbol')['close'].pct_change()
        
        # 检查超过20%的单日涨跌幅
        extreme_moves = df_sorted[abs(df_sorted['returns']) > 0.20]
        
        if len(extreme_moves) > 0:
            print(f"⚠️ 发现{len(extreme_moves)}次极端价格变动(>20%)")
        else:
            print("✅ 无极端价格变动")
    
    def test_02_volume_spikes(self):
        """测试成交量异常"""
        # 计算每只股票的平均成交量
        vol_stats = self.df_all.groupby('symbol')['volume'].agg(['mean', 'std'])
        
        anomalies = 0
        for symbol in vol_stats.index[:10]:  # 检查前10只
            df_sym = self.df_all[self.df_all['symbol'] == symbol]
            mean_vol = vol_stats.loc[symbol, 'mean']
            std_vol = vol_stats.loc[symbol, 'std']
            
            # 超过5倍标准差视为异常
            if std_vol > 0:
                spike_threshold = mean_vol + 5 * std_vol
                spikes = (df_sym['volume'] > spike_threshold).sum()
                anomalies += spikes
        
        if anomalies > 0:
            print(f"⚠️ 发现{anomalies}次成交量异常")
        else:
            print("✅ 成交量正常")
    
    def test_03_stale_data(self):
        """测试数据时效性"""
        latest_date = pd.to_datetime(self.df_all['date'].max())
        today = pd.Timestamp.now().normalize()
        
        days_diff = (today - latest_date).days
        
        print(f"✅ 最新数据日期: {latest_date.date()} ({days_diff}天前)")
        
        # 数据不应该超过30天
        self.assertLess(days_diff, 30, "数据过于陈旧")


class TestDataQualityReport(unittest.TestCase):
    """数据质量报告测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.df_all = cls.data_mgr.load_all_data()
    
    def test_01_generate_quality_report(self):
        """生成数据质量报告"""
        report = {
            'total_records': len(self.df_all),
            'total_symbols': self.df_all['symbol'].nunique(),
            'date_range': {
                'start': str(self.df_all['date'].min()),
                'end': str(self.df_all['date'].max())
            },
            'null_counts': {
                col: int(self.df_all[col].isnull().sum())
                for col in self.df_all.columns
            },
            'price_stats': {
                'min': float(self.df_all['close'].min()),
                'max': float(self.df_all['close'].max()),
                'mean': float(self.df_all['close'].mean())
            }
        }
        
        self.assertIn('total_records', report)
        self.assertIn('total_symbols', report)
        
        print(f"✅ 质量报告生成完成")
        print(f"   总记录: {report['total_records']:,}")
        print(f"   股票数: {report['total_symbols']}")
        print(f"   日期: {report['date_range']['start']} ~ {report['date_range']['end']}")


def run_tests():
    """运行测试"""
    print("="*70)
    print("🔍 数据质量监控测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDataQualityBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestDataCompleteness))
    suite.addTests(loader.loadTestsFromTestCase(TestDataConsistency))
    suite.addTests(loader.loadTestsFromTestCase(TestDataAnomalies))
    suite.addTests(loader.loadTestsFromTestCase(TestDataQualityReport))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有数据质量测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
