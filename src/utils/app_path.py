import os
from typing import Optional, Dict
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# 缓存应用名称和基础路径，避免重复获取
_app_name = None
_user_dir = None
_app_dir = None

def get_app_name() -> str:
    """获取应用名称
    
    Returns:
        str: 应用名称
    """
    global _app_name
    if _app_name is None:
        _app_name = QApplication.instance().applicationName()
    return _app_name

def get_user_dir() -> str:
    """获取用户主目录路径
    
    Returns:
        str: 用户主目录的绝对路径
    """
    global _user_dir
    if _user_dir is None:
        _user_dir = os.path.expanduser("~")
    return _user_dir

def get_app_dir() -> str:
    """获取应用主目录路径，如果不存在则创建
    
    Returns:
        str: 应用主目录的绝对路径
    """
    global _app_dir
    if _app_dir is None:
        _app_dir = os.path.join(get_user_dir(), get_app_name())
        ensure_dir_exists(_app_dir)
    return _app_dir

def ensure_dir_exists(path: str) -> None:
    """确保目录存在，如果不存在则创建
    
    Args:
        path: 需要确保存在的目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path)

def get_logs_dir() -> str:
    """获取日志目录路径，如果不存在则创建
    
    Returns:
        str: 日志目录的绝对路径
    """
    logs_dir = os.path.join(get_app_dir(), "logs")
    ensure_dir_exists(logs_dir)
    return logs_dir

def get_config_dir() -> str:
    """获取配置文件目录路径，如果不存在则创建
    
    Returns:
        str: 配置目录的绝对路径
    """
    config_dir = os.path.join(get_app_dir(), "config")
    ensure_dir_exists(config_dir)
    return config_dir

def get_db_dir() -> str:
    """获取数据库目录路径，如果不存在则创建
    
    Returns:
        str: 数据库目录的绝对路径
    """
    db_dir = os.path.join(get_app_dir(), "db")
    ensure_dir_exists(db_dir)
    return db_dir

def get_db_path(db_name: str) -> str:
    """获取数据库文件的完整路径
    
    Args:
        db_name: 数据库文件名
        
    Returns:
        str: 数据库文件的绝对路径
    """
    db_dir = get_db_dir()
    return os.path.join(db_dir, f"{db_name}.db")

def get_cache_dir() -> str:
    """获取缓存目录路径，如果不存在则创建
    
    Returns:
        str: 缓存目录的绝对路径
    """
    cache_dir = os.path.join(get_app_dir(), "cache")
    ensure_dir_exists(cache_dir)
    return cache_dir

def get_config_file_path(filename: str = "settings.json") -> str:
    """获取配置文件的完整路径
    
    Args:
        filename: 配置文件名，默认为settings.json
        
    Returns:
        str: 配置文件的绝对路径
    """
    config_dir = get_config_dir()
    return os.path.join(config_dir, filename)

def initialize_app_dirs() -> Dict[str, str]:
    """初始化所有应用目录并返回路径信息
    
    该函数会确保应用所需的所有目录都已创建，并返回包含所有路径的字典。
    可在应用启动时调用一次，确保所有目录结构正确创建。
    
    Returns:
        Dict[str, str]: 包含所有路径信息的字典
    """
    # 获取并确保所有目录存在
    app_dir = get_app_dir()
    logs_dir = get_logs_dir()
    config_dir = get_config_dir()
    db_dir = get_db_dir()
    cache_dir = get_cache_dir()
    
    # 返回包含所有路径的字典
    return {
        "app_name": get_app_name(),
        "user_dir": get_user_dir(),
        "app_dir": app_dir,
        "logs_dir": logs_dir,
        "config_dir": config_dir,
        "db_dir": db_dir,
        "cache_dir": cache_dir
    }
