"""
数据库适配器模块

将 DatabaseDataManager 的接口包装为简单的 peek/consume 流式访问模式。
用于需要流式处理大量数据时，避免一次性全量加载。
"""
from __future__ import annotations

from typing import Any


class DatabaseAdapter:
    """
    数据库适配器：批量查询结果的流式读取

    使用示例:
        adapter = DatabaseAdapter(pg_connector)
        adapter.load('SELECT * FROM market_data WHERE symbol=%s', ('000001',))
        while (row := adapter.consume()):
            process(row)
    """

    def __init__(self, connection: Any):
        """
        Args:
            connection: PostgresConnector 实例
        """
        self.connection = connection
        self._data: list[dict] = []
        self._loaded = False

    def load(self, query: str, params: tuple = ()) -> int:
        """
        执行查询并将结果加载到内部缓冲区

        Args:
            query:  SQL 查询语句
            params: 查询参数

        Returns:
            加载的记录数
        """
        self._data = self.connection.execute(query, params, fetch=True) or []
        self._loaded = True
        return len(self._data)

    def peek(self) -> dict | None:
        """
        查看第一条数据但不消费（不移动游标）

        Returns:
            第一条记录 dict，无数据时返回 None
        """
        if not self._loaded:
            raise RuntimeError("请先调用 load() 加载数据")
        return self._data[0] if self._data else None

    def consume(self) -> dict | None:
        """
        消费并返回第一条数据（移动游标）

        Returns:
            第一条记录 dict，无数据时返回 None
        """
        if not self._loaded:
            raise RuntimeError("请先调用 load() 加载数据")
        return self._data.pop(0) if self._data else None

    def consume_all(self) -> list[dict]:
        """一次性消费所有数据"""
        if not self._loaded:
            raise RuntimeError("请先调用 load() 加载数据")
        data, self._data = self._data, []
        return data

    def __len__(self) -> int:
        return len(self._data)

    def __bool__(self) -> bool:
        return bool(self._data)

    @property
    def remaining(self) -> int:
        """剩余未消费的记录数"""
        return len(self._data)
