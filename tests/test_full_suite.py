#!/usr/bin/env python3
"""
kimi 完整测试套件 — 单元/集成/回归
覆盖：波浪算法 / 买点评分 / 共振 / 自适应参数 / 回测引擎 / 性能适配器 / 配置管理

所有测试均不依赖数据库，使用合成数据验证逻辑正确性。
运行方式：pytest tests/test_full_suite.py -v
"""
import sys, os, time, unittest
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 合成数据工厂 ────────────────────────────────────────────────────────────
def make_df(n=300, slope=0.0003, seed=42, vol=0.012):
    np.random.seed(seed); t = np.arange(n)
    p = 100 * np.exp(slope*t + vol*np.cumsum(np.random.randn(n)))
    hi = p*(1+abs(np.random.randn(n)*0.007))
    lo = p*(1-abs(np.random.randn(n)*0.007))
    return pd.DataFrame({
        'date':   pd.date_range('2021-01-01', periods=n, freq='B').strftime('%Y-%m-%d'),
        'open':   p, 'high': hi, 'low': lo, 'close': p,
        'volume': np.random.randint(1e6, 1e7, n).astype(float)
    })

def mkp(i, price):
    from analysis.wave.elliott_wave import WavePoint
    return WavePoint(i, f'2024-01-{i+1:02d}', float(price))


# ══════════════════════════════════════════════════════════════════════════════
# 1. 单元测试 — 波浪验证函数
# ══════════════════════════════════════════════════════════════════════════════
class TestWaveValidation(unittest.TestCase):
    """validate_* 函数正确性测试"""

    def setUp(self):
        from analysis.wave.elliott_wave import (
            validate_flat, validate_zigzag, validate_triangle,
            validate_diagonal, validate_impulse_rules)
        self.vf = validate_flat
        self.vz = validate_zigzag
        self.vt = validate_triangle
        self.vd = validate_diagonal
        self.vi = validate_impulse_rules

    # ── ZigZag ──
    def test_zigzag_deep_valid(self):
        pts = [mkp(0,100), mkp(5,72), mkp(10,88), mkp(15,58)]
        v, _, s = self.vz(pts)
        self.assertTrue(v); self.assertGreater(s, 0.5)

    def test_zigzag_shallow_valid(self):
        pts = [mkp(0,100), mkp(5,84), mkp(10,94), mkp(15,72)]
        v, _, s = self.vz(pts)
        self.assertTrue(v)

    def test_zigzag_insufficient_points(self):
        pts = [mkp(0,100), mkp(5,80)]
        # 点数不足时返回 valid=False（errors 可能为空，检查 valid 即可）
        v, _, _ = self.vz(pts)
        self.assertFalse(v)

    # ── Flat (三种子类型) ──
    def test_flat_expanded_valid(self):
        pts = [mkp(0,100), mkp(5,82), mkp(10,108), mkp(15,72)]
        v, _, s = self.vf(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.7)

    def test_flat_regular_valid(self):
        pts = [mkp(0,100), mkp(5,82), mkp(10,99), mkp(15,78)]
        v, _, s = self.vf(pts)
        self.assertTrue(v); self.assertGreater(s, 0.5)

    def test_flat_running_valid(self):
        pts = [mkp(0,100), mkp(5,88), mkp(10,102), mkp(15,92)]
        v, _, s = self.vf(pts)
        self.assertTrue(v)

    # ── Triangle ──
    def test_triangle_symmetric_valid(self):
        pts = [mkp(0,100), mkp(5,85), mkp(10,95), mkp(15,87), mkp(20,93)]
        v, _, s = self.vt(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.9)

    def test_triangle_fibonacci_ideal(self):
        """黄金比例收缩三角形 score=1.0"""
        pts = [mkp(0,100), mkp(5,86), mkp(10,97), mkp(15,89), mkp(20,95)]
        v, _, s = self.vt(pts)
        self.assertTrue(v); self.assertGreater(s, 0.7)

    def test_triangle_not_enough_points(self):
        pts = [mkp(0,100), mkp(5,85), mkp(10,95)]
        v, errors, _ = self.vt(pts)
        self.assertFalse(v)

    # ── Diagonal ──
    def test_diagonal_ending_valid(self):
        """Ending Diagonal: 浪4进入浪1区域（重叠）"""
        pts = [mkp(0,100), mkp(5,116), mkp(10,107), mkp(15,119), mkp(20,111)]
        v, _, s = self.vd(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.85)

    def test_diagonal_leading_valid(self):
        pts = [mkp(0,50), mkp(5,62), mkp(10,55), mkp(15,65), mkp(20,59)]
        v, _, s = self.vd(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.8)

    def test_diagonal_impulse_rejected(self):
        """普通推动浪不应被识别为对角线浪"""
        pts = [mkp(0,100), mkp(5,115), mkp(10,108), mkp(15,130), mkp(20,120)]
        v, _, s = self.vd(pts)
        self.assertFalse(v)

    # ── Impulse ──
    def test_impulse_standard_valid(self):
        pts = [mkp(0,100), mkp(5,120), mkp(8,108),
               mkp(15,145), mkp(20,132), mkp(28,168)]
        # validate_impulse_rules 返回 (valid, errors, score, fib_details)
        result = self.vi(pts)
        v, errors, s = result[0], result[1], result[2]
        self.assertTrue(v)
        self.assertGreater(s, 0.5)

    def test_impulse_rule_wave4_overlap(self):
        """浪4进入浪1区域应该失败"""
        pts = [mkp(0,100), mkp(5,120), mkp(8,105),
               mkp(15,140), mkp(18,115), mkp(25,155)]
        result = self.vi(pts)
        v = result[0]
        self.assertFalse(v)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 单元测试 — TechnicalIndicators
