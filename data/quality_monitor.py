"""
数据质量监控 - 检测异常值、缺失值、数据完整性
"""
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class DataQualityReport:
    """数据质量报告"""
    symbol: str
    total_rows: int
    missing_values: dict[str, int]
    duplicate_dates: int
    price_anomalies: list[dict[str, Any]]
    volume_anomalies: list[dict[str, Any]]
    gap_dates: list[str]
    is_valid: bool
    score: float  # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            'symbol': self.symbol,
            'total_rows': self.total_rows,
            'missing_values': self.missing_values,
            'duplicate_dates': self.duplicate_dates,
            'price_anomalies_count': len(self.price_anomalies),
            'volume_anomalies_count': len(self.volume_anomalies),
            'gap_dates_count': len(self.gap_dates),
            'is_valid': self.is_valid,
            'score': round(self.score, 2)
        }


class DataQualityMonitor:
    """数据质量监控器"""

    def __init__(
        self,
        price_change_threshold: float = 0.15,  # 15%单日涨跌幅视为异常
        volume_spike_threshold: float = 5.0,   # 5倍成交量突增
        max_missing_ratio: float = 0.05        # 最大5%缺失率
    ):
        self.price_change_threshold = price_change_threshold
        self.volume_spike_threshold = volume_spike_threshold
        self.max_missing_ratio = max_missing_ratio

    def check(self, df: pd.DataFrame, symbol: str) -> DataQualityReport:
        """
        检查数据质量

        Args:
            df: 价格数据
            symbol: 股票代码

        Returns:
            DataQualityReport
        """
        if df is None or df.empty:
            return DataQualityReport(
                symbol=symbol,
                total_rows=0,
                missing_values={},
                duplicate_dates=0,
                price_anomalies=[],
                volume_anomalies=[],
                gap_dates=[],
                is_valid=False,
                score=0.0
            )

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        total_rows = len(df)

        # 1. 检查缺失值
        missing_values = {
            col: int(df[col].isna().sum())
            for col in df.columns
        }

        # 2. 检查重复日期
        duplicate_dates = int(df['date'].duplicated().sum())

        # 3. 检查价格异常
        price_anomalies = self._check_price_anomalies(df)

        # 4. 检查成交量异常
        volume_anomalies = self._check_volume_anomalies(df)

        # 5. 检查日期缺失（交易日不连续）
        gap_dates = self._check_date_gaps(df)

        # 计算质量分数
        score = self._calculate_score(
            total_rows,
            missing_values,
            duplicate_dates,
            price_anomalies,
            volume_anomalies,
            gap_dates
        )

        # 判断是否有效
        is_valid = score >= 60 and missing_values.get('close', 0) / max(total_rows, 1) < self.max_missing_ratio

        return DataQualityReport(
            symbol=symbol,
            total_rows=total_rows,
            missing_values=missing_values,
            duplicate_dates=duplicate_dates,
            price_anomalies=price_anomalies,
            volume_anomalies=volume_anomalies,
            gap_dates=gap_dates,
            is_valid=is_valid,
            score=score
        )

    def _check_price_anomalies(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查价格异常"""
        anomalies = []

        # 计算涨跌幅
        df['price_change'] = df['close'].pct_change()
        df['high_low_ratio'] = (df['high'] - df['low']) / df['close']

        # 检查极端涨跌幅
        extreme_changes = df[
            abs(df['price_change']) > self.price_change_threshold
        ].copy()

        for _, row in extreme_changes.iterrows():
            anomalies.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'type': 'extreme_change',
                'value': round(row['price_change'] * 100, 2),
                'close': round(row['close'], 2),
                'description': f"单日涨跌幅 {row['price_change']*100:.1f}%"
            })

        # 检查高开低收异常
        invalid_ohlc = df[
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ].copy()

        for _, row in invalid_ohlc.iterrows():
            anomalies.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'type': 'invalid_ohlc',
                'value': None,
                'close': round(row['close'], 2),
                'description': "OHLC数据异常"
            })

        return anomalies[:10]  # 最多返回10条

    def _check_volume_anomalies(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查成交量异常"""
        anomalies = []

        if 'volume' not in df.columns:
            return anomalies

        # 计算平均成交量
        avg_volume = df['volume'].mean()

        # 检查成交量突增
        volume_spikes = df[
            df['volume'] > avg_volume * self.volume_spike_threshold
        ].copy()

        for _, row in volume_spikes.iterrows():
            spike_ratio = row['volume'] / avg_volume
            anomalies.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'type': 'volume_spike',
                'value': round(spike_ratio, 2),
                'close': round(row['close'], 2),
                'description': f"成交量突增 {spike_ratio:.1f}倍"
            })

        # 检查零成交量
        zero_volume = df[df['volume'] == 0].copy()
        for _, row in zero_volume.iterrows():
            anomalies.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'type': 'zero_volume',
                'value': 0,
                'close': round(row['close'], 2),
                'description': "成交量为零"
            })

        return anomalies[:10]

    def _check_date_gaps(self, df: pd.DataFrame) -> list[str]:
        """检查日期缺失"""
        gaps = []

        if len(df) < 2:
            return gaps

        # 计算日期间隔
        df['date_diff'] = df['date'].diff().dt.days

        # 正常交易日间隔（考虑周末）
        # 如果间隔 > 5天，视为有缺失
        large_gaps = df[df['date_diff'] > 5].copy()

        for _, row in large_gaps.iterrows():
            gaps.append(row['date'].strftime('%Y-%m-%d'))

        return gaps[:10]

    def _calculate_score(
        self,
        total_rows: int,
        missing_values: dict[str, int],
        duplicate_dates: int,
        price_anomalies: list,
        volume_anomalies: list,
        gap_dates: list
    ) -> float:
        """计算质量分数 (0-100)"""
        if total_rows == 0:
            return 0.0

        score = 100.0

        # 缺失值扣分
        total_missing = sum(missing_values.values())
        missing_ratio = total_missing / (total_rows * len(missing_values))
        score -= missing_ratio * 30  # 最多扣30分

        # 重复日期扣分
        duplicate_ratio = duplicate_dates / total_rows
        score -= duplicate_ratio * 20  # 最多扣20分

        # 异常值扣分
        score -= len(price_anomalies) * 2  # 每个异常扣2分
        score -= len(volume_anomalies) * 1  # 每个异常扣1分

        # 日期缺失扣分
        score -= len(gap_dates) * 1  # 每个缺失扣1分

        return max(0.0, min(100.0, score))

    def auto_fix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        自动修复数据问题

        修复项:
        1. 删除重复日期
        2. 填充缺失值（前向填充）
        3. 修复OHLC异常
        """
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # 1. 删除重复日期（保留第一条）
        df = df.drop_duplicates(subset=['date'], keep='first')

        # 2. 排序
        df = df.sort_values('date')

        # 3. 填充缺失值
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].ffill().bfill()

        # 4. 修复OHLC异常
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)

        return df
