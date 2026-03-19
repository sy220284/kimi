"""
基础工具模块 - 结构化日志系统
支持文件+控制台双输出
"""
import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def __init__(self, fmt: str | None = None, structured: bool = False):
        """
        初始化格式化器

        Args:
            fmt: 格式字符串
            structured: 是否输出JSON结构化格式
        """
        super().__init__(fmt)
        self.structured = structured

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        if self.structured:
            log_dict: dict[str, Any] = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'filename': record.filename,
                'line': record.lineno,
                'function': record.funcName,
            }

            # 添加额外字段
            if hasattr(record, 'extra_data'):
                log_dict['extra'] = record.extra_data

            # 添加异常信息
            if record.exc_info:
                log_dict['exception'] = self.formatException(record.exc_info)

            return json.dumps(log_dict, ensure_ascii=False, default=str)
        else:
            return super().format(record)


class LoggerError(Exception):
    """日志系统错误"""
    pass


class Logger(logging.Logger):
    """结构化日志系统，支持文件+控制台双输出"""

    # 日志级别映射
    LEVEL_MAP = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    # 默认格式
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

    def __init__(
        self,
        name: str,
        level: str | int = 'INFO',
        log_file: str | Path | None = None,
        max_size: str = '100MB',
        backup_count: int = 10,
        console_output: bool = True,
        file_output: bool = True,
        structured_format: bool = False,
        detailed_format: bool = False
    ):
        """
        初始化日志系统

        Args:
            name: 日志器名称
            level: 日志级别
            log_file: 日志文件路径
            max_size: 单个日志文件最大大小
            backup_count: 保留的备份文件数量
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            structured_format: 是否使用JSON结构化格式
            detailed_format: 是否使用详细格式
        """
        super().__init__(name, self._parse_level(level))
        self.structured_format = structured_format

        # 选择格式
        if structured_format:
            fmt = None
        else:
            fmt = self.DETAILED_FORMAT if detailed_format else self.DEFAULT_FORMAT

        formatter = StructuredLogFormatter(fmt, structured=structured_format)

        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.addHandler(console_handler)

        # 文件处理器
        if file_output and log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            max_bytes = self._parse_size(max_size)
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.addHandler(file_handler)

    def _parse_level(self, level: str | int) -> int:
        """解析日志级别"""
        if isinstance(level, int):
            return level
        return self.LEVEL_MAP.get(level.upper(), logging.INFO)

    def _parse_size(self, size_str: str) -> int:
        """解析文件大小字符串"""
        size_str = size_str.upper()
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
        }

        for suffix, multiplier in multipliers.items():
            if size_str.endswith(suffix):
                return int(size_str[:-len(suffix)]) * multiplier

        return int(size_str)

    def _log_with_extra(
        self,
        level: int,
        message: str,
        extra: dict[str, Any] | None = None,
        exc_info: bool | None = None
    ) -> None:
        """内部日志方法（支持extra参数）"""
        extra_attrs = {}
        if extra:
            if self.structured_format:
                extra_attrs['extra_data'] = extra
            else:
                # 非结构化格式，将额外信息附加到消息
                extra_str = ' | '.join(f'{k}={v}' for k, v in extra.items())
                message = f"{message} [{extra_str}]"

        super().log(level, message, extra=extra_attrs, exc_info=exc_info)

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """记录DEBUG级别日志"""
        if extra:
            self._log_with_extra(logging.DEBUG, message, extra)
        else:
            super().debug(message)

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """记录INFO级别日志"""
        if extra:
            self._log_with_extra(logging.INFO, message, extra)
        else:
            super().info(message)

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """记录WARNING级别日志"""
        if extra:
            self._log_with_extra(logging.WARNING, message, extra)
        else:
            super().warning(message)

    def error(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        exc_info: bool = True
    ) -> None:
        """记录ERROR级别日志"""
        if extra:
            self._log_with_extra(logging.ERROR, message, extra, exc_info=exc_info)
        else:
            super().error(message, exc_info=exc_info)

    def critical(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        exc_info: bool = True
    ) -> None:
        """记录CRITICAL级别日志"""
        if extra:
            self._log_with_extra(logging.CRITICAL, message, extra, exc_info=exc_info)
        else:
            super().critical(message, exc_info=exc_info)

    def exception(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """记录异常信息"""
        self._log_with_extra(logging.ERROR, message, extra, exc_info=True)


# 全局日志器缓存
_loggers: dict[str, Logger] = {}


def get_logger(
    name: str = 'quant_agent',
    level: str | int = 'INFO',
    log_file: str | Path | None = None,
    **kwargs
) -> Logger:
    """
    获取或创建日志器

    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径
        **kwargs: 其他Logger参数

    Returns:
        Logger实例
    """
    if name not in _loggers:
        _loggers[name] = Logger(name, level=level, log_file=log_file, **kwargs)
    return _loggers[name]


def setup_logging_from_config(config: dict[str, Any]) -> Logger:
    """
    根据配置设置日志系统

    Args:
        config: 日志配置字典

    Returns:
        配置好的Logger实例
    """
    level = config.get('level', 'INFO')
    log_file = config.get('file')
    max_size = config.get('max_size', '100MB')
    backup_count = config.get('backup_count', 10)

    return get_logger(
        name='quant_agent',
        level=level,
        log_file=log_file,
        max_size=max_size,
        backup_count=backup_count,
        console_output=True,
        file_output=bool(log_file)
    )