# ══════════════════════════════════════════════════════════════════════════════
class TestTechnicalIndicators(unittest.TestCase):
    """技术指标计算正确性"""

    def setUp(self):
        from analysis.technical.indicators import TechnicalIndicators
        self.ti = TechnicalIndicators()
        self.df = make_df(250, seed=0)

    def test_calculate_all_returns_df(self):
        result = self.ti.calculate_all(self.df.copy())
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), len(self.df))

    def test_macd_columns_exist(self):
        result = self.ti.calculate_all(self.df.copy())
        self.assertIn('MACD', result.columns)
        self.assertIn('MACD_Signal', result.columns)
        self.assertIn('MACD_Histogram', result.columns)

    def test_rsi_range(self):
        result = self.ti.calculate_all(self.df.copy())
        self.assertIn('RSI14', result.columns)
        rsi_vals = result['RSI14'].dropna()
        self.assertTrue((rsi_vals >= 0).all())
        self.assertTrue((rsi_vals <= 100).all())

    def test_kdj_columns(self):
        result = self.ti.calculate_all(self.df.copy())
        self.assertIn('K', result.columns)
        self.assertIn('D', result.columns)
        self.assertIn('J', result.columns)

    def test_ma_cumsum_correctness(self):
        """验证 numpy cumsum MA与 pandas rolling 结果一致"""
        result = self.ti.calculate_all(self.df.copy())
        self.assertIn('MA20', result.columns)
        # pandas reference
        ref_ma20 = self.df['close'].rolling(20).mean()
        np.testing.assert_allclose(
            result['MA20'].dropna().values,
            ref_ma20.dropna().values,
            rtol=1e-8
        )

    def test_bb_columns(self):
        result = self.ti.calculate_all(self.df.copy())
        self.assertIn('BB_Upper', result.columns)
        self.assertIn('BB_Lower', result.columns)
        self.assertIn('BB_Width', result.columns)

    def test_no_info_log_spam(self):
        """OPT-0: calculate_all 不再输出 INFO 日志"""
        import logging, io
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.setLevel(logging.INFO)
        logging.getLogger().addHandler(h)
        self.ti.calculate_all(self.df.copy())
        logging.getLogger().removeHandler(h)
        info_lines = [l for l in buf.getvalue().split('\n') if '计算完成' in l]
        self.assertEqual(len(info_lines), 0, "calculate_all 不应输出 INFO 日志")


