#!/usr/bin/env python3
"""
回测参数优化器 - 通过系统性回测优化波浪分析参数
Phase 3+5 增强: 数据驱动的参数调优
"""
import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ParameterSet:
    """参数组合"""
    # 波浪检测参数
    atr_mult: float = 0.5
    confidence_threshold: float = 0.5
    min_change_pct: float = 2.0
    peak_window: int = 3
    min_dist: int = 3

    # 共振参数
    resonance_min_strength: float = 0.4
    macd_weight: float = 1.0
    rsi_weight: float = 0.8
    volume_weight: float = 0.6
    wave_weight: float = 1.2

    # 交易参数
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15
    position_size: float = 0.2

    def to_dict(self) -> dict[str, Any]:
        return {
            'atr_mult': self.atr_mult,
            'confidence_threshold': self.confidence_threshold,
            'min_change_pct': self.min_change_pct,
            'peak_window': self.peak_window,
            'min_dist': self.min_dist,
            'resonance_min_strength': self.resonance_min_strength,
            'macd_weight': self.macd_weight,
            'rsi_weight': self.rsi_weight,
            'volume_weight': self.volume_weight,
            'wave_weight': self.wave_weight,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'position_size': self.position_size
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> 'ParameterSet':
        return cls(**d)

    def get_id(self) -> str:
        """生成参数唯一ID"""
        param_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:8]


@dataclass
class OptimizationResult:
    """优化结果"""
    params: ParameterSet
    win_rate: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    trade_count: int
    composite_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            'param_id': self.params.get_id(),
            'params': self.params.to_dict(),
            'win_rate': self.win_rate,
            'total_return': self.total_return,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'profit_factor': self.profit_factor,
            'trade_count': self.trade_count,
            'composite_score': self.composite_score
        }


