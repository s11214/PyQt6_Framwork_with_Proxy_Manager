import sqlite3
import os
import time
import threading
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QApplication
import json
from src.utils.logger import get_logger
from src.utils.app_path import get_db_path

logger = get_logger()

class ImportedProxyPool:
    """导入代理池类 - 管理导入的代理
    
    导入代理池负责存储和管理所有导入的代理，包括代理状态、响应时间、成功率等信息。
    它提供了添加、获取、更新代理状态等功能。
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化代理池
        
        Args:
            db_path: 数据库文件路径，如果为None则使用应用目录下的默认路径
        """
        self.proxies = []
        self.lock = threading.RLock()  # 用于线程安全操作
        
        # 如果未指定数据库路径，使用应用目录下的路径
        if not db_path:
            self.db_path = get_db_path("imported_proxies")
            logger.debug(f"导入代理池使用应用目录数据库: {self.db_path}")
        else:
            self.db_path = db_path
            logger.debug(f"导入代理池使用指定数据库: {self.db_path}")
        
        self._init_db()
        self._load_proxies_from_db()
        
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建代理表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy_type TEXT NOT NULL,
                host TEXT NOT NULL,
                port TEXT NOT NULL,
                username TEXT,
                password TEXT,
                country TEXT,
                status TEXT DEFAULT 'unused',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _load_proxies_from_db(self):
        """从数据库加载代理"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取列名
        cursor.execute("PRAGMA table_info(proxies)")
        columns = [column[1] for column in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM proxies')
        rows = cursor.fetchall()
        
        # 将数据库行转换为代理字典
        self.proxies = []
        for row in rows:
            proxy = {
                'id': row[0],
                'proxy_type': row[1],
                'host': row[2],
                'port': row[3],
                'username': row[4],
                'password': row[5],
                'country': row[6],
                'status': row[7]  # 直接使用数据库中的status字段
            }
            self.proxies.append(proxy)
            
        conn.close()
        
    def add_proxy(self, proxy_type: str, host: str, port: str, username: str, password: str, country: str = "OTHER") -> tuple[bool, str]:
        """添加代理到池中"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查是否已存在相同的代理
            cursor.execute('''
                SELECT id FROM proxies 
                WHERE proxy_type = ? AND host = ? AND port = ? AND username = ? AND password = ?
            ''', (proxy_type, host, port, username, password))
            
            if cursor.fetchone():
                return False, "代理已存在"
            
            # 插入新代理
            cursor.execute('''
                INSERT INTO proxies (proxy_type, host, port, username, password, country)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (proxy_type, host, port, username, password, country))
            
            conn.commit()
            conn.close()
            
            # 重新加载代理列表
            self._load_proxies_from_db()
            
            return True, "代理添加成功"
        except Exception as e:
            return False, f"代理添加失败: {str(e)}"
            
    def get_proxies(self) -> List[Dict]:
        """获取所有代理"""
        # 确保每次获取代理都是从数据库获取最新数据
        try:
            # 先清空现有代理列表
            self.proxies.clear()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM proxies')
            rows = cursor.fetchall()
            
            for row in rows:
                proxy = {
                    'id': row[0],
                    'proxy_type': row[1],
                    'host': row[2],
                    'port': row[3],
                    'username': row[4],
                    'password': row[5],
                    'country': row[6],
                    'status': row[7]
                }
                self.proxies.append(proxy)
                
            conn.close()
        except Exception as e:
            print(f"获取代理时出错: {str(e)}")
            
        return self.proxies
        
    def get_proxy_stats(self) -> tuple[int, int]:
        """获取代理统计信息"""
        used = sum(1 for p in self.proxies if p.get('status') == 'used')
        total = len(self.proxies)
        return used, total
        
    def clear_all(self) -> tuple[bool, str]:
        """清空代理池"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM proxies')
            conn.commit()
            conn.close()
            
            self.proxies.clear()
            return True, "代理池已清空"
        except Exception as e:
            return False, f"清空失败: {str(e)}"
            
    def update_proxy_status(self, proxy_id: int, status: str) -> tuple[bool, str]:
        """更新代理状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE proxies 
                SET status = ? 
                WHERE id = ?
            ''', (status, proxy_id))
            
            conn.commit()
            conn.close()
            
            # 更新内存中的代理状态
            for proxy in self.proxies:
                if proxy['id'] == proxy_id:
                    proxy['status'] = status
                    break
                    
            return True, "状态更新成功"
        except Exception as e:
            return False, f"状态更新失败: {str(e)}"
            
    def delete_proxy(self, proxy_id: int) -> tuple[bool, str]:
        """删除代理"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM proxies WHERE id = ?', (proxy_id,))
            conn.commit()
            conn.close()
            
            # 从内存中删除代理
            self.proxies = [p for p in self.proxies if p['id'] != proxy_id]
            
            return True, "代理删除成功"
        except Exception as e:
            return False, f"删除失败: {str(e)}"
            
    def batch_add_proxies(self, proxy_list: List[Dict]) -> tuple[int, int, str]:
        """批量添加代理到池中
        
        Args:
            proxy_list: 代理列表，每个代理为包含必要信息的字典
            
        Returns:
            tuple: (成功数量, 失败数量, 错误消息)
        """
        success_count = 0
        fail_count = 0
        error_msg = ""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 准备批量插入
            values_to_insert = []
            for proxy in proxy_list:
                proxy_type = proxy.get('proxy_type')
                host = proxy.get('host')
                port = proxy.get('port')
                username = proxy.get('username')
                password = proxy.get('password')
                country = proxy.get('country', 'OTHER')
                
                # 检查是否已存在相同的代理
                cursor.execute('''
                    SELECT id FROM proxies 
                    WHERE proxy_type = ? AND host = ? AND port = ? AND username = ? AND password = ?
                ''', (proxy_type, host, port, username, password))
                
                if cursor.fetchone():
                    fail_count += 1
                    continue
                
                values_to_insert.append((proxy_type, host, port, username, password, country))
            
            # 批量插入
            if values_to_insert:
                cursor.executemany('''
                    INSERT INTO proxies (proxy_type, host, port, username, password, country)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', values_to_insert)
                
                success_count = len(values_to_insert)
                
            conn.commit()
            conn.close()
            
            # 重新加载代理列表
            self._load_proxies_from_db()
            
            return success_count, fail_count, error_msg
        except Exception as e:
            error_msg = f"批量导入代理失败: {str(e)}"
            return success_count, fail_count, error_msg 