# ══════════════════════════════════════════════════════════════════════════════
# 3. 单元测试 — EntryOptimizer 买点评分
# ══════════════════════════════════════════════════════════════════════════════
class TestEntryOptimizer(unittest.TestCase):
    """买点7维评分测试"""

    def setUp(self):
        from analysis.wave.entry_optimizer import WaveEntryOptimizer
        from analysis.technical.indicators import TechnicalIndicators
        self.eo = WaveEntryOptimizer.from_config()
        self.ti = TechnicalIndicators()
        self.df = self.ti.calculate_all(make_df(300, seed=5))
        self.idx = len(self.df) - 1

    def test_seven_detectors_exist(self):
        methods = [m for m in dir(self.eo) if m.startswith('_detect')]
        self.assertGreaterEqual(len(methods), 7)

    def test_volume_shrink_range(self):
        s = self.eo._detect_volume_shrink(self.df, self.idx)
        self.assertGreaterEqual(s, 0.0); self.assertLessEqual(s, 1.0)

    def test_ma_alignment_range(self):
        s = self.eo._detect_ma_alignment(self.df, self.idx)
        self.assertGreaterEqual(s, 0.0); self.assertLessEqual(s, 1.0)

    def test_bb_squeeze_range(self):
        s = self.eo._detect_bb_squeeze(self.df, self.idx)
        self.assertGreaterEqual(s, 0.0); self.assertLessEqual(s, 1.0)

    def test_macd_divergence_range(self):
        s = self.eo._detect_macd_divergence(self.df, self.idx)
        self.assertGreaterEqual(s, 0.0); self.assertLessEqual(s, 1.0)

    def test_rsi_oversold_range(self):
        s = self.eo._detect_rsi_oversold(self.df, self.idx)
        self.assertGreaterEqual(s, 0.0); self.assertLessEqual(s, 1.0)

    def test_get_buy_rating(self):
        # strong_buy >= 0.5, buy >= 0.4, watch >= 0.35
        self.assertEqual(self.eo.get_buy_rating(0.72), '强买入')
        self.assertEqual(self.eo.get_buy_rating(0.50), '强买入')  # 边界值=强买入
        self.assertEqual(self.eo.get_buy_rating(0.45), '买入')
        self.assertEqual(self.eo.get_buy_rating(0.40), '买入')
        self.assertEqual(self.eo.get_buy_rating(0.37), '关注')
        self.assertEqual(self.eo.get_buy_rating(0.20), '观望')

    def test_from_config_loads_params(self):
        self.assertGreater(self.eo.strong_buy_threshold, 0)
        self.assertGreater(self.eo.macd_divergence_weight, 0)


# ══════════════════════════════════════════════════════════════════════════════
# 4. 单元测试 — ResonanceAnalyzer
# ══════════════════════════════════════════════════════════════════════════════
class TestResonanceAnalyzer(unittest.TestCase):
    """共振分析测试"""

    def setUp(self):
        from analysis.wave.resonance import ResonanceAnalyzer, SignalDirection
        from analysis.technical.indicators import TechnicalIndicators
        self.ra = ResonanceAnalyzer()
        self.SignalDirection = SignalDirection
        ti = TechnicalIndicators()
        self.df = ti.calculate_all(make_df(300, seed=10))
        self.df_raw = make_df(300, seed=10)

    def test_analyze_returns_result(self):
        result = self.ra.analyze(self.df_raw.copy())
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.overall_direction)

    def test_analyze_precomputed_faster(self):
        t0 = time.perf_counter()
        for _ in range(20): self.ra.analyze_precomputed(self.df)
        t_fast = (time.perf_counter()-t0)/20

        t0 = time.perf_counter()
        for _ in range(20): self.ra.analyze(self.df_raw.copy())
        t_slow = (time.perf_counter()-t0)/20
        self.assertLess(t_fast, t_slow, "precomputed 路径应比 full 路径快")

    def test_analyze_precomputed_consistent(self):
        r1 = self.ra.analyze_precomputed(self.df)
        r2 = self.ra.analyze(self.df_raw.copy())
        self.assertEqual(r1.overall_direction.value, r2.overall_direction.value)

    def test_market_state_adaptive_weights(self):
        """E2: 市场状态自适应权重"""
        src = open('analysis/wave/resonance.py').read()
        self.assertIn("trending", src)
        self.assertIn("1.4", src)  # 趋势市 MACD 权重

    def test_volume_analyzer_has_obv(self):
        """E5: VolumeAnalyzer 升级包含 OBV"""
        from analysis.wave.resonance import VolumeAnalyzer
        import inspect
        src = inspect.getsource(VolumeAnalyzer.analyze_signal)
        self.assertIn('obv', src.lower())

    def test_volume_analyzer_confidence(self):
        from analysis.wave.resonance import VolumeAnalyzer
        result = VolumeAnalyzer.analyze_signal(self.df)
        self.assertGreater(result.confidence, 0)
        self.assertGreater(len(result.description), 0)


