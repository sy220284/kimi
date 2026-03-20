"""Database Adapter Module"""

class DatabaseAdapter:
    """数据库适配器类"""
    
    def __init__(self, connection):
        self.connection = connection
        self.data = None
        self._data_loaded = False
    
    def _fetch_data(self):
        """从数据库获取数据"""
        # 实际的数据获取逻辑
        # 这里应该实现具体的数据库查询
        if not self._data_loaded:
            # 模拟或实际的数据获取
            self.data = self._query_db()
            self._data_loaded = True
        return self.data
    
    def _query_db(self):
        """执行数据库查询"""
        # 实际查询逻辑
        pass
    
    def get_data(self):
        """获取所有数据"""
        return self._fetch_data()
    
    def peek(self):
        """查看第一条数据但不消费
        
        Returns:
            第一条数据，如果无数据则返回None
        """
        # 修复：使用 _fetch_data() 而不是 get_data()，并正确检查 self.data
        if not self._data_loaded:
            self._fetch_data()
        
        if not self.data:
            return None
        
        return self.data[0] if len(self.data) > 0 else None
    
    def consume(self):
        """消费并返回第一条数据"""
        if not self._data_loaded:
            self._fetch_data()
        
        if not self.data:
            return None
        
        return self.data.pop(0) if len(self.data) > 0 else None
