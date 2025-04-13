import os
import sqlite3
import time
import threading
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
from src.utils.app_path import get_db_path

logger = get_logger()

class TaskProxyPool:
    """任务代理池，用于存储和管理临时任务代理"""
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化任务代理池
        
        Args:
            db_path: 数据库文件路径，如果为None则使用应用目录下的默认路径
        """
        self.lock = threading.RLock()
        
        # 如果未指定数据库路径，使用应用目录下的路径
        if not db_path:
            self.db_path = get_db_path("task_proxies")
            logger.debug(f"任务代理池使用应用目录数据库: {self.db_path}")
        else:
            self.db_path = db_path
            logger.debug(f"任务代理池使用指定数据库: {self.db_path}")
        
        # 代理池监控相关变量
        self._should_monitor = False  # 是否应该继续监控
        self._total_tasks = 0  # 总任务数
        self._proxy_source = None  # 代理来源
        self._monitor_task = None  # 异步监控任务
        
        # 初始化数据库
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库和表结构"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                # 创建代理表，设置约束条件
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_proxies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    protocol TEXT NOT NULL,
                    username TEXT,
                    password TEXT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_proxy UNIQUE (host, port, username, password)
                )
                ''')
                
                # 创建索引
                cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_proxies_status ON task_proxies (status)
                ''')
                
                conn.commit()
                logger.debug("任务代理池数据库表初始化完成")
                
            except sqlite3.Error as e:
                logger.error(f"初始化任务代理池数据库表出错: {str(e)}")
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

    def get_pool_stats(self) -> Dict[str, int]:
        """获取任务代理池统计信息
        
        Returns:
            Dict[str, int]: 包含总数、可用数、使用中数、已使用数、失败数
        """
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 获取总数
                cursor.execute("SELECT COUNT(*) FROM task_proxies")
                total = cursor.fetchone()[0]
                
                # 获取各状态数量
                cursor.execute("SELECT status, COUNT(*) FROM task_proxies GROUP BY status")
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                stats = {
                    "total": total,
                    "available": status_counts.get("available", 0),
                    "in_use": status_counts.get("in_use", 0),
                    "used": status_counts.get("used", 0),
                    "failed": status_counts.get("failed", 0)
                }
                
                return stats
                
            except sqlite3.Error as e:
                logger.error(f"获取代理池统计信息出错: {str(e)}")
                return {"total": 0, "available": 0, "in_use": 0, "used": 0, "failed": 0}
            finally:
                if conn:
                    conn.close()

    def clear_task_proxy_pool_da(self) -> bool:
        """清空任务代理池数据
        
        Returns:
            bool: 清空操作是否成功
        """
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 清空表中所有数据
                cursor.execute("DELETE FROM task_proxies")
                
                # 重置自增ID
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='task_proxies'")
                
                # 提交事务
                conn.commit()
                
                # 记录日志
                deleted_count = cursor.rowcount
                logger.info(f"任务代理池已清空，删除了 {deleted_count} 条代理记录")
                
                cursor.close()
                return True
                
            except sqlite3.Error as e:
                logger.error(f"清空任务代理池出错: {str(e)}")
                if conn:
                    conn.rollback()
                return False
                
            finally:
                if conn:
                    conn.close()

    def batch_add_proxies(self, proxy_list: List[Dict[str, Any]]) -> Tuple[int, int]:
        """批量添加代理到任务代理池
        
        Args:
            proxy_list: 代理列表
            
        Returns:
            Tuple[int, int]: (添加成功的数量, 添加失败的数量)
        """
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                success_count = 0
                fail_count = 0
                
                for proxy in proxy_list:
                    try:
                        # 提取代理信息
                        host = proxy.get('host', '')
                        port = proxy.get('port', 0)
                        protocol = proxy.get('protocol', 'http')
                        username = proxy.get('username', '')
                        password = proxy.get('password', '')
                        source = proxy.get('source', 'UNKNOWN')
                        
                        # 验证必要字段
                        if not host or not port:
                            logger.warning(f"跳过无效代理: {proxy}")
                            fail_count += 1
                            continue
                        
                        # 插入记录
                        cursor.execute('''
                        INSERT OR IGNORE INTO task_proxies 
                        (host, port, protocol, username, password, source, status) 
                        VALUES (?, ?, ?, ?, ?, ?, 'available')
                        ''', (host, port, protocol, username, password, source))
                        
                        # 检查是否实际插入了记录
                        if cursor.rowcount > 0:
                            success_count += 1
                        else:
                            fail_count += 1
                            logger.debug(f"代理已存在，忽略添加: {host}:{port}")
                            
                    except Exception as e:
                        fail_count += 1
                        logger.error(f"添加代理时出错: {str(e)}, 代理: {proxy}")
                
                # 提交事务
                conn.commit()
                logger.info(f"批量添加代理到任务代理池: 成功 {success_count} 个, 失败 {fail_count} 个")
                
                return success_count, fail_count
                
            except sqlite3.Error as e:
                logger.error(f"批量添加代理到任务代理池出错: {str(e)}")
                if conn:
                    conn.rollback()
                return 0, len(proxy_list)
                
            finally:
                if conn:
                    conn.close()

    def get_proxy(self) -> Optional[Dict[str, Any]]:
        """从任务代理池中获取一个可用的代理
        
        获取后会将代理状态更新为'in_use'
        
        Returns:
            Optional[Dict[str, Any]]: 代理信息，如果没有可用代理则返回None
        """
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
                cursor = conn.cursor()
                
                # 获取一个可用的代理
                cursor.execute('''
                SELECT * FROM task_proxies 
                WHERE status = 'available' 
                ORDER BY id ASC 
                LIMIT 1
                ''')
                
                proxy_row = cursor.fetchone()
                if not proxy_row:
                    logger.warning("任务代理池中没有可用的代理")
                    return None
                
                # 将代理状态更新为'in_use'
                proxy_id = proxy_row['id']
                cursor.execute('''
                UPDATE task_proxies 
                SET status = 'in_use', last_updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                ''', (proxy_id,))
                
                # 提交事务
                conn.commit()
                
                # 构建代理信息字典
                proxy = {
                    "id": proxy_id,
                    "host": proxy_row['host'],
                    "port": proxy_row['port'],
                    "protocol": proxy_row['protocol'],
                    "username": proxy_row['username'] if proxy_row['username'] else '',
                    "password": proxy_row['password'] if proxy_row['password'] else '',
                    "source": proxy_row['source'],
                    "status": 'in_use'
                }
                
                logger.debug(f"从任务代理池获取代理: {proxy['host']}:{proxy['port']}")
                return proxy
                
            except sqlite3.Error as e:
                logger.error(f"从任务代理池获取代理时出错: {str(e)}")
                if conn:
                    conn.rollback()
                return None
                
            finally:
                if conn:
                    conn.close()
                    
    def mark_proxy_status(self, proxy_id: int, status: str) -> bool:
        """标记代理状态
        
        Args:
            proxy_id: 代理ID
            status: 新状态，可选值: 'available', 'in_use', 'failed', 'used'
            
        Returns:
            bool: 操作是否成功
        """
        with self.lock:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 更新代理状态
                cursor.execute('''
                UPDATE task_proxies 
                SET status = ?, last_updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                ''', (status, proxy_id))
                
                # 提交事务
                conn.commit()
                
                # 检查是否实际更新了记录
                if cursor.rowcount > 0:
                    logger.debug(f"代理 (ID: {proxy_id}) 状态已更新为: {status}")
                    return True
                else:
                    logger.warning(f"未找到ID为 {proxy_id} 的代理，无法更新状态")
                    return False
                
            except sqlite3.Error as e:
                logger.error(f"更新代理状态时出错: {str(e)}")
                if conn:
                    conn.rollback()
                return False
                
            finally:
                if conn:
                    conn.close()
                    
    async def monitor_pool_for_tasks(self, total_tasks: int, proxy_source: str = 'api') -> None:
        """异步监控任务代理池，并根据需求动态补充代理
        
        Args:
            total_tasks: 总任务数量
            proxy_source: 代理来源，'api'或'pool'
        """
        # 如果已经在监控中，直接返回
        if self._should_monitor:
            logger.warning("代理池监控已在运行中，无需重复启动")
            return
            
        if proxy_source not in ['api', 'pool']:
            logger.error(f"不支持的代理来源: {proxy_source}，只能是'api'或'pool'")
            return
            
        self._total_tasks = total_tasks
        self._proxy_source = proxy_source
        self._should_monitor = True
        
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        
        # 创建异步监控任务
        self._monitor_task = loop.create_task(self._monitor_pool_async())
        logger.info(f"已启动任务代理池异步监控，总任务数: {total_tasks}，代理来源: {proxy_source}")
        
    async def stop_monitoring(self) -> None:
        """异步停止任务代理池监控"""
        if not self._should_monitor:
            return
            
        self._should_monitor = False
        logger.info("正在停止任务代理池监控...")
        
        # 等待监控任务完成
        if self._monitor_task and not self._monitor_task.done():
            try:
                # 给监控任务一些时间来完成当前周期并退出
                await asyncio.wait_for(self._monitor_task, timeout=3.0)
            except asyncio.TimeoutError:
                # 超时后取消任务
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    logger.debug("任务代理池监控任务已取消")
            
        logger.info("任务代理池监控已停止")
    
    async def _monitor_pool_async(self) -> None:
        """异步代理池监控函数"""
        try:
            # 安全系数：确保有足够的代理可用，避免因代理不足导致任务无法执行
            safety_factor = 1.2
            
            # 最低代理数：即使任务数很少，也至少保持这么多代理
            min_proxies = 5
            
            # 检查间隔：每隔多少秒检查一次代理池状态
            check_interval = 10
            
            # 导入代理管理器，获取代理
            from src.core.proxy.proxy_manager import get_proxy_manager
            proxy_manager = get_proxy_manager()
            
            # 监控循环
            while self._should_monitor:
                # 异步检查和补充代理
                await self._check_and_replenish_proxies(
                    proxy_manager, 
                    safety_factor, 
                    min_proxies
                )
                
                # 异步等待下一次检查
                await asyncio.sleep(check_interval)
                
        except asyncio.CancelledError:
            logger.debug("代理池监控任务被取消")
            raise
        except Exception as e:
            logger.error(f"代理池监控任务发生错误: {str(e)}")
        finally:
            logger.debug("代理池监控任务已退出")
            
    async def _check_and_replenish_proxies(self, proxy_manager, safety_factor, min_proxies) -> None:
        """检查代理池状态并补充代理
        
        Args:
            proxy_manager: 代理管理器
            safety_factor: 安全系数
            min_proxies: 最低代理数
        """
        try:
            # 获取代理池状态
            stats = self.get_pool_stats()
            available_count = stats["available"]
            
            # 计算需要的代理数量
            needed_count = max(min_proxies, int(self._total_tasks * safety_factor))
            
            # 如果可用代理不足，补充代理
            if available_count < needed_count:
                # 计算需要补充的数量
                fetch_count = needed_count - available_count
                logger.info(f"任务代理池可用代理不足 (当前: {available_count}, 需要: {needed_count})，补充 {fetch_count} 个")
                
                # 调用代理管理器获取代理
                await proxy_manager.get_proxies_batch(
                    count=fetch_count,
                    source_type=self._proxy_source,
                    save_to_task_pool=True
                )
                
                # 再次获取统计信息，查看是否补充成功
                new_stats = self.get_pool_stats()
                logger.info(f"代理补充后，可用代理: {new_stats['available']} 个")
            else:
                logger.debug(f"任务代理池代理充足 (当前可用: {available_count}, 需要: {needed_count})")
                
        except Exception as e:
            logger.error(f"检查并补充代理时出错: {str(e)}")