# ══════════════════════════════════════════════════════════════════════════════
# 5. 单元测试 — AdaptiveParams
# ══════════════════════════════════════════════════════════════════════════════
class TestAdaptiveParams(unittest.TestCase):
    """自适应参数系统测试"""

    def setUp(self):
        from analysis.wave.adaptive_params import AdaptiveParameterOptimizer, MarketCondition
        self.opt = AdaptiveParameterOptimizer
        self.MC = MarketCondition

    def test_base_params_tuned(self):
        """E4: 基准参数已调整"""
        self.assertEqual(self.opt.BASE_PARAMS['atr_mult'], 0.4)
        self.assertEqual(self.opt.BASE_PARAMS['atr_period'], 10)
        self.assertEqual(self.opt.BASE_PARAMS['confidence_threshold'], 0.45)

    def test_optimize_returns_params(self):
        df = make_df(200, seed=0)
        ap = self.opt.optimize(df)
        self.assertIsNotNone(ap)
        self.assertGreater(ap.atr_mult, 0)
        self.assertGreater(ap.confidence_threshold, 0)

    def test_cache_speedup(self):
        """OPT-2: _adaptive_cache 命中后极快"""
        from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
        ua = UnifiedWaveAnalyzer()
        df = make_df(200, seed=0)
        ua._apply_adaptive_params(df)  # 预热

        t0 = time.perf_counter()
        for _ in range(100): ua._apply_adaptive_params(df)
        t_cached = (time.perf_counter()-t0)/100*1000
        self.assertLess(t_cached, 0.5, "缓存命中应 <0.5ms")


# ══════════════════════════════════════════════════════════════════════════════
# 6. 单元测试 — WaveStrategy 出场逻辑
# ══════════════════════════════════════════════════════════════════════════════
class TestWaveStrategyExit(unittest.TestCase):
    """出场机制完整性测试"""

    def setUp(self):
        from analysis.backtest.wave_backtester import WaveStrategy
        self.ws = WaveStrategy()

    def test_max_holding_days_exists(self):
        """E3: 时间止损参数"""
        self.assertTrue(hasattr(self.ws, 'max_holding_days'))
        self.assertEqual(self.ws.max_holding_days, 60)

    def test_breakeven_pct_exists(self):
        """E3: 保本止损参数"""
        self.assertTrue(hasattr(self.ws, 'breakeven_pct'))
        self.assertEqual(self.ws.breakeven_pct, 0.05)

    def test_time_stop_in_code(self):
        src = open('analysis/backtest/wave_backtester.py').read()
        self.assertIn('time_stop', src)

    def test_breakeven_logic_in_code(self):
        src = open('analysis/backtest/wave_backtester.py').read()
        self.assertIn('breakeven_pct', src)
        self.assertIn('entry_price', src)

    def test_kelly_enabled_default(self):
        self.assertTrue(self.ws.use_kelly)
        self.assertEqual(self.ws.kelly_max_fraction, 0.25)

    def test_trailing_stop_enabled_default(self):
        self.assertTrue(self.ws.use_trailing_stop)
        self.assertEqual(self.ws.trailing_stop_pct, 0.08)

    def test_numpy_precomputed_in_run(self):
        """OPT-B1: run() 使用 numpy 数组代替 df.iloc"""
        src = open('analysis/backtest/wave_backtester.py').read()
        self.assertIn('_closes', src)
        self.assertIn('_dates_str', src)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 单元测试 — PerformanceAdaptor
# ══════════════════════════════════════════════════════════════════════════════
class TestPerformanceAdaptor(unittest.TestCase):
    """设备性能适配器测试"""

    def setUp(self):
        from utils.performance_adaptor import get_adaptor, reset_adaptor, DeviceTier, PerfProfile
        self.get_adaptor = get_adaptor
        self.reset = reset_adaptor
        self.Tier = DeviceTier
        self.Profile = PerfProfile

    def tearDown(self):
        self.reset()

    def test_adaptor_returns_profile(self):
        cfg = self.get_adaptor()
        self.assertIsInstance(cfg, self.Profile)

    def test_all_tiers_have_params(self):
        for tier in self.Tier:
            self.reset()
            cfg = self.get_adaptor(force_tier=tier)
            self.assertGreater(cfg.scan_workers, 0)
            self.assertGreater(cfg.lru_max_symbols, 0)

    def test_low_tier_conservative(self):
        cfg = self.get_adaptor(force_tier=self.Tier.LOW)
        self.assertLessEqual(cfg.scan_workers, 2)
        self.assertLessEqual(cfg.lru_max_symbols, 300)

    def test_extreme_tier_aggressive(self):
        self.reset()
        cfg = self.get_adaptor(force_tier=self.Tier.EXTREME)
        self.assertGreaterEqual(cfg.scan_workers, 16)
        self.assertGreaterEqual(cfg.lru_max_symbols, 5000)

    def test_env_override(self):
        import os
        self.reset()
        os.environ['KIMI_SCAN_WORKERS'] = '3'
        cfg = self.get_adaptor(force_tier=self.Tier.HIGH)
        del os.environ['KIMI_SCAN_WORKERS']
        self.assertEqual(cfg.scan_workers, 3)


