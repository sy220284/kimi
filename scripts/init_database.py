#!/usr/bin/env python3
"""
数据库初始化脚本
创建智能体量化分析系统所需的数据库表结构
"""

import psycopg2
from psycopg2 import sql
import yaml
import os
from pathlib import Path

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_db_connection(config):
    """获取数据库连接"""
    db_config = config['database']['postgres']
    
    conn = psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['username'],
        password=db_config['password']
    )
    return conn

def create_tables(conn):
    """创建所有表"""
    cursor = conn.cursor()
    
    # 1. 行情数据表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_data (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        date DATE NOT NULL,
        open DECIMAL(10, 4),
        high DECIMAL(10, 4),
        low DECIMAL(10, 4),
        close DECIMAL(10, 4),
        volume BIGINT,
        amount DECIMAL(15, 2),
        data_source VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, date)
    )
    """)
    
    # 2. 申万行业指数表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sw_industry_index (
        id SERIAL PRIMARY KEY,
        industry_code VARCHAR(20) NOT NULL,
        industry_name VARCHAR(100),
        date DATE NOT NULL,
        open DECIMAL(10, 4),
        high DECIMAL(10, 4),
        low DECIMAL(10, 4),
        close DECIMAL(10, 4),
        volume BIGINT,
        amount DECIMAL(15, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(industry_code, date)
    )
    """)
    
    # 3. 分析结果表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analysis_results (
        id SERIAL PRIMARY KEY,
        analyst_type VARCHAR(50) NOT NULL,
        symbol VARCHAR(20),
        analysis_date DATE NOT NULL,
        result_json JSONB,
        confidence_score DECIMAL(5, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(analyst_type, symbol, analysis_date)
    )
    """)
    
    # 4. 技术指标表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS technical_indicators (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        date DATE NOT NULL,
        indicator_name VARCHAR(50) NOT NULL,
        indicator_value JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, date, indicator_name)
    )
    """)
    
    # 5. 波浪分析表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wave_analysis (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        analysis_date DATE NOT NULL,
        wave_pattern JSONB,
        wave_count INTEGER,
        target_prices JSONB,
        stop_loss DECIMAL(10, 4),
        confidence DECIMAL(5, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, analysis_date)
    )
    """)
    
    # 6. 轮动分析表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rotation_analysis (
        id SERIAL PRIMARY KEY,
        analysis_date DATE NOT NULL,
        industry_rankings JSONB,
        recommended_allocation JSONB,
        rotation_signals JSONB,
        confidence DECIMAL(5, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(analysis_date)
    )
    """)
    
    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_date ON market_data(symbol, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sw_industry_date ON sw_industry_index(industry_code, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_type_date ON analysis_results(analyst_type, analysis_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_technical_symbol_date ON technical_indicators(symbol, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wave_symbol_date ON wave_analysis(symbol, analysis_date)")
    
    conn.commit()
    print("✅ 数据库表创建完成")

def create_hypertables(conn):
    """创建TimescaleDB超表（如果可用）"""
    cursor = conn.cursor()
    
    try:
        # 检查TimescaleDB扩展
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        
        # 将market_data转换为超表
        cursor.execute("""
        SELECT create_hypertable('market_data', 'date', 
                                 if_not_exists => TRUE,
                                 chunk_time_interval => INTERVAL '1 month')
        """)
        
        # 将sw_industry_index转换为超表
        cursor.execute("""
        SELECT create_hypertable('sw_industry_index', 'date', 
                                 if_not_exists => TRUE,
                                 chunk_time_interval => INTERVAL '1 month')
        """)
        
        conn.commit()
        print("✅ TimescaleDB超表创建完成")
    except Exception as e:
        print(f"⚠️ TimescaleDB扩展不可用，使用普通表: {e}")
        conn.rollback()

def main():
    """主函数"""
    print("🚀 开始初始化数据库...")
    
    try:
        # 加载配置
        config = load_config()
        print("✅ 配置文件加载成功")
        
        # 连接数据库
        conn = get_db_connection(config)
        print("✅ 数据库连接成功")
        
        # 创建表
        create_tables(conn)
        
        # 创建超表
        create_hypertables(conn)
        
        # 关闭连接
        conn.close()
        print("✅ 数据库初始化完成")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        raise

if __name__ == "__main__":
    main()