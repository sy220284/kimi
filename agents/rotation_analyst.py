"""
智能体框架 - 轮动分析师智能体 (AI增强版)
分析申万行业指数轮动，集成AI市场环境分析
"""
import contextlib
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class RotationAnalystAgent(BaseAgent):
    """
    轮动分析师智能体 - 基于申万行业指数
    
    功能:
    1. 行业动量分析（申万行业指数）
    2. 强势行业买点识别（波浪分析）
    3. AI推理增强（MarketContextAgent）- 市场环境解读和配置建议
    
    使用AI增强:
        agent = RotationAnalystAgent(use_ai=True, ai_model="deepseek/deepseek-reasoner")
    """

    def __init__(
        self,
        config_path: Path | None = None,
        use_ai: bool = False,
        ai_model: str = "deepseek/deepseek-reasoner"
    ):
        super().__init__(
            agent_name="rotation_analyst",
            analysis_type=AnalysisType.ROTATION,
            config_path=config_path
        )
        self.lookback_period = 60   # 动量回看60日
        self.momentum_period = 20   # 短期动量20日
        self.min_stocks_per_sector = 3  # 板块最少股票数
        
        # AI子代理
        self.use_ai = use_ai
        self.ai_agent = None
        if use_ai:
            try:
                from agents.ai_subagents import MarketContextAgent
                self.ai_agent = MarketContextAgent(model=ai_model)
                self.logger.info(f"AI子代理已启用: {ai_model}")
            except Exception as e:
                self.logger.warning(f"AI子代理初始化失败: {e}")
                self.use_ai = False

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行轮动分析（含日级结果缓存，同一交易日重复调用直接返回缓存）

        策略：
        1. 优先查询 sw_industry_index 表（申万行业指数），计算各行业动量/相对强弱
        2. 若行业指数表为空，回退到 market_data 按板块聚合动量计算
        3. 对强势行业进行波浪分析，识别买点
        4. AI增强：市场环境解读、板块配置建议
        5. 输出强弱排名、轮动建议、买点行业、AI分析

        OPT-B4: 行业轮动分析在同一天结果不变，缓存 TTL=4h，减少重复 DB 查询
        """
        start_time = time.time()

        # OPT-B4: 日内结果缓存（行业轮动结果在当天内不变）
        today = datetime.now().strftime('%Y-%m-%d %H')   # 按小时 key（每4小时刷新）
        cache_key = f'rotation_{today}'
        if hasattr(self, '_result_cache') and self._result_cache.get('key') == cache_key:
            cached = self._result_cache['output']
            cached.execution_time = 0.0  # 缓存命中
            return cached

        try:
            result = self._analyze_sw_industry()
            if result['status'] == 'no_data':
                # 申万行业表为空，回退到市值板块分析
                result = self._analyze_by_market_sector()

            # 分析强势行业的买点
            if result.get('status') == 'success':
                buy_points = self._analyze_industry_buy_points(result.get('all_industries', []))
                result['buy_point_industries'] = buy_points

            # AI推理增强
            ai_result = None
            if self.use_ai and self.ai_agent and result.get('status') == 'success':
                try:
                    from agents.ai_subagents import AIAgentInput
                    
                    ai_input = AIAgentInput(
                        raw_data=result,
                        context=f"分析日期: {datetime.now().strftime('%Y-%m-%d')}"
                    )
                    
                    ai_output = self.ai_agent.analyze(ai_input)
                    
                    ai_result = {
                        'reasoning': ai_output.reasoning,
                        'conclusion': ai_output.conclusion,
                        'confidence': ai_output.confidence,
                        'action_suggestion': ai_output.action_suggestion,
                        'details': ai_output.details
                    }
                    
                    result['ai_analysis'] = ai_result
                    
                except Exception as e:
                    self.logger.warning(f"AI分析失败: {e}")
                    result['ai_error'] = str(e)

            confidence = self._calc_confidence(result, ai_result)

            output = AgentOutput(
                agent_type=self.analysis_type.value,
                symbol='MARKET',
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result=result,
                confidence=confidence,
                state=AgentState.COMPLETED,
                execution_time=time.time() - start_time,
                error_message=None
            )
            # OPT-B4: 写入日内缓存
            self._result_cache = {'key': cache_key, 'output': output}
            return output

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

    def _analyze_industry_buy_points(self, industries: list) -> list:
        """
        分析强势行业的波浪买点
        
        对排名靠前的行业进行波浪分析，识别：
        - C浪底部 (调整浪结束)
        - 2浪回调买点
        - 4浪整理买点
        """
        from utils.config_loader import load_config
        from utils.db_connector import PostgresConnector
        from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer

        if not industries:
            return []

        cfg = load_config()
        pg_cfg = cfg.get('database', {}).get('postgres', {})

        pg = PostgresConnector(
            host=pg_cfg.get('host', 'localhost'),
            port=pg_cfg.get('port', 5432),
            database=pg_cfg.get('database', 'quant_analysis'),
            username=pg_cfg.get('username', 'quant_user'),
            password=pg_cfg.get('password', ''),
        )

        buy_point_industries = []
        analyzer = UnifiedWaveAnalyzer()

        # 只分析排名前10的行业
        top_industries = [ind for ind in industries if ind.get('momentum_20d', 0) > 0][:10]

        # 在循环外统一连接，避免重复初始化和连接泄漏
        try:
            pg.connect()
            
            for industry in top_industries:
                code = industry.get('code', '')
                name = industry.get('name', '')

                try:
                    # 获取行业指数近期数据
                    sql = """
                        SELECT date, open, high, low, close, volume
                        FROM sw_industry_index
                        WHERE industry_code = %s
                        ORDER BY date DESC
                        LIMIT 120
                    """
                    rows = pg.execute(sql, (code,), fetch=True)

                    if not rows or len(rows) < 60:
                        continue

                    # 转换为DataFrame并转换数据类型
                    df = pd.DataFrame(rows)
                    df = df.sort_values('date')
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # 转换价格列为float避免Decimal问题
                    price_cols = ['open', 'high', 'low', 'close', 'volume']
                    for col in price_cols:
                        if col in df.columns:
                            df[col] = df[col].astype(float)

                    # 运行波浪分析
                    signals = analyzer.detect(df, mode='all')
                    
                    # 获取最佳信号
                    best_signal = None
                    for signal in signals:
                        if signal.is_valid and signal.confidence >= 0.5:
                            if best_signal is None or signal.confidence > best_signal.confidence:
                                best_signal = signal
                    
                    if best_signal:
                        buy_point_industries.append({
                            'code': code,
                            'name': name,
                            'momentum_20d': industry.get('momentum_20d'),
                            'buy_signal': {
                                'type': best_signal.entry_type.value,
                                'entry_price': round(best_signal.entry_price, 4),
                                'stop_loss': round(best_signal.stop_loss, 4),
                                'target_price': round(best_signal.target_price, 4),
                                'confidence': round(best_signal.confidence, 2),
                                'quality_score': round(best_signal.quality_score, 2) if hasattr(best_signal, 'quality_score') else 0,
                            }
                        })

                except Exception as e:
                    self.logger.warning(f"行业 {name} 买点分析失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
        finally:
            # 循环结束后统一断开连接
            with contextlib.suppress(Exception):
                pg.disconnect()

        # 按置信度排序
        buy_point_industries.sort(
            key=lambda x: x['buy_signal']['confidence'],
            reverse=True
        )

        return buy_point_industries

    # ──────────────────────────────────────────────────
    # 主路径：申万行业指数
    # ──────────────────────────────────────────────────

    def _analyze_sw_industry(self) -> dict:
        """从 sw_industry_index 表读取行业指数并计算轮动指标"""
        from utils.config_loader import load_config
        from utils.db_connector import PostgresConnector

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
        # 使用参数化查询防止SQL注入
        sql = """
            SELECT industry_code, industry_name, date, close
            FROM sw_industry_index
            WHERE date >= %s
            ORDER BY industry_code, date
        """

        try:
            # 使用参数化查询
            rows = pg.execute(sql, (cutoff,), fetch=True)
            if not rows:
                return {'status': 'no_data', 'reason': 'table_empty'}
            df = pd.DataFrame(rows)
        except Exception as e:
            self.logger.warning(f"sw_industry_index 查询失败: {e}")
            return {'status': 'no_data', 'reason': str(e)}
        finally:
            with contextlib.suppress(Exception):
                pg.disconnect()

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
            closes = np.array(idf['close'].values, dtype=float)  # 转换为float避免Decimal问题

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

    def _calc_confidence(self, result: dict, ai_result: dict | None = None) -> float:
        """根据结果质量计算置信度"""
        if result.get('status') != 'success':
            return 0.0
        
        source = result.get('data_source', '')
        count  = result.get('industry_count', 0)
        
        if source == 'sw_industry_index':
            base = 0.85
        else:
            base = 0.45  # 回退模式置信度低
        
        base_confidence = min(base + count * 0.002, 1.0)
        
        # 综合AI置信度
        if ai_result and ai_result.get('confidence'):
            return (base_confidence + ai_result['confidence']) / 2
        
        return base_confidence

    def analyze_market_rotation(self) -> AgentOutput:
        """便捷入口：市场轮动分析（传入空 AgentInput）"""
        dummy = AgentInput(symbol='MARKET')
        return self.analyze(dummy)


# 向后兼容别名
RotationAnalyst = RotationAnalystAgent