# ══════════════════════════════════════════════════════════════════════════════
# 8. 单元测试 — IncrementalIndicatorCache
# ══════════════════════════════════════════════════════════════════════════════
class TestIncrementalCache(unittest.TestCase):
    """OPT-7: 增量指标缓存测试"""

    def setUp(self):
        from data.incremental_indicator_cache import IncrementalIndicatorCache
        # 新实例避免单例干扰
        IncrementalIndicatorCache._instance = None
        self.cache = IncrementalIndicatorCache(max_symbols=50)
        self.df = make_df(200, seed=0)

    def test_miss_computes_indicators(self):
        result = self.cache.get('SYM001', self.df.copy())
        self.assertIn('MACD', result.columns)

    def test_hit_returns_cached(self):
        self.cache.get('SYM001', self.df.copy())   # miss
        t0 = time.perf_counter()
        result = self.cache.get('SYM001', self.df.copy())  # hit
        t_hit = (time.perf_counter()-t0)*1000
        self.assertLess(t_hit, 1.0, "缓存命中应 <1ms")
        self.assertIn('MACD', result.columns)

    def test_stats_track_hits(self):
        self.cache.get('SYM002', self.df.copy())
        self.cache.get('SYM002', self.df.copy())
        self.assertGreaterEqual(self.cache.stats['hits'], 1)
        self.assertGreaterEqual(self.cache.stats['misses'], 1)

    def test_lru_eviction(self):
        for i in range(60):
            self.cache.get(f'SYM{i:03d}', make_df(100, seed=i))
        self.assertLessEqual(len(self.cache._cache), 50)

    def test_invalidate(self):
        self.cache.get('SYM003', self.df.copy())
        self.cache.invalidate('SYM003')
        self.assertNotIn('SYM003', self.cache._cache)


# ══════════════════════════════════════════════════════════════════════════════
# 9. 集成测试 — UnifiedWaveAnalyzer Pipeline
# ══════════════════════════════════════════════════════════════════════════════
class TestUnifiedAnalyzerPipeline(unittest.TestCase):
    """detect() 全流程集成测试"""

    def setUp(self):
        from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
        from analysis.technical.indicators import TechnicalIndicators
        self.ua = UnifiedWaveAnalyzer()
        self.ti = TechnicalIndicators()

    def test_detect_returns_list(self):
        df = make_df(300, seed=0)
        result = self.ua.detect(df, mode='all')
        self.assertIsInstance(result, list)

    def test_detect_with_precomputed_indicators(self):
        """OPT-1: 预计算指标不报错，且结果一致"""
        df = make_df(300, seed=0)
        df_ind = self.ti.calculate_all(df.copy())
        r1 = self.ua.detect(df.copy(), mode='all')
        r2 = self.ua.detect(df_ind, mode='all')
        self.assertEqual(len(r1), len(r2))

    def test_ensure_indicators_adds_columns(self):
        df = make_df(200, seed=0)
        df_out = self.ua._ensure_indicators(df.copy())
        self.assertIn('MACD', df_out.columns)
        self.assertIn('RSI14', df_out.columns)
        self.assertIn('K', df_out.columns)

    def test_ensure_indicators_skips_if_present(self):
        df_ind = self.ti.calculate_all(make_df(200, seed=0))
        df_out = self.ua._ensure_indicators(df_ind)
        self.assertIs(df_out, df_ind, "已有指标列时应直接返回同一对象")

    def test_detect_short_data_returns_empty(self):
        df = make_df(30, seed=0)
        result = self.ua.detect(df, mode='all')
        self.assertEqual(result, [])

    def test_detect_signal_structure(self):
        df = make_df(500, seed=7, slope=0.0004)
        df_ind = self.ti.calculate_all(df)
        sigs = self.ua.detect(df_ind, mode='all')
        for sig in sigs:
            self.assertIsNotNone(sig.entry_type)
            self.assertIsNotNone(sig.confidence)
            self.assertGreaterEqual(sig.confidence, 0)
            self.assertLessEqual(sig.confidence, 1.0)
            self.assertIsNotNone(sig.entry_price)
            self.assertIsNotNone(sig.target_price)
            self.assertIsNotNone(sig.stop_loss)

    def test_detect_mode_c_only(self):
        df = make_df(500, seed=0)
        df_ind = self.ti.calculate_all(df)
        sigs = self.ua.detect(df_ind, mode='C')
        for sig in sigs:
            self.assertEqual(sig.entry_type.value, 'C')

    def test_multi_timeframe_returns_list(self):
        df = make_df(400, seed=0)
        result = self.ua.detect_multi_timeframe(df)
        self.assertIsInstance(result, list)

    def test_pipeline_latency(self):
        """OPT 系列：全管线 <15ms/股"""
        df_ind = self.ti.calculate_all(make_df(300, seed=0))
        t0 = time.perf_counter()
        for _ in range(20):
            self.ua.detect(df_ind, mode='all')
        ms = (time.perf_counter()-t0)/20*1000
        self.assertLess(ms, 15.0, f"detect 耗时 {ms:.1f}ms 超过 15ms 预算")