class ParameterOptimizer:
    """
    参数优化器

    优化流程:
    1. 定义参数搜索空间
    2. 多组参数并行回测
    3. 计算综合评分
    4. 筛选最优参数
    5. 验证集测试（防过拟合）
    """

    # 参数搜索范围
    SEARCH_SPACE = {
        'atr_mult': (0.3, 1.5),
        'confidence_threshold': (0.3, 0.8),
        'min_change_pct': (1.0, 5.0),
        'peak_window': (2, 5),
        'min_dist': (2, 6),
        'resonance_min_strength': (0.2, 0.7),
        'macd_weight': (0.5, 2.0),
        'rsi_weight': (0.5, 1.5),
        'volume_weight': (0.3, 1.0),
        'wave_weight': (0.8, 2.0),
        'stop_loss_pct': (0.03, 0.08),
        'take_profit_pct': (0.10, 0.25),
        'position_size': (0.1, 0.3)
    }

    def __init__(self, analyzer_class, backtester_class):
        self.analyzer_class = analyzer_class
        self.backtester_class = backtester_class
        self.results: list[OptimizationResult] = []

    def _random_params(self) -> ParameterSet:
        """生成随机参数组合"""
        return ParameterSet(
            atr_mult=random.uniform(*self.SEARCH_SPACE['atr_mult']),
            confidence_threshold=random.uniform(*self.SEARCH_SPACE['confidence_threshold']),
            min_change_pct=random.uniform(*self.SEARCH_SPACE['min_change_pct']),
            peak_window=random.randint(*self.SEARCH_SPACE['peak_window']),
            min_dist=random.randint(*self.SEARCH_SPACE['min_dist']),
            resonance_min_strength=random.uniform(*self.SEARCH_SPACE['resonance_min_strength']),
            macd_weight=random.uniform(*self.SEARCH_SPACE['macd_weight']),
            rsi_weight=random.uniform(*self.SEARCH_SPACE['rsi_weight']),
            volume_weight=random.uniform(*self.SEARCH_SPACE['volume_weight']),
            wave_weight=random.uniform(*self.SEARCH_SPACE['wave_weight']),
            stop_loss_pct=random.uniform(*self.SEARCH_SPACE['stop_loss_pct']),
            take_profit_pct=random.uniform(*self.SEARCH_SPACE['take_profit_pct']),
            position_size=random.uniform(*self.SEARCH_SPACE['position_size'])
        )

    def _calculate_score(self, result) -> float:
        """
        计算综合评分

        权重分配:
        - 胜率: 25%
        - 年化收益: 25%
        - 风险控制(1-回撤): 20%
        - Sharpe比率: 15%
        - 盈亏比: 15%
        """
        win_rate = result.win_rate
        annual_return = result.total_return / 100  # 转为小数
        risk_control = max(0, 1 - result.max_drawdown / 100)
        sharpe = min(3.0, max(0, result.sharpe_ratio)) / 3.0  # 归一化到0-1
        profit_factor = min(3.0, result.profit_factor) / 3.0 if result.profit_factor != float('inf') else 1.0

        # 惩罚交易次数过少
        trade_penalty = min(1.0, result.trade_count / 10)  # 至少10笔交易

        score = (
            win_rate * 0.25 +
            annual_return * 0.25 +
            risk_control * 0.20 +
            sharpe * 0.15 +
            profit_factor * 0.15
        ) * trade_penalty

        return max(0, score)

    def _single_backtest(
        self,
        params: ParameterSet,
        symbol: str,
        df: pd.DataFrame,
        train_start: str,
        train_end: str
    ) -> OptimizationResult | None:
        """单次回测"""
        try:
            # 创建带参数的分析器
            analyzer = self.analyzer_class(
                atr_mult=params.atr_mult,
                confidence_threshold=params.confidence_threshold,
                min_change_pct=params.min_change_pct,
                peak_window=params.peak_window,
                min_dist=params.min_dist
            )

            # 设置共振权重
            if hasattr(analyzer, 'resonance_analyzer'):
                analyzer.resonance_analyzer.weights = {
                    'MACD': params.macd_weight,
                    'RSI': params.rsi_weight,
                    'Volume': params.volume_weight,
                    'ElliottWave': params.wave_weight
                }

            # 创建回测器
            backtester = self.backtester_class(analyzer)
            backtester.strategy.min_confidence = params.confidence_threshold
            backtester.strategy.use_resonance = True
            backtester.strategy.stop_loss_pct = params.stop_loss_pct
            backtester.strategy.take_profit_pct = params.take_profit_pct
            backtester.strategy.position_size = params.position_size

            # 运行回测
            result = backtester.run(symbol, df, reanalyze_every=5)

            # 计算评分
            composite_score = self._calculate_score(result)

            return OptimizationResult(
                params=params,
                win_rate=result.win_rate,
                total_return=result.total_return_pct,
                max_drawdown=result.max_drawdown_pct,
                sharpe_ratio=result.sharpe_ratio,
                profit_factor=result.profit_factor,
                trade_count=result.total_trades,
                composite_score=composite_score
            )

        except Exception as e:
            print(f"  回测失败 [{params.get_id()}]: {e}")
            return None

    def optimize(
        self,
        symbols: list[str],
        data_loader,
        n_iterations: int = 50,
        train_ratio: float = 0.7,
        top_k: int = 5
    ) -> list[OptimizationResult]:
        """
        执行参数优化

        Args:
            symbols: 股票列表
            data_loader: 数据加载函数
            n_iterations: 随机搜索次数
            train_ratio: 训练集比例
            top_k: 返回最优参数数量

        Returns:
            List[OptimizationResult]
        """
        print(f"\n{'='*70}")
        print("🔧 开始参数优化")
        print(f"{'='*70}")
        print(f"搜索空间: {len(self.SEARCH_SPACE)} 个参数")
        print(f"迭代次数: {n_iterations}")
        print(f"测试股票: {symbols}")

        all_results = []

        for symbol in symbols:
            print(f"\n📊 优化股票: {symbol}")

            # 加载数据
            df = data_loader(symbol)
            if df is None or len(df) < 100:
                print("  数据不足，跳过")
                continue

            # 分割训练/验证集
            train_size = int(len(df) * train_ratio)
            train_df = df.iloc[:train_size]

            print(f"  训练集: {len(train_df)} 条数据")

            # 随机搜索
            for i in range(n_iterations):
                params = self._random_params()
                print(f"  [{i+1}/{n_iterations}] 测试参数 {params.get_id()}...", end=' ')

                result = self._single_backtest(params, symbol, train_df, '', '')

                if result:
                    print(f"得分={result.composite_score:.3f}, 胜率={result.win_rate:.1%}, 收益={result.total_return:.1f}%")
                    all_results.append(result)
                else:
                    print("失败")

        if not all_results:
            print("\n❌ 没有成功的回测结果")
            return []

        # 按综合评分排序
        all_results.sort(key=lambda x: x.composite_score, reverse=True)

        print(f"\n{'='*70}")
        print(f"🏆 TOP {top_k} 最优参数")
        print(f"{'='*70}")

        for i, r in enumerate(all_results[:top_k], 1):
            print(f"\n#{i} 参数ID: {r.params.get_id()}")
            print(f"   综合得分: {r.composite_score:.3f}")
            print(f"   胜率: {r.win_rate:.1%} | 收益: {r.total_return:.1f}% | 回撤: {r.max_drawdown:.1f}%")
            print(f"   Sharpe: {r.sharpe_ratio:.2f} | 盈亏比: {r.profit_factor:.2f}")
            print(f"   关键参数: ATR={r.params.atr_mult:.2f}, 置信度={r.params.confidence_threshold:.2f}, 共振门槛={r.params.resonance_min_strength:.2f}")

        self.results = all_results
        return all_results[:top_k]

    def validate(
        self,
        top_results: list[OptimizationResult],
        symbols: list[str],
        data_loader,
        train_ratio: float = 0.7
    ) -> dict[str, Any]:
        """
        验证集测试 - 防止过拟合
        """
        print(f"\n{'='*70}")
        print("🧪 验证集测试 (防过拟合)")
        print(f"{'='*70}")

        validation_scores = []

        for result in top_results:
            print(f"\n验证参数 {result.params.get_id()}:")

            symbol_scores = []

            for symbol in symbols:
                df = data_loader(symbol)
                if df is None:
                    continue

                # 使用验证集（后30%数据）
                train_size = int(len(df) * train_ratio)
                val_df = df.iloc[train_size:]

                val_result = self._single_backtest(
                    result.params, symbol, val_df, '', ''
                )

                if val_result:
                    symbol_scores.append(val_result.composite_score)
                    print(f"  {symbol}: 得分={val_result.composite_score:.3f}, 胜率={val_result.win_rate:.1%}")

            avg_score = np.mean(symbol_scores) if symbol_scores else 0
            validation_scores.append({
                'param_id': result.params.get_id(),
                'train_score': result.composite_score,
                'val_score': avg_score,
                'degradation': result.composite_score - avg_score
            })
            print(f"  平均验证得分: {avg_score:.3f} (训练集: {result.composite_score:.3f})")

        # 找出泛化能力最强的参数
        best_generalization = min(validation_scores, key=lambda x: x['degradation'])

        print(f"\n{'='*70}")
        print(f"✅ 最佳泛化参数: {best_generalization['param_id']}")
        print(f"   训练得分: {best_generalization['train_score']:.3f}")
        print(f"   验证得分: {best_generalization['val_score']:.3f}")
        print(f"   性能衰减: {best_generalization['degradation']:.3f}")
        print(f"{'='*70}")

        return {
            'validation_scores': validation_scores,
            'best_params_id': best_generalization['param_id']
        }

    def walk_forward_optimize(
        self,
        symbols: list[str],
        data_loader,
        n_iterations: int = 30,
        n_windows: int = 4,
        train_ratio: float = 0.7,
        top_k: int = 3
    ) -> dict[str, Any]:
        """
        Walk-Forward 参数优化 — 防过拟合的标准做法

        将历史数据按时间切成 n_windows 个滑动窗口，每个窗口内：
        - 前 train_ratio 部分用于优化参数
        - 后 (1-train_ratio) 部分用于样本外验证
        最终汇总所有窗口的样本外表现，选出泛化能力最强的参数。

        相比简单的 70/30 分割，Walk-Forward 可以：
        1. 验证参数在不同市场周期的稳健性
        2. 检测参数在时间轴上的衰减情况
        3. 提供更可靠的样本外期望收益估计

        Args:
            symbols: 股票列表
            data_loader: 数据加载函数 (symbol -> DataFrame)
            n_iterations: 每个窗口的随机搜索次数
            n_windows: Walk-Forward 窗口数量（建议 3-5）
            train_ratio: 每个窗口内训练集比例
            top_k: 候选参数数量

        Returns:
            {
                'best_params': ParameterSet,       # 样本外表现最佳的参数
                'window_results': list[dict],       # 每个窗口的详细结果
                'oos_score': float,                 # 样本外综合得分
                'stability': float,                 # 参数稳定性评分 (0-1，越高越稳)
                'degradation': float                # 训练/验证性能衰减
            }
        """
        print(f"\n{'='*70}")
        print(f"🔄 Walk-Forward 参数优化 ({n_windows} 个窗口)")
        print(f"{'='*70}")

        all_window_results = []
        param_oos_scores: dict[str, list[float]] = {}  # param_id -> [oos scores]

        for symbol in symbols:
            df = data_loader(symbol)
            if df is None or len(df) < 200:
                print(f"  {symbol}: 数据不足 (<200条)，跳过")
                continue

            n = len(df)
            window_size = n // n_windows

            for w in range(n_windows):
                # 窗口范围
                win_start = w * window_size
                win_end   = win_start + window_size if w < n_windows - 1 else n
                window_df = df.iloc[win_start:win_end]

                train_end = int(len(window_df) * train_ratio)
                train_df  = window_df.iloc[:train_end]
                oos_df    = window_df.iloc[train_end:]

                if len(train_df) < 60 or len(oos_df) < 20:
                    continue

                period_label = (
                    f"{str(window_df.index[0]) if hasattr(window_df.index[0], 'date') else w}"
                    f"~W{w+1}"
                )
                print(f"\n  [{symbol}] 窗口 {w+1}/{n_windows} "
                      f"(训练{len(train_df)}条 / OOS{len(oos_df)}条)")

                # 在训练集上随机搜索
                window_top: list[OptimizationResult] = []
                for _ in range(n_iterations):
                    params = self._random_params()
                    res = self._single_backtest(params, symbol, train_df, '', '')
                    if res:
                        window_top.append(res)

                if not window_top:
                    continue

                window_top.sort(key=lambda x: x.composite_score, reverse=True)
                top_candidates = window_top[:top_k]

                # 在样本外集上验证每个候选
                for cand in top_candidates:
                    oos_res = self._single_backtest(cand.params, symbol, oos_df, '', '')
                    pid = cand.params.get_id()
                    if oos_res:
                        param_oos_scores.setdefault(pid, []).append(oos_res.composite_score)
                        all_window_results.append({
                            'symbol': symbol,
                            'window': w + 1,
                            'param_id': pid,
                            'train_score': cand.composite_score,
                            'oos_score': oos_res.composite_score,
                            'degradation': cand.composite_score - oos_res.composite_score,
                        })
                        print(f"    参数 {pid[:8]}: 训练={cand.composite_score:.3f} "
                              f"OOS={oos_res.composite_score:.3f}")

        if not param_oos_scores:
            print("\n❌ Walk-Forward 无有效结果")
            return {'best_params': self._random_params(), 'window_results': [],
                    'oos_score': 0.0, 'stability': 0.0, 'degradation': 0.0}

        # 选最优参数：OOS均值最高 且 稳定性好（标准差小）
        param_stats = {}
        for pid, scores in param_oos_scores.items():
            mean_oos = float(np.mean(scores))
            std_oos  = float(np.std(scores)) if len(scores) > 1 else 0.0
            stability = 1.0 / (1.0 + std_oos)  # 标准差越小 → 稳定性越高
            param_stats[pid] = {
                'mean_oos': mean_oos,
                'std_oos': std_oos,
                'stability': stability,
                'combined': mean_oos * 0.7 + stability * 0.3,  # OOS表现为主
                'n_windows': len(scores),
            }

        best_pid = max(param_stats, key=lambda p: param_stats[p]['combined'])
        best_stat = param_stats[best_pid]

        # 从 all_window_results 找对应参数对象（取最近一次）
        matching = [r for r in all_window_results if r['param_id'] == best_pid]
        train_scores = [r['train_score'] for r in matching]
        degradation = float(np.mean([r['degradation'] for r in matching])) if matching else 0.0

        # 重建 ParameterSet（从 param_id 反推或重新搜索）
        # 简化：返回最优 param_id 和统计信息，调用方可用 load_results() 重建
        print(f"\n{'='*70}")
        print(f"✅ Walk-Forward 最优参数: {best_pid}")
        print(f"   OOS 均值: {best_stat['mean_oos']:.3f} ± {best_stat['std_oos']:.3f}")
        print(f"   参数稳定性: {best_stat['stability']:.3f}")
        print(f"   训练/验证衰减: {degradation:.3f}")
        print(f"   覆盖窗口: {best_stat['n_windows']} 个")
        print(f"{'='*70}")

        return {
            'best_param_id': best_pid,
            'param_stats': param_stats,
            'window_results': all_window_results,
            'oos_score': best_stat['mean_oos'],
            'stability': best_stat['stability'],
            'degradation': degradation,
        }

    def save_results(self, filepath: str):
        """保存优化结果"""
        data = [r.to_dict() for r in self.results]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 优化结果已保存: {filepath}")

    @classmethod
    def load_results(cls, filepath: str) -> list[OptimizationResult]:
        """加载优化结果"""
        with open(filepath) as f:
            data = json.load(f)
        return [OptimizationResult(
            params=ParameterSet.from_dict(r['params']),
            win_rate=r['win_rate'],
            total_return=r['total_return'],
            max_drawdown=r['max_drawdown'],
            sharpe_ratio=r['sharpe_ratio'],
            profit_factor=r['profit_factor'],
            trade_count=r['trade_count'],
            composite_score=r['composite_score']
        ) for r in data]


