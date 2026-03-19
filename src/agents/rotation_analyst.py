"""
智能体框架 - 轮动分析师智能体
分析申万行业指数轮动，回退到板块动量分析
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class RotationAnalystAgent(BaseAgent):
    """轮动分析师智能体 - 基于申万行业指数"""

    def __init__(self, config_path: Path | None = None):
        super().__init__(
            agent_name="rotation_analyst",
            analysis_type=AnalysisType.ROTATION,
            config_path=config_path
        )
        self.lookback_period = 60   # 动量回看60日
        self.momentum_period = 20   # 短期动量20日
        self.min_stocks_per_sector = 3  # 板块最少股票数

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行轮动分析

        策略：
        1. 优先查询 sw_industry_index 表（申万行业指数），计算各行业动量/相对强弱
        2. 若行业指数表为空，回退到 market_data 按板块聚合动量计算
        3. 输出强弱排名、轮动建议

        Args:
            input_data: 输入数据（symbol 不使用，轮动覆盖全市场）

        Returns:
            轮动分析结果
        """
        start_time = time.time()

        try:
            result = self._analyze_sw_industry()
            if result['status'] == 'no_data':
                # 申万行业表为空，回退到市值板块分析
                result = self._analyze_by_market_sector()

            confidence = self._calc_confidence(result)

            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol='MARKET',
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result=result,
                confidence=confidence,
                state=AgentState.COMPLETED,
                execution_time=time.time() - start_time,
                error_message=None
            )

        except Exception as e:
            self.logger.error(f"轮动分析失败: {e}")
            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol='MARKET',
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={'status': 'error', 'message': str(e)},
                confidence=0.0,
                state=AgentState.ERROR,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )

    # ──────────────────────────────────────────────────
    # 主路径：申万行业指数
    # ──────────────────────────────────────────────────

    def _analyze_sw_industry(self) -> dict:
        """从 sw_industry_index 表读取行业指数并计算轮动指标"""
        from utils.db_connector import PostgresConnector
        from utils.config_loader import load_config

        cfg = load_config()
        pg_cfg = cfg.get('database', {}).get('postgres', {})

        pg = PostgresConnector(
            host=pg_cfg.get('host', 'localhost'),
            port=pg_cfg.get('port', 5432),
            database=pg_cfg.get('database', 'quant_analysis'),
            username=pg_cfg.get('username', 'quant_user'),
            password=pg_cfg.get('password', 'quant_password'),
        )

        try:
            pg.connect()
        except Exception as e:
            self.logger.warning(f"数据库连接失败，将使用回退路径: {e}")
            return {'status': 'no_data', 'reason': 'db_connect_failed'}

        cutoff = (datetime.now() - timedelta(days=self.lookback_period + 10)).strftime('%Y-%m-%d')
        sql = f"""
            SELECT industry_code, industry_name, date, close
            FROM sw_industry_index
            WHERE date >= '{cutoff}'
            ORDER BY industry_code, date
        """

        try:
            df = pg.execute_query(sql)
        except Exception as e:
            self.logger.warning(f"sw_industry_index 查询失败: {e}")
            return {'status': 'no_data', 'reason': str(e)}
        finally:
            try:
                pg.disconnect()
            except Exception:
                pass

        if df is None or df.empty:
            return {'status': 'no_data', 'reason': 'table_empty'}

        return self._calc_industry_rotation(df)

    def _calc_industry_rotation(self, df: pd.DataFrame) -> dict:
        """计算行业动量、相对强弱、轮动排名"""
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(['industry_code', 'date'])

        industries = df['industry_code'].unique()
        records = []

        for code in industries:
            idf = df[df['industry_code'] == code].copy()
            if len(idf) < self.momentum_period:
                continue

            name = idf['industry_name'].iloc[-1] if 'industry_name' in idf.columns else code
            closes = idf['close'].values

            # 动量指标
            mom_20d = (closes[-1] / closes[-self.momentum_period] - 1) * 100 if len(closes) >= self.momentum_period else 0.0
            mom_60d = (closes[-1] / closes[0] - 1) * 100 if len(closes) >= 2 else 0.0

            # 趋势（短期均线 vs 长期均线）
            ma5  = float(np.mean(closes[-5:])) if len(closes) >= 5 else closes[-1]
            ma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else closes[-1]
            trend = 'up' if ma5 > ma20 else 'down'

            # 波动率（20日日收益率标准差年化）
            returns = pd.Series(closes).pct_change().dropna()
            vol = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 5 else 0.0

            records.append({
                'code': code,
                'name': name,
                'momentum_20d': round(mom_20d, 2),
                'momentum_60d': round(mom_60d, 2),
                'trend': trend,
                'volatility': round(vol, 2),
                'latest_close': round(float(closes[-1]), 4),
            })

        if not records:
            return {'status': 'no_data', 'reason': 'insufficient_history'}

        perf_df = pd.DataFrame(records).sort_values('momentum_20d', ascending=False)

        strong = perf_df.head(5)[['name', 'momentum_20d', 'momentum_60d', 'trend']].to_dict('records')
        weak   = perf_df.tail(5)[['name', 'momentum_20d', 'momentum_60d', 'trend']].to_dict('records')

        # 轮动建议
        strong_names = [r['name'] for r in strong[:3]]
        weak_names   = [r['name'] for r in weak[:3]]
        recommendation = (
            f"强势行业：{', '.join(strong_names)}；"
            f"弱势行业：{', '.join(weak_names)}。"
            f"建议超配强势行业，减少弱势行业配置。"
        )

        return {
            'status': 'success',
            'data_source': 'sw_industry_index',
            'industry_count': len(records),
            'strong_industries': strong,
            'weak_industries': weak,
            'all_industries': perf_df.to_dict('records'),
            'recommendation': recommendation,
        }

    # ──────────────────────────────────────────────────
    # 回退路径：按上市板块聚合动量
    # ──────────────────────────────────────────────────

    def _analyze_by_market_sector(self) -> dict:
        """
        回退路径：申万行业表为空时，按上市板块（科创/创业/沪主/深主）
        聚合个股动量，输出板块相对强弱。
        覆盖全部股票而非仅取前5只，样本更具代表性。
        """
        from data.optimized_data_manager import get_optimized_data_manager

        data_mgr = get_optimized_data_manager()
        df_all = data_mgr.load_all_data()

        if df_all is None or df_all.empty:
            return {'status': 'no_data', 'reason': 'market_data_empty'}

        sector_map = {
            '科创板':  df_all['symbol'].str.startswith('688', na=False),
            '创业板':  df_all['symbol'].str.startswith(('300', '301'), na=False),
            '沪市主板': df_all['symbol'].str.startswith(('600', '601', '603', '605'), na=False),
            '深市主板': df_all['symbol'].str.startswith(('000', '001', '002', '003'), na=False),
        }

        records = []
        for sector_name, mask in sector_map.items():
            symbols = df_all[mask]['symbol'].unique()
            if len(symbols) < self.min_stocks_per_sector:
                continue

            mom_list, vol_list = [], []
            for sym in symbols:
                sdf = data_mgr.get_stock_data(sym)
                if sdf is None or len(sdf) < self.momentum_period:
                    continue
                closes = sdf['close'].values
                mom = (closes[-1] / closes[-self.momentum_period] - 1) * 100
                if not np.isnan(mom):
                    mom_list.append(mom)
                    ret = pd.Series(closes[-20:]).pct_change().dropna()
                    vol_list.append(float(ret.std() * np.sqrt(252) * 100))

            if len(mom_list) < self.min_stocks_per_sector:
                continue

            avg_mom = float(np.mean(mom_list))
            avg_vol = float(np.mean(vol_list)) if vol_list else 0.0
            records.append({
                'name': sector_name,
                'momentum_20d': round(avg_mom, 2),
                'stock_count': len(mom_list),
                'volatility': round(avg_vol, 2),
                'trend': 'up' if avg_mom > 0 else 'down',
            })

        if not records:
            return {'status': 'no_data', 'reason': 'no_sector_data'}

        perf_df = pd.DataFrame(records).sort_values('momentum_20d', ascending=False)

        strong = perf_df.head(2).to_dict('records')
        weak   = perf_df.tail(2).to_dict('records')

        strong_names = [r['name'] for r in strong]
        weak_names   = [r['name'] for r in weak]
        recommendation = (
            f"【回退模式·板块聚合】强势板块：{', '.join(strong_names)}；"
            f"弱势板块：{', '.join(weak_names)}。"
            f"注：申万行业指数表尚未入库，当前为板块级别近似分析，"
            f"精度低于行业指数模式。"
        )

        return {
            'status': 'success',
            'data_source': 'market_data_sector_fallback',
            'industry_count': len(records),
            'strong_industries': strong,
            'weak_industries': weak,
            'all_industries': perf_df.to_dict('records'),
            'recommendation': recommendation,
        }

    def _calc_confidence(self, result: dict) -> float:
        """根据结果质量计算置信度"""
        if result.get('status') != 'success':
            return 0.0
        source = result.get('data_source', '')
        count  = result.get('industry_count', 0)
        if source == 'sw_industry_index':
            base = 0.85
        else:
            base = 0.45  # 回退模式置信度低
        return min(base + count * 0.002, 1.0)

    def analyze_market_rotation(self) -> AgentOutput:
        """便捷入口：市场轮动分析（传入空 AgentInput）"""
        dummy = AgentInput(symbol='MARKET')
        return self.analyze(dummy)


# 向后兼容别名
RotationAnalyst = RotationAnalystAgent