# ══════════════════════════════════════════════════════════════════════════════
# 10. 集成测试 — 参数管理系统
# ══════════════════════════════════════════════════════════════════════════════
class TestParamManagement(unittest.TestCase):
    """wave_params.json → ConfigManager → from_config() 闭环测试"""

    def test_wave_params_loads(self):
        from utils.param_manager import get_wave_params
        params = get_wave_params()
        self.assertIsInstance(params, dict)
        self.assertIn('thresholds', params)
        self.assertIn('_meta', params)

    def test_strong_buy_threshold(self):
        from utils.param_manager import get_wave_params
        params = get_wave_params()
        self.assertEqual(params['thresholds']['strong_buy'], 0.5)

    def test_config_manager_dotpath(self):
        from utils.config_manager import config
        val = config.get('wave.scoring.rsi_weight')
        self.assertIsNotNone(val)
        self.assertEqual(val, 0.2)

    def test_config_manager_load_config_compat(self):
        from utils.config_manager import load_config
        cfg = load_config()
        self.assertIsInstance(cfg, dict)
        self.assertGreater(len(cfg), 0)

    def test_entry_optimizer_from_config(self):
        from analysis.wave.entry_optimizer import WaveEntryOptimizer
        eo = WaveEntryOptimizer.from_config()
        self.assertEqual(eo.strong_buy_threshold, 0.5)
        self.assertEqual(eo.buy_threshold, 0.4)
        self.assertGreater(eo.macd_divergence_weight, 0)

    def test_meta_performance(self):
        from utils.param_manager import get_wave_params
        params = get_wave_params()
        perf = params['_meta']['performance']
        self.assertGreater(perf['annual_return'], 0)
        self.assertGreater(perf['sharpe_ratio'], 0)
        self.assertLess(perf['max_drawdown'], 20)  # 回撤应 <20%


