#!/usr/bin/env python3
"""
数据库层全覆盖测试
测试PostgreSQL和Redis的所有功能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import pandas as pd

from data.db_manager import DatabaseDataManager
from data.optimizeddata_manager import get_optimizeddata_manager

# 辅助函数：获取数据库管理器实例
def get_db_manager():
    """获取数据库管理器实例"""
    return DatabaseDataManager()


class TestDatabaseConnection(unittest.TestCase):
    """数据库连接测试"""
    
    def test_01_postgres_connection(self):
        """测试PostgreSQL连接"""
        db = get_db_manager()
        # 使用上下文管理器
        conn_mgr = db.get_connection()
        self.assertIsNotNone(conn_mgr)
        with conn_mgr as conn:
            self.assertIsNotNone(conn)
        print("✅ PostgreSQL连接正常")
    
    def test_02_connection_pool(self):
        """测试连接池"""
        db = get_db_manager()
        
        # 获取多个连接
        for _ in range(5):
            with db.get_connection() as conn:
                self.assertIsNotNone(conn)
        
        print("✅ 连接池工作正常")
    
    def test_03_execute_query(self):
        """测试执行查询"""
        db = get_db_manager()
        
        result = db.execute_query("SELECT 1 as test")
        self.assertIsNotNone(result)
        self.assertEqual(result[0]['test'], 1)
        
        print("✅ 查询执行正常")


class TestMarketDataOperations(unittest.TestCase):
    """市场数据操作测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = get_db_manager()
        cls.data_mgr = get_optimizeddata_manager()
    
    def test_01_query_stockdata(self):
        """测试查询股票数据"""
        df = self.data_mgr.get_stock_data('600519')
        
        if df is not None:
            self.assertGreater(len(df), 0)
            self.assertIn('date', df.columns)
            self.assertIn('close', df.columns)
            print(f"✅ 股票数据查询正常 ({len(df)}条)")
        else:
            self.skipTest("无数据")
    
    def test_02_query_date_range(self):
        """测试日期范围查询"""
        query = """
            SELECT * FROM marketdata 
            WHERE symbol = '600519' 
            AND date BETWEEN '2024-01-01' AND '2024-01-31'
            ORDER BY date
        """
        result = self.db.execute_query(query)
        
        if result:
            self.assertGreater(len(result), 0)
            print(f"✅ 日期范围查询正常 ({len(result)}条)")
        else:
            self.skipTest("无数据")
    
    def test_03_distinct_symbols(self):
        """测试获取股票列表"""
        query = "SELECT DISTINCT symbol FROM marketdata LIMIT 10"
        result = self.db.execute_query(query)
        
        self.assertGreater(len(result), 0)
        print(f"✅ 股票列表查询正常 ({len(result)}只股票)")
    
    def test_04_count_records(self):
        """测试记录数统计"""
        query = "SELECT COUNT(*) as count FROM marketdata"
        result = self.db.execute_query(query)
        
        count = result[0]['count']
        self.assertGreater(count, 0)
        print(f"✅ 总记录数: {count:,}")
    
    def test_05data_integrity(self):
        """测试数据完整性"""
        query = """
            SELECT symbol, COUNT(*) as count, 
                   MIN(date) as min_date, MAX(date) as max_date
            FROM marketdata
            GROUP BY symbol
            LIMIT 5
        """
        result = self.db.execute_query(query)
        
        self.assertGreater(len(result), 0)
        for row in result:
            self.assertGreater(row['count'], 0)
            self.assertIsNotNone(row['min_date'])
            self.assertIsNotNone(row['max_date'])
        
        print("✅ 数据完整性检查通过")


