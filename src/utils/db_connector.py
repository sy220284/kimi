"""
基础工具模块 - 数据库连接池封装
支持PostgreSQL、Redis、MongoDB
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
import json

# PostgreSQL
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

# Redis
try:
    from redis import Redis, ConnectionPool as RedisConnectionPool
except ImportError:
    Redis = None
    RedisConnectionPool = None

# MongoDB (可选依赖)
try:
    from pymongo import MongoClient
    from pymongo.database import Database
    from pymongo.collection import Collection
except ImportError:
    MongoClient = None
    Database = None
    Collection = None


class DatabaseError(Exception):
    """数据库错误基类"""
    pass


class ConnectionError(DatabaseError):
    """连接错误"""
    pass


class QueryError(DatabaseError):
    """查询错误"""
    pass


class DatabaseConnector(ABC):
    """数据库连接器抽象基类"""
    
    @abstractmethod
    def connect(self) -> None:
        """建立连接"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass


class PostgresConnector(DatabaseConnector):
    """PostgreSQL连接器"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5432,
        database: str = 'quant_analysis',
        username: str = '',
        password: str = '',
        pool_size: int = 10,
        **kwargs
    ):
        """
        初始化PostgreSQL连接器
        
        Args:
            host: 主机地址
            port: 端口
            database: 数据库名
            username: 用户名
            password: 密码
            pool_size: 连接池大小
        """
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.pool_size = pool_size
        self._pool: Optional[ThreadedConnectionPool] = None
    
    def connect(self) -> None:
        """建立连接池"""
        try:
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=self.pool_size,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password
            )
        except Exception as e:
            raise ConnectionError(f"PostgreSQL连接失败: {e}")
    
    def disconnect(self) -> None:
        """关闭连接池"""
        if self._pool:
            self._pool.closeall()
            self._pool = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._pool is not None
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception:
            return False
    
    @contextmanager
    def get_connection(self):
        """
        获取连接上下文管理器
        
        Yields:
            数据库连接
        """
        if not self._pool:
            self.connect()
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise QueryError(f"数据库操作失败: {e}")
        finally:
            if conn and self._pool:
                self._pool.putconn(conn)
    
    def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        执行SQL查询
        
        Args:
            query: SQL语句
            params: 查询参数
            fetch: 是否获取结果
            
        Returns:
            查询结果（如果fetch=True）
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return [dict(row) for row in cur.fetchall()]
                return None
    
    def execute_many(
        self,
        query: str,
        params_list: List[tuple]
    ) -> int:
        """
        批量执行SQL
        
        Args:
            query: SQL语句
            params_list: 参数列表
            
        Returns:
            影响的行数
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
                return cur.rowcount
    
    def insert_market_data(
        self,
        symbol: str,
        date: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: int,
        amount: float,
        source: str = ''
    ) -> None:
        """
        插入行情数据
        
        Args:
            symbol: 股票代码
            date: 日期
            open_price: 开盘价
            high: 最高价
            low: 最低价
            close: 收盘价
            volume: 成交量
            amount: 成交额
            source: 数据源
        """
        query = """
            INSERT INTO market_data 
            (symbol, date, open, high, low, close, volume, amount, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount,
                data_source = EXCLUDED.data_source
        """
        self.execute(query, (symbol, date, open_price, high, low, close, volume, amount, source))
    
    def get_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取行情数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            行情数据列表
        """
        query = """
            SELECT * FROM market_data 
            WHERE symbol = %s AND date BETWEEN %s AND %s
            ORDER BY date
        """
        return self.execute(query, (symbol, start_date, end_date), fetch=True) or []
    
    def insert_analysis_result(
        self,
        analyst_type: str,
        symbol: Optional[str],
        analysis_date: str,
        result: Dict[str, Any],
        confidence: float
    ) -> None:
        """
        插入分析结果
        
        Args:
            analyst_type: 分析师类型
            symbol: 股票代码
            analysis_date: 分析日期
            result: 分析结果JSON
            confidence: 置信度
        """
        query = """
            INSERT INTO analysis_results 
            (analyst_type, symbol, analysis_date, result_json, confidence_score)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (analyst_type, symbol, analysis_date) DO UPDATE SET
                result_json = EXCLUDED.result_json,
                confidence_score = EXCLUDED.confidence_score,
                created_at = CURRENT_TIMESTAMP
        """
        self.execute(query, (analyst_type, symbol, analysis_date, json.dumps(result), confidence))


class RedisConnector(DatabaseConnector):
    """Redis连接器"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
        **kwargs
    ):
        """
        初始化Redis连接器
        
        Args:
            host: 主机地址
            port: 端口
            db: 数据库编号
            password: 密码
            max_connections: 最大连接数
        """
        if Redis is None:
            raise ImportError("redis not installed. Run: pip install redis")
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password or None
        self.max_connections = max_connections
        self._pool: Optional[RedisConnectionPool] = None
        self._redis: Optional[Redis] = None
    
    def connect(self) -> None:
        """建立连接"""
        try:
            self._pool = RedisConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections
            )
            self._redis = Redis(connection_pool=self._pool)
        except Exception as e:
            raise ConnectionError(f"Redis连接失败: {e}")
    
    def disconnect(self) -> None:
        """断开连接"""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            self._redis = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._redis is not None
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            if self._redis:
                self._redis.ping()
                return True
            return False
        except Exception:
            return False
    
    @property
    def client(self) -> Redis:
        """获取Redis客户端"""
        if not self._redis:
            self.connect()
        return self._redis
    
    def set_cache(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒）
            
        Returns:
            是否设置成功
        """
        try:
            # 处理日期序列化
            def json_serializer(obj):
                if hasattr(obj, 'isoformat'):  # date/datetime
                    return obj.isoformat()
                if hasattr(obj, '__float__'):  # Decimal
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            serialized = json.dumps(value, default=json_serializer)
            return self.client.set(key, serialized, ex=expire)
        except Exception as e:
            raise DatabaseError(f"缓存设置失败: {e}")
    
    def get_cache(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或None
        """
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            raise DatabaseError(f"缓存获取失败: {e}")
    
    def delete_cache(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        return bool(self.client.delete(key))
    
    def set_market_data_cache(
        self,
        symbol: str,
        data: List[Dict[str, Any]],
        expire: int = 3600
    ) -> None:
        """
        设置行情数据缓存
        
        Args:
            symbol: 股票代码
            data: 行情数据
            expire: 过期时间（秒）
        """
        key = f"market_data:{symbol}"
        self.set_cache(key, data, expire)
    
    def get_market_data_cache(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取行情数据缓存
        
        Args:
            symbol: 股票代码
            
        Returns:
            行情数据或None
        """
        key = f"market_data:{symbol}"
        return self.get_cache(key)


class MongoDBConnector(DatabaseConnector):
    """MongoDB连接器"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 27017,
        database: str = 'quant_data',
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ):
        """
        初始化MongoDB连接器
        
        Args:
            host: 主机地址
            port: 端口
            database: 数据库名
            username: 用户名
            password: 密码
        """
        if MongoClient is None:
            raise ImportError("pymongo not installed. Run: pip install pymongo")
        
        self.host = host
        self.port = port
        self.database_name = database
        self.username = username
        self.password = password
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
    
    def connect(self) -> None:
        """建立连接"""
        try:
            if self.username and self.password:
                uri = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database_name}"
                self._client = MongoClient(uri)
            else:
                self._client = MongoClient(self.host, self.port)
            
            self._db = self._client[self.database_name]
        except Exception as e:
            raise ConnectionError(f"MongoDB连接失败: {e}")
    
    def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._client is not None
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            if self._client:
                self._client.admin.command('ping')
                return True
            return False
        except Exception:
            return False
    
    @property
    def db(self) -> Database:
        """获取数据库对象"""
        if not self._db:
            self.connect()
        return self._db
    
    def get_collection(self, name: str) -> Collection:
        """
        获取集合
        
        Args:
            name: 集合名称
            
        Returns:
            集合对象
        """
        return self.db[name]
    
    def insert_document(
        self,
        collection: str,
        document: Dict[str, Any]
    ) -> str:
        """
        插入文档
        
        Args:
            collection: 集合名称
            document: 文档
            
        Returns:
            插入的文档ID
        """
        try:
            result = self.get_collection(collection).insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            raise DatabaseError(f"文档插入失败: {e}")
    
    def insert_documents(
        self,
        collection: str,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量插入文档
        
        Args:
            collection: 集合名称
            documents: 文档列表
            
        Returns:
            插入的文档ID列表
        """
        try:
            result = self.get_collection(collection).insert_many(documents)
            return [str(id) for id in result.inserted_ids]
        except Exception as e:
            raise DatabaseError(f"批量插入失败: {e}")
    
    def find_documents(
        self,
        collection: str,
        query: Dict[str, Any],
        limit: Optional[int] = None,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """
        查询文档
        
        Args:
            collection: 集合名称
            query: 查询条件
            limit: 限制数量
            sort: 排序规则
            
        Returns:
            文档列表
        """
        try:
            cursor = self.get_collection(collection).find(query)
            
            if sort:
                cursor = cursor.sort(sort)
            if limit:
                cursor = cursor.limit(limit)
            
            return list(cursor)
        except Exception as e:
            raise DatabaseError(f"文档查询失败: {e}")


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self._connectors: Dict[str, DatabaseConnector] = {}
    
    def register_connector(
        self,
        name: str,
        connector: DatabaseConnector
    ) -> None:
        """
        注册连接器
        
        Args:
            name: 连接器名称
            connector: 连接器实例
        """
        self._connectors[name] = connector
    
    def get_connector(self, name: str) -> Optional[DatabaseConnector]:
        """
        获取连接器
        
        Args:
            name: 连接器名称
            
        Returns:
            连接器实例或None
        """
        return self._connectors.get(name)
    
    def connect_all(self) -> None:
        """连接所有数据库"""
        for name, connector in self._connectors.items():
            try:
                connector.connect()
            except Exception as e:
                raise ConnectionError(f"连接 {name} 失败: {e}")
    
    def disconnect_all(self) -> None:
        """断开所有数据库连接"""
        for connector in self._connectors.values():
            try:
                connector.disconnect()
            except Exception:
                pass
    
    def health_check_all(self) -> Dict[str, bool]:
        """检查所有数据库健康状态"""
        return {
            name: connector.health_check()
            for name, connector in self._connectors.items()
        }


# 全局数据库管理器
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
