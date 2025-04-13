import asyncio
import time
from typing import Dict, List, Tuple, Any, Optional, Set, Callable
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger
from src.core.proxy.proxy_checker import ProxyChecker
from src.core.proxy.proxy_source.direct_source import DirectConnectionSource
from src.core.proxy.proxy_source.fixed_source import FixedProxySource
from src.core.proxy.proxy_source.api_source import ApiProxySource
from src.core.proxy.proxy_source.import_source import ImportedProxySource
from src.core.proxy.task_proxy_pool import TaskProxyPool

logger = get_logger()

class ProxyManager:
    """代理管理器类
    
    统一管理不同来源的代理，提供异步获取和检测代理的接口
    """
    
    def __init__(self):
        """初始化代理管理器"""
        self.config_manager = ConfigManager()
        
        # 初始化代理来源
        self.direct_source = DirectConnectionSource()
        self.fixed_source = FixedProxySource()
        self.api_source = ApiProxySource()
        self.import_source = ImportedProxySource()
        
        # 初始化代理检查器
        self.proxy_checker = ProxyChecker(self.config_manager)
        
        # 初始化代理缓存
        self._proxy_cache = {
            # 直连模式缓存
            "direct": {
                "proxy": None,          # 代理信息
                "check_result": None,   # 检测结果
                "last_check_time": 0,   # 最后检测时间戳
                "expiry_time": 0,       # 过期时间戳
                "failures": 0           # 连续失败计数
            },
            # 固定代理缓存
            "fixed": {
                "proxy": None,
                "check_result": None,
                "last_check_time": 0,
                "expiry_time": 0,
                "failures": 0
            }
        }
        
        # 缓存锁 - 确保线程安全
        self._cache_lock = asyncio.Lock()
        
        # 加载配置
        self._load_config()
        
    def _load_config(self):
        """从配置管理器加载配置"""
        settings = self.config_manager.load_settings() or {}
        
        # 获取代理设置
        proxy_settings = settings.get("proxy", {})
        
        # 当前代理来源
        self.source_type = proxy_settings.get("source", "direct")
        
        # 获取缓存设置
        cache_settings = proxy_settings.get("cache", {})
        self._cache_ttl = cache_settings.get("ttl", 300)  # 默认5分钟
        self._cache_failure_ttl = cache_settings.get("failure_ttl", 30)  # 失败后30秒
        self._cache_max_failures = cache_settings.get("max_failures", 3)  # 最大3次失败
        
        # 获取通用设置
        general_settings = settings.get("general", {})
        try:
            self.max_workers = int(general_settings.get("thread_count", 10))
        except (ValueError, TypeError):
            self.max_workers = 10
            
        # 忽略IP检查
        self.ignore_ip_check = general_settings.get("ignore_ip_check", True)
        
        # 目标国家
        self.target_country = general_settings.get("ip_country", "CN")
        
    async def get_proxy(self, source_type: Optional[str] = None, retry_count: int = 0) -> Dict[str, Any]:
        """从指定来源异步获取单个代理
        
        优先从缓存中获取，如果缓存不存在或已过期，则重新检测
        最多尝试3次，如果获取失败会自动重试
        
        Args:
            source_type: 代理来源类型，可选值为 'direct', 'fixed'
                         如果为None，则使用配置中设置的默认来源
            retry_count: 当前重试次数，内部使用，不需要手动设置
        
        Returns:
            Dict[str, Any]: 代理信息，如果获取失败则为空字典
                           对于直连模式，返回连通性和IP所在地检查结果
        """
        # 设置最大重试次数
        max_retries = 3
        
        # 检查重试次数是否超过最大值
        if retry_count >= max_retries:
            logger.warning(f"获取代理失败，已达到最大重试次数 ({max_retries})")
            return {}
        
        # 如果未指定来源类型，使用配置中的默认来源
        if source_type is None:
            source_type = self.source_type
            
        # 只支持direct和fixed两种来源
        if source_type not in ["direct", "fixed"]:
            logger.error(f"get_proxy方法只支持 'direct' 和 'fixed' 两种来源，当前: {source_type}")
            return {}
        
        # 检查缓存是否有效
        async with self._cache_lock:
            cache = self._proxy_cache.get(source_type)
            current_time = time.time()
            
            # 缓存有效且存在代理信息时直接返回
            if (cache and cache["proxy"] and cache["check_result"] and 
                current_time < cache["expiry_time"]):
                logger.debug(f"使用缓存的{source_type}代理，距离上次检查: {int(current_time - cache['last_check_time'])}秒")
                return cache["proxy"]
        
        # 缓存无效，获取新代理
        try:
            # 根据来源类型选择相应的代理来源
            if source_type == "direct":
                # 对于直连模式，检查连通性和IP所在地
                success, result = await self.check_proxy(None)
                if success:
                    # 创建一个包含直连检测结果的伪代理对象
                    proxy = {
                        "source": "DIRECT",
                        "is_direct": True,
                        "check_result": result,
                        # 如果有IP地址信息，添加到proxy中
                        "ip": result.get("ip", "unknown")
                    }
                    
                    # 更新缓存
                    await self._update_proxy_cache(source_type, proxy, result, success)
                    return proxy
                else:
                    logger.error(f"直连不可用: {result.get('error', '未知错误')}，重试 {retry_count+1}/{max_retries}")
                    # 记录失败并更新缓存状态
                    await self._update_proxy_cache(source_type, {}, result, success)
                    # 短暂等待后重试
                    await asyncio.sleep(1)
                    return await self.get_proxy(source_type, retry_count + 1)
                
            elif source_type == "fixed":
                # 从固定代理来源获取代理
                # 由于原方法是同步的，使用run_in_executor转为异步
                proxy_list = await asyncio.get_event_loop().run_in_executor(
                    None, self.fixed_source.get_proxies, 1
                )
                if proxy_list:
                    # 对获取的代理进行检测
                    proxy = proxy_list[0]
                    success, result = await self.check_proxy(proxy)
                    if success:
                        proxy["check_result"] = result
                        # 更新缓存
                        await self._update_proxy_cache(source_type, proxy, result, success)
                        return proxy
                    else:
                        logger.error(f"固定代理不可用: {result.get('error', '未知错误')}，重试 {retry_count+1}/{max_retries}")
                        # 记录失败并更新缓存状态
                        await self._update_proxy_cache(source_type, {}, result, success)
                        # 短暂等待后重试
                        await asyncio.sleep(1)
                        return await self.get_proxy(source_type, retry_count + 1)
                else:
                    logger.error(f"固定代理获取失败，重试 {retry_count+1}/{max_retries}")
                    # 记录失败并更新缓存状态
                    await self._update_proxy_cache(source_type, {}, {"error": "获取代理失败"}, False)
                    # 短暂等待后重试
                    await asyncio.sleep(1)
                    return await self.get_proxy(source_type, retry_count + 1)
                
        except Exception as e:
            logger.error(f"获取代理时出错: {str(e)}，重试 {retry_count+1}/{max_retries}")
            # 发生异常时也更新缓存状态
            await self._update_proxy_cache(source_type, {}, {"error": str(e)}, False)
            # 短暂等待后重试
            await asyncio.sleep(1)
            return await self.get_proxy(source_type, retry_count + 1)

    async def _update_proxy_cache(self, source_type: str, proxy: Dict[str, Any], 
                                check_result: Dict[str, Any], success: bool) -> None:
        """更新代理缓存
        
        Args:
            source_type: 代理来源类型
            proxy: 代理信息
            check_result: 检测结果
            success: 检测是否成功
        """
        async with self._cache_lock:
            current_time = time.time()
            cache = self._proxy_cache.get(source_type)
            
            if not cache:
                # 如果缓存不存在，初始化
                cache = {
                    "proxy": None,
                    "check_result": None,
                    "last_check_time": 0,
                    "expiry_time": 0,
                    "failures": 0
                }
                self._proxy_cache[source_type] = cache
            
            # 更新缓存内容
            cache["proxy"] = proxy if success else None
            cache["check_result"] = check_result
            cache["last_check_time"] = current_time
            
            # 根据检测结果设置过期时间和更新失败计数
            if success:
                # 成功时重置失败计数，使用标准TTL
                cache["failures"] = 0
                cache["expiry_time"] = current_time + self._cache_ttl
                logger.debug(f"更新{source_type}代理缓存，有效期: {self._cache_ttl}秒")
            else:
                # 失败时增加失败计数，使用更短的TTL
                cache["failures"] += 1
                
                # 如果连续失败次数超过阈值，下次必须重新检测
                if cache["failures"] >= self._cache_max_failures:
                    cache["expiry_time"] = 0
                    logger.warning(f"{source_type}代理连续失败{cache['failures']}次，下次将强制重新检测")
                else:
                    # 使用失败TTL（更短）
                    cache["expiry_time"] = current_time + self._cache_failure_ttl
                    logger.debug(f"{source_type}代理检测失败，{self._cache_failure_ttl}秒后重试")

    async def report_proxy_failure(self, source_type: Optional[str] = None) -> None:
        """报告代理使用失败
        
        当应用层检测到代理实际使用失败时调用此方法，
        用于提前使缓存过期并增加失败计数
        
        Args:
            source_type: 代理来源类型，可选值为 'direct', 'fixed'
                         如果为None，则使用配置中的默认来源
        """
        if source_type is None:
            source_type = self.source_type
            
        if source_type not in ["direct", "fixed"]:
            return
            
        async with self._cache_lock:
            cache = self._proxy_cache.get(source_type)
            if cache:
                cache["failures"] += 1
                
                # 立即使缓存过期，强制下次重新检测
                cache["expiry_time"] = 0
                logger.warning(f"应用层报告{source_type}代理失败，强制下次重新检测")

    async def refresh_proxy_cache(self, source_type: Optional[str] = None) -> bool:
        """强制刷新代理缓存
        
        Args:
            source_type: 代理来源类型，可选值为 'direct', 'fixed'
                         如果为None，则使用配置中的默认来源
                         
        Returns:
            bool: 刷新是否成功
        """
        if source_type is None:
            source_type = self.source_type
            
        if source_type not in ["direct", "fixed"]:
            logger.error(f"refresh_proxy_cache方法只支持 'direct' 和 'fixed' 两种来源，当前: {source_type}")
            return False
        
        # 强制缓存过期
        async with self._cache_lock:
            cache = self._proxy_cache.get(source_type)
            if cache:
                cache["expiry_time"] = 0
                
        # 重新获取代理
        proxy = await self.get_proxy(source_type)
        return bool(proxy)

    async def get_proxies_batch(self, 
                               count: int, 
                               source_type: Optional[str] = None,
                               save_to_task_pool: bool = True) -> List[Dict[str, Any]]:
        """从指定来源异步批量获取代理
        
        Args:
            count: 需要获取的代理数量
            source_type: 代理来源类型，可选值为 'api', 'pool' (导入代理池)
                         如果为None，则使用配置中设置的默认来源
            save_to_task_pool: 是否保存到任务代理池，默认为True
            
        Returns:
            List[Dict[str, Any]]: 代理列表
        """
        # 如果未指定来源类型，使用配置中的默认来源
        if source_type is None:
            source_type = self.source_type
            
        # 只支持API和导入代理池两种批量来源
        if source_type not in ["api", "pool"]:
            logger.error(f"批量获取代理只支持 'api' 和 'pool' 两种来源，当前: {source_type}")
            return []
            
        try:
            # 获取代理列表
            if source_type == "api":
                proxy_list = await asyncio.get_event_loop().run_in_executor(
                    None, self.api_source.get_proxies, int(count * 1.5)
                )
            else:  # pool
                proxy_list = await asyncio.get_event_loop().run_in_executor(
                    None, self.import_source.get_proxies, int(count * 1.5)
                )
                
            logger.info(f"批量获取代理: 总共 {len(proxy_list)} 个")
            
            # 如果需要，保存到任务代理池
            if save_to_task_pool and proxy_list:
                await self._save_to_task_pool(proxy_list)
            
            return proxy_list
            
        except Exception as e:
            logger.error(f"批量获取代理时出错: {str(e)}")
            return []
            
    async def _save_to_task_pool(self, proxy_list: List[Dict[str, Any]]) -> Tuple[int, int]:
        """保存代理到任务代理池
        
        Args:
            proxy_list: 代理列表
            
        Returns:
            Tuple[int, int]: (添加成功的数量, 添加失败的数量)
        """
        try:
            # 懒加载任务代理池
            task_pool = TaskProxyPool()
            
            # 使用线程池执行数据库操作，避免阻塞事件循环
            success_count, fail_count = await asyncio.get_event_loop().run_in_executor(
                None, task_pool.batch_add_proxies, proxy_list
            )
            
            logger.info(f"已将 {success_count} 个代理保存到任务代理池")
            return success_count, fail_count
            
        except Exception as e:
            logger.error(f"保存代理到任务代理池出错: {str(e)}")
            return 0, len(proxy_list)
            
    async def get_proxy_from_task_pool(self, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """从任务代理池中异步获取单个代理
        
        获取后会将代理状态更新为'in_use'，如果代理检测失败，会自动尝试获取下一个代理，
        直到获取到可用代理或达到最大重试次数。
        
        Args:
            retry_count: 当前重试次数，内部使用
        
        Returns:
            Optional[Dict[str, Any]]: 代理信息，如果没有可用代理则返回None
        """
        try:
            # 获取配置的最大代理更换次数
            settings = self.config_manager.load_settings() or {}
            proxy_settings = settings.get("proxy", {})
            checker_settings = proxy_settings.get("checker", {})
            max_proxy_retries = checker_settings.get("max_proxy_retries", 5)
            
            # 检查是否超过最大重试次数
            if retry_count >= max_proxy_retries:
                logger.warning(f"尝试获取代理失败，已达到最大重试次数 ({max_proxy_retries})")
                return None
                
            # 懒加载任务代理池
            task_pool = TaskProxyPool()
            
            # 使用线程池执行数据库操作，避免阻塞事件循环
            proxy = await asyncio.get_event_loop().run_in_executor(
                None, task_pool.get_proxy
            )
            
            if proxy:
                logger.info(f"从任务代理池获取代理: {proxy['host']}:{proxy['port']} (尝试 {retry_count+1}/{max_proxy_retries})")
                
                # 进行代理检测以确保可用性
                success, result = await self.check_proxy(proxy)
                if success:
                    # 添加检测结果
                    proxy["check_result"] = result
                    return proxy
                else:
                    # 如果代理不可用，标记为失败并获取下一个
                    logger.warning(f"任务代理池中的代理不可用: {proxy['host']}:{proxy['port']}, 错误: {result.get('error', '未知错误')}")
                    
                    # 异步标记代理状态为失败
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: task_pool.mark_proxy_status(proxy['id'], 'failed')
                    )
                    
                    # 递归调用自身尝试获取下一个代理，并增加重试计数
                    return await self.get_proxy_from_task_pool(retry_count + 1)
            else:
                logger.warning("任务代理池中没有可用的代理")
                return None
                
        except Exception as e:
            logger.error(f"从任务代理池获取代理时出错: {str(e)}")
            return None
            
    async def mark_task_proxy_used(self, proxy_id: int) -> bool:
        """将任务代理池中的代理标记为已使用
        
        Args:
            proxy_id: 代理ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 懒加载任务代理池
            task_pool = TaskProxyPool()
            
            # 使用线程池执行数据库操作，避免阻塞事件循环
            success = await asyncio.get_event_loop().run_in_executor(
                None, lambda: task_pool.mark_proxy_status(proxy_id, 'used')
            )
            
            if success:
                logger.debug(f"代理 (ID: {proxy_id}) 已标记为已使用")
            else:
                logger.warning(f"标记代理 (ID: {proxy_id}) 为已使用失败")
                
            return success
            
        except Exception as e:
            logger.error(f"标记代理为已使用时出错: {str(e)}")
            return False

    async def check_proxy(self, proxy: Optional[Dict[str, Any]] = None, test_url: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """异步检测单个代理的有效性，也可用于检测直连
        
        Args:
            proxy: 代理信息，如果为None或空字典则检测直连
            test_url: 测试URL，如果为None则使用自动选择的URL
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (是否有效, 检测结果详情)
        """
        try:
            # 如果proxy为None或空字典，检测直连
            if proxy is None or not proxy:
                logger.debug("检测直连连通性和IP所在地")
                return await self.proxy_checker.check_direct_connection_async()
            else:
                # 检测代理
                return await self.proxy_checker.check_proxy_async(proxy, test_url)
        except Exception as e:
            logger.error(f"检测连通性时出错: {str(e)}")
            return False, {"error": f"检测出错: {str(e)}"}
            
    async def check_proxies_batch(self, 
                                 proxies: List[Dict[str, Any]], 
                                 callback: Optional[Callable[[Dict[str, Any], bool, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """异步批量检测代理有效性
        
        Args:
            proxies: 代理列表
            callback: 回调函数，用于处理检查结果，参数为(代理, 是否可用, 结果详情)
            
        Returns:
            Dict[str, Any]: 检查结果统计
        """
        if not proxies:
            return {"total": 0, "available": 0, "unavailable": 0}
            
        try:
            # 已有异步批量检测方法，直接使用
            return await self.proxy_checker.batch_check_async(proxies, callback)
        except Exception as e:
            logger.error(f"批量检测代理时出错: {str(e)}")
            return {
                "total": len(proxies),
                "available": 0,
                "unavailable": len(proxies),
                "error": str(e)
            }
    
    async def reload_config(self):
        """重新加载配置"""
        self._load_config()

# 单例模式
_proxy_manager_instance = None

def get_proxy_manager() -> ProxyManager:
    """获取代理管理器单例"""
    global _proxy_manager_instance
    if _proxy_manager_instance is None:
        _proxy_manager_instance = ProxyManager()
    return _proxy_manager_instance