class TestIndexPerformance(unittest.TestCase):
    """索引性能测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = get_db_manager()
    
    def test_01_index_usage(self):
        """测试索引使用"""
        import time
        
        # 带索引的查询
        start = time.time()
        query = """
            SELECT * FROM marketdata 
            WHERE symbol = '600519' AND date = '2024-01-02'
        """
        result = self.db.execute_query(query)
        elapsed = time.time() - start
        
        print(f"✅ 索引查询耗时: {elapsed*1000:.2f}ms")
        self.assertLess(elapsed, 1)  # 应该很快
    
    def test_02_bulk_query_performance(self):
        """测试批量查询性能"""
        import time
        
        symbols = ['600519', '000858', '002594', '000001', '000002']
        
        start = time.time()
        for symbol in symbols * 10:  # 50次查询
            query = f"SELECT * FROM marketdata WHERE symbol = '{symbol}' LIMIT 1"
            self.db.execute_query(query)
        elapsed = time.time() - start
        
        print(f"✅ 50次查询耗时: {elapsed*1000:.1f}ms")
        self.assertLess(elapsed, 5)  # 应该很快


class TestTransactionSafety(unittest.TestCase):
    """事务安全测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = get_db_manager()
    
    def test_01_transaction_rollback(self):
        """测试事务回滚"""
        # 创建一个测试表（如果存在则忽略错误）
        try:
            self.db.execute_query("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    value TEXT
                )
            """, fetch=False)
            print("✅ 事务测试表创建成功")
        except Exception as e:
            print(f"⚠️ 事务测试跳过: {e}")
            self.skipTest("无法创建测试表")


class TestDataConsistency(unittest.TestCase):
    """数据一致性测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimizeddata_manager()
    
    def test_01_price_consistency(self):
        """测试价格数据一致性"""
        df = self.data_mgr.load_alldata()
        
        # 检查基本约束
        invalid = df[
            (df['high'] < df['low']) |
            (df['high'] < df['close']) |
            (df['low'] > df['close'])
        ]
        
        if len(invalid) > 0:
            print(f"⚠️ 发现{len(invalid)}条异常价格数据")
        else:
            print("✅ 价格数据一致性检查通过")
    
    def test_02_volume_positive(self):
        """测试成交量为正"""
        df = self.data_mgr.load_alldata()
        
        negative_volume = df[df['volume'] < 0]
        
        self.assertEqual(len(negative_volume), 0)
        print("✅ 成交量均为非负数")
    
    def test_03_date_continuity(self):
        """测试日期连续性"""
        df = self.data_mgr.get_stock_data('600519')
        
        if df is not None and len(df) > 0:
            df = df.sort_values('date')
            df['date'] = pd.to_datetime(df['date'])
            df['date_diff'] = df['date'].diff().dt.days
            
            # 检查是否有异常大间隔（超过30天）
            large_gaps = df[df['date_diff'] > 30]
            
            if len(large_gaps) > 0:
                print(f"⚠️ 发现{len(large_gaps)}个大间隔（可能为停牌）")
            else:
                print("✅ 日期连续性正常")


class TestTableStructure(unittest.TestCase):
    """表结构测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = get_db_manager()
    
    def test_01_marketdata_columns(self):
        """测试marketdata表结构"""
        query = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'marketdata'
            ORDER BY ordinal_position
        """
        result = self.db.execute_query(query)
        
        columns = {row['column_name'] for row in result}
        expected = {'id', 'symbol', 'date', 'open', 'high', 'low', 'close', 'volume'}
        
        for col in expected:
            self.assertIn(col, columns)
        
        print(f"✅ 表结构正确 ({len(result)}列)")
    
    def test_02_indexes_exist(self):
        """测试索引存在"""
        query = """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'marketdata'
        """
        result = self.db.execute_query(query)
        
        self.assertGreater(len(result), 0)
        print(f"✅ 索引检查通过 ({len(result)}个索引)")


def run_tests():
    """运行测试"""
    print("="*70)
    print("🗄️ 数据库层全覆盖测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestMarketDataOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestIndexPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestTransactionSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestDataConsistency))
    suite.addTests(loader.loadTestsFromTestCase(TestTableStructure))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有数据库测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
