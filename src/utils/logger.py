import os
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QThread
from PyQt6.QtWidgets import QApplication
from typing import Optional
from src.utils.app_path import get_app_name, get_logs_dir

# 自定义日志格式化器，将日志级别翻译成中文
class ChineseLogFormatter(logging.Formatter):
    """自定义日志格式化器，将日志级别翻译成中文"""
    
    # 日志级别中英文映射
    LEVEL_MAP = {
        'DEBUG': '调试',
        'INFO': '信息',
        'WARNING': '警告',
        'ERROR': '错误',
        'CRITICAL': '严重错误',
    }
    
    def format(self, record):
        # 替换记录中的levelname为中文
        if record.levelname in self.LEVEL_MAP:
            record.levelname = self.LEVEL_MAP[record.levelname]
        return super().format(record)

class LogSignals(QObject):
    """日志信号类，用于将日志消息发送到UI"""
    log_message = pyqtSignal(str)

class Logger:
    """日志管理器单例类"""
    _instance: Optional['Logger'] = None
    _initialized = False
    _lock = threading.RLock()  # 增加线程锁
    
    @classmethod
    def instance(cls) -> 'Logger':
        """获取Logger单例实例，线程安全"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """初始化Logger，只在第一次调用时执行"""
        with Logger._lock:
            if Logger._initialized:
                return
            
            self.logger = logging.getLogger(get_app_name())
            self.logger.setLevel(logging.DEBUG)
            # 避免日志重复输出
            self.logger.propagate = False
            
            # 检查是否已有处理器
            if not self.logger.handlers:
                # 使用自定义格式化器，将级别翻译成中文
                self.formatter = ChineseLogFormatter('[%(asctime)s] [%(levelname)s] %(message)s')
                
                # 控制台日志处理器
                self.console_handler = logging.StreamHandler()
                self.console_handler.setFormatter(self.formatter)
                self.console_handler.setLevel(logging.INFO)
                self.logger.addHandler(self.console_handler)
            
            # 信号对象，用于与UI交互
            self.signals = LogSignals()
            
            # 文件日志处理器 - 延迟初始化
            self.file_handler = None
            
            # 主线程ID，用于区分是否从其他线程调用
            self.main_thread_id = threading.current_thread().ident
            
            # 标记为已初始化
            Logger._initialized = True
    
    def _init_file_handler(self):
        """初始化文件日志处理器 - 延迟加载，线程安全"""
        with Logger._lock:
            if self.file_handler is not None:
                return
                
            try:
                # 获取日志目录
                log_dir = get_logs_dir()
                    
                # 每天一个日志文件
                log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
                
                # 创建文件处理器
                self.file_handler = RotatingFileHandler(
                    log_file, 
                    maxBytes=10*1024*1024,  # 10MB
                    backupCount=5
                )
                self.file_handler.setFormatter(self.formatter)
                self.file_handler.setLevel(logging.DEBUG)
                self.logger.addHandler(self.file_handler)
            except Exception as e:
                print(f"初始化文件日志处理器失败: {str(e)}")
    
    def debug(self, message):
        """记录调试级别日志"""
        self._init_file_handler()  # 确保文件处理器已初始化
        self.logger.debug(message)
        self._emit_to_ui(message, logging.DEBUG)
    
    def info(self, message):
        """记录信息级别日志"""
        self._init_file_handler()  # 确保文件处理器已初始化
        self.logger.info(message)
        self._emit_to_ui(message, logging.INFO)
    
    def warning(self, message):
        """记录警告级别日志"""
        self._init_file_handler()  # 确保文件处理器已初始化
        self.logger.warning(message)
        self._emit_to_ui(message, logging.WARNING)
    
    def error(self, message):
        """记录错误级别日志"""
        self._init_file_handler()  # 确保文件处理器已初始化
        self.logger.error(message)
        self._emit_to_ui(message, logging.ERROR)
    
    def critical(self, message):
        """记录严重错误级别日志"""
        self._init_file_handler()  # 确保文件处理器已初始化
        self.logger.critical(message)
        self._emit_to_ui(message, logging.CRITICAL)
        
    def _emit_to_ui(self, message, level):
        """向UI发送日志信号，线程安全"""
        try:
            # 通过信号发送到UI
            if level >= logging.INFO:  # 只有INFO及以上级别才发送到UI
                # 获取当前时间和对应的中文级别
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                level_name = ChineseLogFormatter.LEVEL_MAP.get(
                    logging.getLevelName(level), logging.getLevelName(level)
                )
                # 格式化消息
                formatted_msg = f"[{timestamp}] [{level_name}] {message}"
                # 发送到UI
                self.signals.log_message.emit(formatted_msg)
        except Exception as e:
            print(f"发送日志到UI失败: {str(e)}")


# 便捷函数，用于快速访问日志功能
def get_logger() -> Logger:
    """获取Logger实例的便捷方法"""
    return Logger.instance()


# 日志级别快捷函数
def debug(message):
    get_logger().debug(message)

def info(message):
    get_logger().info(message)
    
def warning(message):
    get_logger().warning(message)
    
def error(message):
    get_logger().error(message)
    
def critical(message):
    get_logger().critical(message) 