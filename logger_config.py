#!/usr/bin/env python3
"""
日志配置模块
提供统一的日志记录配置
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str,
    log_dir: str = "logs",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的日志文件数量
    
    Returns:
        配置好的日志记录器
    """
    
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(name)s][%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（轮转）
    log_file = log_path / f"{name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 错误日志单独处理器
    error_log_file = log_path / f"{name}_error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        filename=error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger


def log_execution_time(logger: logging.Logger):
    """
    装饰器：记录函数执行时间
    
    Args:
        logger: 日志记录器
    """
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"{func.__name__} 执行成功，耗时: {elapsed:.2f}秒")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"{func.__name__} 执行失败，耗时: {elapsed:.2f}秒，错误: {e}")
                raise
        return wrapper
    return decorator


class JobLogger:
    """任务执行日志记录器"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.logger = setup_logger("job_execution", log_dir)
    
    def log_job_start(self, job_id: str, job_name: str, params: dict):
        """记录任务开始"""
        self.logger.info("="*50)
        self.logger.info(f"任务开始: {job_name} (ID: {job_id})")
        self.logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"任务参数: {params}")
        self.logger.info("="*50)
    
    def log_job_end(self, job_id: str, job_name: str, success: bool, elapsed: float, result: str = ""):
        """记录任务结束"""
        status = "成功" if success else "失败"
        self.logger.info("-"*50)
        self.logger.info(f"任务结束: {job_name} (ID: {job_id})")
        self.logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"执行状态: {status}")
        self.logger.info(f"执行耗时: {elapsed:.2f}秒")
        if result:
            self.logger.info(f"执行结果: {result}")
        self.logger.info("-"*50)
    
    def log_job_error(self, job_id: str, job_name: str, error: Exception):
        """记录任务错误"""
        self.logger.error(f"任务错误: {job_name} (ID: {job_id})")
        self.logger.error(f"错误信息: {str(error)}")
        self.logger.error(f"错误类型: {type(error).__name__}")


def cleanup_old_logs(log_dir: str = "logs", days: int = 30):
    """
    清理旧日志文件
    
    Args:
        log_dir: 日志目录
        days: 保留天数
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    
    import time
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    
    for log_file in log_path.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                print(f"删除旧日志文件: {log_file}")
            except Exception as e:
                print(f"删除日志文件失败 {log_file}: {e}")


if __name__ == "__main__":
    # 测试日志功能
    logger = setup_logger("test")
    logger.info("这是一条测试信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    
    # 测试任务日志
    job_logger = JobLogger()
    job_logger.log_job_start("test_job", "测试任务", {"param1": "value1"})
    job_logger.log_job_end("test_job", "测试任务", True, 1.23, "任务执行完成")