# ══════════════════════════════════════════════════════════════════════════════
# 11. 回归测试 — 核心逻辑不变性验证
# ══════════════════════════════════════════════════════════════════════════════
class TestRegressionWaveLogic(unittest.TestCase):
    """回归测试：关键逻辑在任何改动后保持正确"""

    def test_flat_expanded_score_regression(self):
        """Expanded Flat 是最常见形态，score 不应退化"""
        pts = [mkp(0,100), mkp(5,82), mkp(10,108), mkp(15,72)]
        from analysis.wave.elliott_wave import validate_flat
        v, _, s = validate_flat(pts)
        self.assertTrue(v)
        self.assertGreaterEqual(s, 0.70, "Expanded Flat score 不应低于 0.70")

    def test_diagonal_score_regression(self):
        """Diagonal 是 E2 新增的重要形态，score 不应退化"""
        pts = [mkp(0,100), mkp(5,116), mkp(10,107), mkp(15,119), mkp(20,111)]
        from analysis.wave.elliott_wave import validate_diagonal
        v, _, s = validate_diagonal(pts)
        self.assertTrue(v)
        self.assertGreaterEqual(s, 0.85, "Diagonal score 不应低于 0.85")

    def test_backtest_result_has_all_metrics(self):
        """BacktestResult 风险指标完整性"""
        import dataclasses
        from analysis.backtest.wave_backtester import BacktestResult
        fields = {f.name for f in dataclasses.fields(BacktestResult)}
        for required in ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
                         'max_drawdown_pct', 'profit_factor', 'win_rate']:
            self.assertIn(required, fields, f"BacktestResult 缺少 {required}")

    def test_kelly_position_sizing_regression(self):
        """Kelly 仓位参数不应被重置"""
        from analysis.backtest.wave_backtester import WaveStrategy
        ws = WaveStrategy()
        self.assertTrue(ws.use_kelly)
        self.assertEqual(ws.kelly_max_fraction, 0.25)
        self.assertTrue(ws.use_trailing_stop)

    def test_lookahead_bias_protection_regression(self):
        """前视偏差保护不应被移除"""
        src = open('analysis/wave/unified_analyzer.py').read()
        self.assertIn('iloc[:-10]', src, "前视偏差保护 df.iloc[:-10] 不应被移除")

    def test_resonance_default_weights_regression(self):
        """默认共振权重不应改变"""
        src = open('analysis/wave/resonance.py').read()
        self.assertIn("'MACD': 1.0", src)
        self.assertIn("'ElliottWave': 1.2", src)

    def test_walk_forward_parallel_regression(self):
        """OPT-6: Walk-Forward 并行逻辑不应回退"""
        src = open('analysis/optimization/param_optimizer.py').read()
        self.assertIn('_run_window', src)
        self.assertIn('as_completed', src)

    def test_signal_confidence_decay_regression(self):
        """E6: 信号置信度衰减逻辑不应回退"""
        src = open('analysis/backtest/wave_backtester.py').read()
        self.assertIn('_signal_ages', src)
        self.assertIn('0.08', src)  # 衰减率

    def test_syntax_all_files_regression(self):
        """全量语法检查：所有 .py 文件均可编译"""
        project_root = Path(__file__).parent.parent
        failed = []
        for path in project_root.rglob('*.py'):
            if any(x in str(path) for x in ['__pycache__', '.git']):
                continue
            try:
                compile(path.read_text(errors='ignore'), str(path), 'exec')
            except SyntaxError as e:
                failed.append(f"{path.name}: {e}")
        self.assertEqual(failed, [], f"语法错误:\n" + '\n'.join(failed))


# ══════════════════════════════════════════════════════════════════════════════
# 12. 性能基准测试
# ══════════════════════════════════════════════════════════════════════════════
class TestPerformanceBenchmarks(unittest.TestCase):
    """关键路径耗时基准（沙箱 2 核，生产环境应更快）"""

    def setUp(self):
        from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
        from analysis.wave.resonance import ResonanceAnalyzer
        from analysis.technical.indicators import TechnicalIndicators
        self.ua = UnifiedWaveAnalyzer()
        self.ra = ResonanceAnalyzer()
        ti = TechnicalIndicators()
        self.df_ind = ti.calculate_all(make_df(300, seed=0))

    def _avg_ms(self, fn, n=20):
        t0 = time.perf_counter()
        for _ in range(n): fn()
        return (time.perf_counter()-t0)/n*1000

    def test_resonance_precomputed_under_5ms(self):
        ms = self._avg_ms(lambda: self.ra.analyze_precomputed(self.df_ind))
        self.assertLess(ms, 5.0, f"resonance.analyze_precomputed {ms:.2f}ms > 5ms")

    def test_detect_under_15ms(self):
        ms = self._avg_ms(lambda: self.ua.detect(self.df_ind, mode='all'))
        self.assertLess(ms, 15.0, f"ua.detect {ms:.2f}ms > 15ms")

    def test_adaptive_cache_under_01ms(self):
        df = make_df(200, seed=0)
        self.ua._apply_adaptive_params(df)  # 预热
        ms = self._avg_ms(lambda: self.ua._apply_adaptive_params(df), n=200)
        self.assertLess(ms, 0.1, f"adaptive_cache hit {ms:.3f}ms > 0.1ms")


if __name__ == '__main__':
    unittest.main(verbosity=2)