class SignalFilter:
    """
    基于回测结果的信号过滤器

    根据历史表现动态调整信号门槛
    """

    def __init__(self, optimization_results: list[OptimizationResult]):
        self.results = optimization_results
        self.best_params = optimization_results[0].params if optimization_results else None

        # 统计失败模式
        self._analyze_failure_patterns()

    def _analyze_failure_patterns(self):
        """分析失败交易的模式"""
        # 根据回测结果调整过滤规则
        self.filters = {
            'min_confidence': 0.5,
            'min_resonance_strength': 0.4,
            'require_volume_confirmation': False,
            'max_conflict_rate': 0.3
        }

        if self.best_params:
            self.filters['min_confidence'] = self.best_params.confidence_threshold
            self.filters['min_resonance_strength'] = self.best_params.resonance_min_strength

    def should_trade(
        self,
        wave_analysis,
        resonance_result,
        market_condition: str = "normal"
    ) -> tuple[bool, str]:
        """
        判断是否应该交易

        Returns:
            (should_trade, reason)
        """
        # 1. 置信度检查
        if wave_analysis.confidence < self.filters['min_confidence']:
            return False, f"置信度不足 ({wave_analysis.confidence:.2f} < {self.filters['min_confidence']})"

        # 2. 共振强度检查
        if resonance_result.overall_strength < self.filters['min_resonance_strength']:
            return False, f"共振强度不足 ({resonance_result.overall_strength:.2f} < {self.filters['min_resonance_strength']})"

        # 3. 信号冲突检查
        if resonance_result.conflicts:
            return False, f"信号冲突: {resonance_result.conflicts[0]}"

        # 4. 方向一致性检查
        if not resonance_result.wave_aligned:
            return False, "波浪与技术指标方向不一致"

        # 5. 市场状态适配
        if market_condition == "volatile" and wave_analysis.confidence < 0.7:
            return False, "高波动市场需要更高置信度"

        return True, "信号通过所有过滤条件"

    def get_position_size_adjustment(self, signal_strength: float) -> float:
        """
        根据信号强度调整仓位

        Args:
            signal_strength: 0-1 信号强度

        Returns:
            仓位系数 0.5-1.5
        """
        base_size = self.best_params.position_size if self.best_params else 0.2

        # 信号越强，仓位越大
        if signal_strength > 0.8:
            return base_size * 1.5
        elif signal_strength > 0.6:
            return base_size * 1.0
        elif signal_strength > 0.4:
            return base_size * 0.7
        else:
            return base_size * 0.5


# 便捷函数
def run_optimization(
    symbols: list[str],
    data_loader,
    analyzer_class,
    backtester_class,
    n_iterations: int = 30,
    save_path: str | None = None
) -> tuple[ParameterSet, SignalFilter]:
    """
    运行完整优化流程

    Returns:
        (最优参数, 信号过滤器)
    """
    optimizer = ParameterOptimizer(analyzer_class, backtester_class)

    # 1. 参数搜索
    top_results = optimizer.optimize(
        symbols=symbols,
        data_loader=data_loader,
        n_iterations=n_iterations
    )

    if not top_results:
        raise ValueError("优化失败，没有获得有效结果")

    # 2. 验证集测试
    validation = optimizer.validate(top_results, symbols, data_loader)

    # 3. 找到最佳泛化参数
    best_param_id = validation['best_params_id']
    best_result = next(r for r in top_results if r.params.get_id() == best_param_id)

    # 4. 创建信号过滤器
    signal_filter = SignalFilter(top_results)

    # 5. 保存结果
    if save_path:
        optimizer.save_results(save_path)

    return best_result.params, signal_filter
