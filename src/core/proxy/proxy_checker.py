import requests
import time
import asyncio
import aiohttp
import random
import json
from typing import Dict, Any, Tuple, Optional, List, Callable, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
import threading
from requests.exceptions import RequestException, Timeout, ProxyError
from src.core.geo.country_mapper import get_mapper
from src.core.geo.data import COUNTRY_CODE_ALIASES

logger = get_logger()

class IPDetector:
    """IP地区检测器类，用于检测IP地区信息"""
    
    def __init__(self, ip_apis: List[Dict[str, Any]]):
        """初始化IP地区检测器
        
        Args:
            ip_apis: IP检测API列表
        """
        self.ip_apis = ip_apis
        
        # API状态跟踪
        self.api_states = {}
        for api in self.ip_apis:
            url = api["url"]
            self.api_states[url] = {
                "last_used": 0,
                "success_count": 0,
                "failure_count": 0,
                "blocked_until": 0
            }
        
        # 获取国家/地区代码映射器
        self.country_mapper = get_mapper()
        # 便于兼容现有代码的引用方式
        self.country_mapping = self.country_mapper.country_mapping
        
    def get_next_available_api(self) -> Optional[Dict[str, Any]]:
        """获取下一个可用的API配置"""
        current_time = time.time()
        
        # 收集所有可用（不在冷却期）的API
        available_apis = []
        for api in self.ip_apis:
            url = api["url"]
            state = self.api_states.get(url, {})
            
            # 检查是否在冷却期
            if current_time < state.get("blocked_until", 0):
                continue
                
            available_apis.append(api)
        
        # 如果有可用的API，随机选择一个
        if available_apis:
            selected_api = random.choice(available_apis)
            # 更新最后使用时间
            self.api_states[selected_api["url"]]["last_used"] = current_time
            return selected_api
            
        # 如果没有可用API，重置所有API状态
        for url in self.api_states:
            self.api_states[url]["blocked_until"] = 0
            
        # 随机返回一个API（如果有的话）
        return random.choice(self.ip_apis) if self.ip_apis else None
        
    def update_api_state(self, api_url: str, success: bool) -> None:
        """更新API状态
        
        Args:
            api_url: API URL
            success: 是否成功
        """
        if api_url not in self.api_states:
            self.api_states[api_url] = {
                "last_used": time.time(),
                "success_count": 0,
                "failure_count": 0,
                "blocked_until": 0
            }
            
        if success:
            self.api_states[api_url]["success_count"] += 1
        else:
            self.api_states[api_url]["failure_count"] += 1
            # 如果连续失败超过5次，则暂时封禁此API
            if self.api_states[api_url]["failure_count"] % 5 == 0:
                self.api_states[api_url]["blocked_until"] = time.time() + 300  # 封禁5分钟
                logger.warning(f"API '{api_url}' 已暂时封禁5分钟，因为连续失败次数过多")
        
    def extract_country_code(self, response_json: Dict[str, Any], api_config: Dict[str, Any]) -> Optional[str]:
        """从API响应中提取国家代码
        
        Args:
            response_json: API响应JSON
            api_config: API配置
            
        Returns:
            Optional[str]: 国家代码或None
        """
        country_code = None
        country_info = None  # API返回的原始国家/地区
        raw_value = None
        
        # 首先尝试从country_path获取国家名称或代码
        country_path = api_config.get("country_path")
        if country_path:
            try:
                paths = country_path.split(".")
                country_value = response_json
                for path in paths:
                    if isinstance(country_value, dict) and path in country_value:
                        country_value = country_value[path]
                    else:
                        country_value = None
                        break
                        
                if country_value:
                    raw_value = str(country_value)
                    country_info = raw_value
            except Exception as e:
                logger.error(f"提取国家/地区路径出错: {str(e)}")
        
        # 检查中国IP标识
        cnip = False
        cnip_path = api_config.get("cnip_path")
        if cnip_path:
            try:
                paths = cnip_path.split(".")
                cnip_value = response_json
                for path in paths:
                    if isinstance(cnip_value, dict) and path in cnip_value:
                        cnip_value = cnip_value[path]
                    else:
                        cnip_value = None
                        break
                        
                if cnip_value is True:
                    cnip = True
            except Exception as e:
                logger.error(f"提取中国IP标识路径出错: {str(e)}")
        
        # 处理原始提取值
        if raw_value:
            raw_value = raw_value.strip()
            
            # 1. 检查是否已经是有效的ISO代码
            if len(raw_value) == 2 and all(ord(c) < 128 for c in raw_value):
                iso_code = raw_value.upper()
                # 验证是有效的ISO代码（直接在mapping表中检查）
                if iso_code in self.country_mapper.country_mapping:
                    country_code = iso_code
                    country_name = self.country_mapper.get_country_name(iso_code)
                    logger.debug(f"API直接返回ISO代码: {iso_code}, 对应国家: {country_name}")
            
            # 2. 如果不是ISO代码，将其视为国家名称，通过映射器获取代码
            if country_code is None:
                country_name = raw_value
                # 尝试直接获取代码
                country_code = self.country_mapper.get_country_code(country_name)
                
                # 如果获取失败，可能是常见的中文变体，尝试查找别名
                if country_code is None:
                    # 检查是否为中文字符（通过Unicode范围判断）
                    has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in country_name)
                    
                    if has_chinese:
                        logger.debug(f"检测到中文国家名称: {country_name}，尝试匹配别名")
                        # 遍历别名字典寻找匹配
                        for code, aliases in COUNTRY_CODE_ALIASES.items():
                            # 检查任何中文别名是否包含在country_name中
                            chinese_aliases = [alias for alias in aliases if any('\u4e00' <= ch <= '\u9fff' for ch in alias)]
                            for alias in chinese_aliases:
                                if alias in country_name or country_name in alias:
                                    country_code = code
                                    logger.debug(f"通过中文别名匹配成功: {country_name} -> {code}")
                                    break
                            if country_code:
                                break
        
        # 如果是中国IP但没有具体地区信息，默认为中国大陆
        if country_code is None and cnip:
            if country_info is None or country_info not in ["香港", "澳门", "台湾", "Hong Kong", "Macau", "Macao", "Taiwan"]:
                country_code = "CN"
                country_name = "中国"
            else:
                # 处理中国港澳台地区
                special_regions = {
                    "香港": "HK", "Hong Kong": "HK",
                    "澳门": "MO", "Macau": "MO", "Macao": "MO",
                    "台湾": "TW", "Taiwan": "TW"
                }
                # 根据地区名称设置对应的区域代码
                country_code = special_regions.get(country_info)
                logger.debug(f"处理中国特别行政区: {country_info} -> {country_code}")
        
        # 获取对应的国家名称（如果有）
        country_name = self.country_mapper.get_country_name(country_code) if country_code else None
        country_english_name = self.country_mapper.get_country_english_name(country_code) if country_code else None
        
        logger.debug(f"从API获取到地区信息: 原始值={raw_value}, 国家代码={country_code}, "
                     f"中文名={country_name}, 英文名={country_english_name}, 中国IP={cnip}")
        
        return country_code
        
    def match_country_code(self, country_code: str, target_country: str) -> bool:
        """检查国家/地区代码是否匹配目标国家
        
        Args:
            country_code: 检测到的国家/地区代码
            target_country: 目标国家/地区代码
            
        Returns:
            bool: 是否匹配
        """
        # 使用国家映射器进行匹配
        return self.country_mapper.match_country_code(country_code, target_country)

class ProxyChecker:
    """代理检查器，用于检查代理是否可用"""
    
    # 默认User-Agent
    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    
    # 可能表示被反爬的状态码
    RATE_LIMIT_STATUS_CODES = {403, 429, 503}
    
    def __init__(self, config_manager: ConfigManager):
        """初始化代理检查器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.lock = threading.RLock()
        
        # 默认检查URL (会被配置覆盖)
        self.check_url = "https://api.vore.top/api/IPdata"
        
        # 测试URL列表将从配置中加载
        self._test_urls = []
        
        # 轮换URL机制的状态跟踪
        self._url_status = {}  # 记录每个URL的状态
        self._blocked_urls = set()  # 记录被封禁的URL
        self._url_cooldown = {}  # URL冷却时间
        self._url_last_used = {}  # 每个URL上次使用时间
        
        # IP地区检测相关
        self.ignore_ip_check = True  # 默认忽略IP地区检查
        self.target_iso = "CN"  # 默认目标国家ISO代码
        self.target_country_name = "中国"  # 默认目标国家中文名
        self.ip_detector = None  # IP地区检测器
        self.country_mapper = get_mapper()
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """从配置管理器加载配置"""
        settings = self.config_manager.load_settings() or {}
        
        # 获取通用设置
        general_settings = settings.get("general", {})
        try:
            self.max_workers = int(general_settings.get("thread_count", 10))
        except (ValueError, TypeError):
            self.max_workers = 10
            
        # 加载IP地区检测设置
        self.ignore_ip_check = general_settings.get("ignore_ip_check", True)
        self.target_iso = general_settings.get("ip_country", "CN")
        # 确保目标ISO代码是标准化的
        if self.target_iso and isinstance(self.target_iso, str):
            self.target_iso = self.target_iso.strip().upper()
        # 获取相应的中文名称（仅用于显示）
        self.target_country_name = self.country_mapper.get_country_name(self.target_iso)
        
        # 获取代理检查器特定设置
        proxy_settings = settings.get("proxy", {})
        checker_settings = proxy_settings.get("checker", {})
        
        # 加载IP地区检测API
        ip_apis = checker_settings.get("ip_apis", [])
        if not ip_apis:
            # 使用默认API
            ip_apis = [{
                "url": "https://api.vore.top/api/IPdata",
                "country_path": "ipdata.info1",
                "cnip_path": "ipinfo.cnip",
                "supports_cors": True
            }]
            
        # 初始化IP地区检测器
        self.ip_detector = IPDetector(ip_apis)
        
        # 如果没有忽略IP地区检查，则使用IP API作为测试URL
        if not self.ignore_ip_check and ip_apis:
            self._test_urls = [api["url"] for api in ip_apis]
            self.check_url = ip_apis[0]["url"]
        else:
            # 否则使用常规测试URL
            custom_urls = checker_settings.get("test_urls", [])
            if custom_urls and isinstance(custom_urls, list) and len(custom_urls) > 0:
                self._test_urls = custom_urls
            else:
                # 如果配置中没有提供测试URL列表，则使用默认值
                self._test_urls = ["https://api.vore.top/api/IPdata"]
                
            self.check_url = self._test_urls[0]
        
        # 检查超时时间（秒）
        self.timeout = checker_settings.get("timeout", 10)
        
        # 检查重试次数
        self.max_retries = checker_settings.get("max_retries", 3)
        
        # 最大代理更换次数
        self.max_proxy_retries = checker_settings.get("max_proxy_retries", 5)
        
        # 初始化URL状态跟踪
        self._initialize_url_tracking()
    
    def _initialize_url_tracking(self):
        """初始化URL状态跟踪"""
        with self.lock:
            for url in self._test_urls:
                self._url_status[url] = True  # 初始状态为可用
                self._url_last_used[url] = 0  # 初始时间为0
                self._url_cooldown[url] = 0   # 初始冷却时间为0
            self._blocked_urls.clear()
    
    def _get_next_available_url(self) -> str:
        """获取下一个可用的测试URL
        
        Returns:
            str: 可用的测试URL
        """
        with self.lock:
            current_time = time.time()
            available_urls = []
            
            # 先检查是否有解除冷却的URL
            for url, cooldown_until in list(self._url_cooldown.items()):
                if current_time > cooldown_until and url in self._blocked_urls:
                    self._blocked_urls.remove(url)
                    self._url_status[url] = True
                    logger.info(f"测试URL已解除封禁: {url}")
            
            # 获取所有可用的URL
            for url in self._test_urls:
                if url not in self._blocked_urls and self._url_status.get(url, True):
                    available_urls.append(url)
            
            # 如果没有可用URL，则重置所有URL状态
            if not available_urls:
                logger.warning("所有测试URL都被标记为不可用，重置URL状态")
                self._initialize_url_tracking()
                available_urls = self._test_urls.copy()
            
            # 根据上次使用时间，优先选择使用较少的URL
            sorted_urls = sorted(available_urls, key=lambda u: self._url_last_used.get(u, 0))
            
            # 选择一个URL并更新使用时间
            selected_url = sorted_urls[0]
            self._url_last_used[selected_url] = current_time
            
            return selected_url
    
    def _mark_url_blocked(self, url: str, status_code: int = 0):
        """标记URL为被封禁
        
        Args:
            url: 被封禁的URL
            status_code: HTTP状态码
        """
        with self.lock:
            # 如果URL不在跟踪列表中，直接返回
            if url not in self._url_status:
                return
                
            self._url_status[url] = False
            self._blocked_urls.add(url)
            
            # 根据状态码设置不同的冷却时间
            cooldown_time = 60  # 默认冷却60秒
            if status_code == 429:  # Too Many Requests
                cooldown_time = 300  # 冷却5分钟
            elif status_code == 403:  # Forbidden
                cooldown_time = 600  # 冷却10分钟
            elif status_code == 503:  # Service Unavailable
                cooldown_time = 900  # 冷却15分钟
            
            cooldown_until = time.time() + cooldown_time
            self._url_cooldown[url] = cooldown_until
            
            logger.warning(f"测试URL被标记为暂时不可用 (状态码: {status_code}): {url}，冷却时间: {cooldown_time}秒")
    
    def format_proxy_url(self, proxy: Dict[str, Any]) -> Optional[str]:
        """格式化代理URL
        
        Args:
            proxy: 代理信息
            
        Returns:
            Optional[str]: 格式化后的代理URL，格式为 protocol://username:password@host:port
        """
        # 兼容两种字段命名 (host/ip, port)
        host = proxy.get("host") or proxy.get("ip")
        port = proxy.get("port")
        
        if not host or not port:
            return None
        
        protocol = proxy.get("protocol", "http").lower()
        username = proxy.get("username")
        password = proxy.get("password")
        
        # 构建代理URL
        if username and password:
            return f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            return f"{protocol}://{host}:{port}"
    
    def check_proxy(self, proxy: Dict[str, Any], test_url: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """检查单个代理是否可用（同步方法，内部调用异步实现）
        
        Args:
            proxy: 代理信息
            test_url: 测试URL，如果为None，则使用自动选择的URL
            
        Returns:
            Tuple[bool, Dict]: (是否可用, 结果详情)
        """
        # 使用事件循环运行异步方法
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # 在循环中运行异步方法
            return loop.run_until_complete(self.check_proxy_async(proxy, test_url))
        finally:
            # 关闭事件循环
            if loop:
                loop.close()
    
    def check_proxies_batch(self, 
                           proxies: List[Dict[str, Any]], 
                           callback: Optional[Callable[[Dict[str, Any], bool, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """批量检查代理是否可用（同步方法，内部调用异步实现）
        
        Args:
            proxies: 代理列表
            callback: 回调函数，用于处理检查结果，参数为(代理, 是否可用, 结果详情)
            
        Returns:
            Dict[str, Any]: 检查结果统计
        """
        # 同步回调转换为异步回调
        async_callback = callback
        if callback:
            # 如果提供了同步回调，创建一个异步包装器
            async def callback_wrapper(proxy, success, result):
                callback(proxy, success, result)
            async_callback = callback_wrapper
        
        # 使用事件循环运行异步方法
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # 在循环中运行异步方法
            return loop.run_until_complete(self.batch_check_async(proxies, async_callback))
        finally:
            # 关闭事件循环
            if loop:
                loop.close()
    
    def check_direct_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """检测直连（不使用代理）的可用性（同步方法，内部调用异步实现）
        
        Returns:
            Tuple[bool, Dict]: (是否有效, 检测结果详情)
        """
        # 使用事件循环运行异步检测
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # 在循环中运行异步方法
            return loop.run_until_complete(self.check_direct_connection_async())
        finally:
            # 关闭事件循环
            if loop:
                loop.close()
    
    async def _check_connection_async(self, test_url: Optional[str] = None, proxy_url: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """内部通用的连接检测方法，被代理检测和直连检测共用
        
        Args:
            test_url: 测试URL，如果为None则自动选择
            proxy_url: 代理URL，如果为None则表示直连
            
        Returns:
            Tuple[bool, Dict]: (是否成功, 结果详情)
        """
        # 如果未指定测试URL，则自动选择一个
        if not test_url:
            # 如果不忽略IP地区检查，并且有可用的IP检测API，则使用IP检测API
            if not self.ignore_ip_check and self.ip_detector and self.ip_detector.ip_apis:
                api_config = self.ip_detector.get_next_available_api()
                if api_config:
                    test_url = api_config.get("url")
            
            # 如果没有获取到IP检测API，则使用普通测试URL
            if not test_url:
                test_url = self._get_next_available_url()
                
        start_time = time.time()
        result = {
            'success': False,
            'response_time': 0,
            'error': None,
            'test_url': test_url,
            'country_code': None,
            'country_match': None,
            'ip': None,
            'country_name': None,
            'country_english_name': None
        }
        
        # 确定连接模式（代理或直连）
        is_proxy_mode = proxy_url is not None
        mode_str = "代理" if is_proxy_mode else "直连"
        
        try:
            # 创建ClientSession
            async with aiohttp.ClientSession() as session:
                # 为每次重试选择不同的URL
                for attempt in range(self.max_retries + 1):
                    try:
                        # 构建请求参数
                        request_kwargs = {
                            'timeout': self.timeout,
                            'headers': {'User-Agent': self.DEFAULT_USER_AGENT}
                        }
                        
                        # 如果是代理模式，添加代理参数
                        if is_proxy_mode:
                            request_kwargs['proxy'] = proxy_url
                            
                        # 发送请求
                        async with session.get(test_url, **request_kwargs) as response:
                            if response.status != 200:
                                # 检查是否遇到反爬状态码
                                if response.status in self.RATE_LIMIT_STATUS_CODES:
                                    # 检查是否是IP地区检测API
                                    is_ip_api = False
                                    if self.ip_detector:
                                        for api in self.ip_detector.ip_apis:
                                            if api.get("url") == test_url:
                                                is_ip_api = True
                                                self.ip_detector.update_api_state(test_url, False)
                                                break
                                    
                                    # 如果不是IP检测API，则标记URL为被封禁
                                    if not is_ip_api:
                                        self._mark_url_blocked(test_url, response.status)
                                    
                                    # 如果还有重试机会，则换一个URL重试
                                    if attempt < self.max_retries:
                                        new_test_url = self._get_next_test_url()
                                        if new_test_url:
                                            test_url = new_test_url
                                            result['test_url'] = test_url
                                            logger.debug(f"检测到可能的反爬限制，切换到新URL: {test_url}")
                                            await asyncio.sleep(1)  # 重试前等待一秒
                                            continue
                                
                                result['error'] = f"HTTP错误: {response.status}"
                                return False, result
                            
                            # 计算响应时间
                            result['response_time'] = round((time.time() - start_time) * 1000)  # 毫秒
                            
                            # 获取响应内容
                            try:
                                response_json = await response.json()
                                
                                # 尝试提取IP地址
                                try:
                                    # 查找匹配的API配置以获取ip_path
                                    api_config = None
                                    if self.ip_detector:
                                        for api in self.ip_detector.ip_apis:
                                            if api.get("url") == test_url:
                                                api_config = api
                                                break
                                    
                                    # 首先尝试使用配置的ip_path提取IP
                                    if api_config and "ip_path" in api_config and api_config["ip_path"]:
                                        ip_path = api_config["ip_path"]
                                        paths = ip_path.split(".")
                                        ip_value = response_json
                                        for path in paths:
                                            if isinstance(ip_value, dict) and path in ip_value:
                                                ip_value = ip_value[path]
                                            else:
                                                ip_value = None
                                                break
                                        
                                        if ip_value:
                                            result['ip'] = str(ip_value)
                                            logger.debug(f"使用配置的ip_path '{ip_path}' 成功提取IP: {result['ip']}")
                                    
                                    # 如果上面未提取到IP，则使用常见路径尝试提取（兼容旧代码）
                                    if 'ip' not in result or not result['ip']:
                                        if 'ipdata' in response_json and 'ip' in response_json['ipdata']:
                                            result['ip'] = response_json['ipdata']['ip']
                                        elif 'ipinfo' in response_json and 'ip' in response_json['ipinfo']:
                                            result['ip'] = response_json['ipinfo']['ip']
                                        elif 'ip' in response_json:
                                            result['ip'] = response_json['ip']
                                        elif 'ipAddress' in response_json:
                                            result['ip'] = response_json['ipAddress']
                                        elif 'ip_address' in response_json:
                                            result['ip'] = response_json['ip_address']
                                        elif 'query' in response_json:
                                            result['ip'] = response_json['query']
                                        elif 'ipv4' in response_json:
                                            result['ip'] = response_json['ipv4']
                                        elif 'IPV4' in response_json:
                                            result['ip'] = response_json['IPV4']
                                        elif 'IP' in response_json:
                                            result['ip'] = response_json['IP']
                                except Exception as e:
                                    logger.debug(f"提取IP地址时出错: {str(e)}")
                                    # 解析错误不影响连通性检测结果
                                
                                # 检查IP地区（如果需要）
                                if not self.ignore_ip_check and self.ip_detector:
                                    # 查找匹配的API配置
                                    api_config = None
                                    for api in self.ip_detector.ip_apis:
                                        if api.get("url") == test_url:
                                            api_config = api
                                            # 标记API调用成功
                                            self.ip_detector.update_api_state(test_url, True)
                                            break
                                    
                                    # 如果找到匹配的API配置，则提取国家代码
                                    if api_config:
                                        country_code = self.ip_detector.extract_country_code(response_json, api_config)
                                        result['country_code'] = country_code
                                        
                                        # 获取国家名称供显示
                                        if country_code:
                                            result['country_name'] = self.country_mapper.get_country_name(country_code)
                                            result['country_english_name'] = self.country_mapper.get_country_english_name(country_code)
                                            
                                            # 检查国家/地区是否匹配
                                            is_match = self.ip_detector.match_country_code(country_code, self.target_iso)
                                            result['country_match'] = is_match
                                            
                                            # 获取检测到的国家名称（用于日志显示）
                                            detected_name = self.country_mapper.get_country_name(country_code) or country_code
                                            
                                            # 日志记录更详细的匹配信息
                                            if is_match:
                                                logger.debug(f"{mode_str}IP地区匹配成功: 检测到 {country_code}({detected_name}), 目标国家 {self.target_iso}({self.target_country_name})")
                                            else:
                                                logger.debug(f"{mode_str}IP地区不匹配: 检测到 {country_code}({detected_name}), 目标国家 {self.target_iso}({self.target_country_name})")
                                                
                                            # 如果不匹配，且用户不忽略IP检查，则标记为失败
                                            if not is_match and not self.ignore_ip_check:
                                                result['success'] = False
                                                result['error'] = f"IP地区不匹配: {detected_name}({country_code})，期望: {self.target_country_name}({self.target_iso})"
                                                return False, result
                                        # 如果未忽略IP检查但无法获取国家代码，则也标记为失败
                                        elif not self.ignore_ip_check:
                                            logger.debug(f"{mode_str}IP地区检测失败: 无法获取IP所在地信息")
                                            result['success'] = False
                                            result['error'] = "无法获取IP所在地信息，检测失败"
                                            return False, result
                            except Exception as e:
                                logger.debug(f"处理响应JSON时出错: {str(e)}")
                                # 解析错误不影响连通性检测结果
                            
                            result['success'] = True
                            logger.debug(f"{mode_str}检查成功: {proxy_url or '直连'}, 响应时间: {result['response_time']}ms, URL: {test_url}")
                            return True, result
                            
                    except asyncio.TimeoutError:
                        result['error'] = "连接超时"
                    except aiohttp.ClientProxyConnectionError:
                        result['error'] = "代理连接错误"
                        # 代理错误是致命问题，无需继续尝试
                        if is_proxy_mode:
                            return False, result
                    except aiohttp.ClientSSLError:
                        result['error'] = "SSL错误"
                    except Exception as e:
                        # 处理IP检测API可能的失败
                        is_ip_api = False
                        if self.ip_detector:
                            for api in self.ip_detector.ip_apis:
                                if api.get("url") == test_url:
                                    is_ip_api = True
                                    self.ip_detector.update_api_state(test_url, False)
                                    break
                        
                        # 检查错误消息中是否包含反爬相关关键词
                        error_str = str(e).lower()
                        if any(kw in error_str for kw in ["forbidden", "too many requests", "rate limit", "blocked", "banned"]):
                            if not is_ip_api:
                                self._mark_url_blocked(test_url)
                            
                            # 如果还有重试机会，则换一个URL重试
                            if attempt < self.max_retries:
                                new_test_url = self._get_next_test_url()
                                if new_test_url:
                                    test_url = new_test_url
                                    result['test_url'] = test_url
                                    logger.debug(f"检测到可能的反爬限制，切换到新URL: {test_url}")
                                    await asyncio.sleep(1)  # 重试前等待一秒
                                    continue
                        
                        result['error'] = f"未知错误: {str(e)}"
                    
                    # 如果还有重试机会，则等待后重试
                    if attempt < self.max_retries:
                        await asyncio.sleep(1)  # 重试前等待一秒
                
        except Exception as e:
            result['error'] = f"未知错误: {str(e)}"
            
        logger.debug(f"{mode_str}检查失败: {proxy_url or '直连'}, {result['error']}, URL: {test_url}")
        return False, result
    
    def _get_next_test_url(self) -> Optional[str]:
        """获取下一个可用的测试URL，兼顾IP检测API和普通URL"""
        # 如果不忽略IP地区检查，优先使用IP检测API
        if not self.ignore_ip_check and self.ip_detector:
            api_config = self.ip_detector.get_next_available_api()
            if api_config:
                return api_config.get("url")
        
        # 如果没有可用的IP检测API，则使用普通URL
        return self._get_next_available_url()
        
    async def check_proxy_async(self, proxy: Dict[str, Any], test_url: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """异步检测代理的有效性
        
        Args:
            proxy: 代理信息字典
            test_url: 测试URL，如果为None则使用自动选择的URL
            
        Returns:
            Tuple[bool, Dict]: (是否有效, 检测结果详情)
        """
        # 格式化代理URL
        proxy_url = self.format_proxy_url(proxy)
        if not proxy_url:
            return False, {'success': False, 'error': "代理格式无效"}
            
        # 调用通用检测方法
        return await self._check_connection_async(test_url, proxy_url)
        
    async def check_direct_connection_async(self, test_url: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """异步检测直连的有效性
        
        Args:
            test_url: 测试URL，如果为None则使用自动选择的URL
            
        Returns:
            Tuple[bool, Dict]: (是否有效, 检测结果详情)
        """
        # 调用通用检测方法，不提供代理URL表示直连
        return await self._check_connection_async(test_url, None)
    
    async def batch_check_async(self, 
                              proxies: List[Dict[str, Any]], 
                              callback: Optional[Callable[[Dict[str, Any], bool, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """异步批量检测多个代理
        
        Args:
            proxies: 代理列表
            callback: 回调函数，用于处理检查结果
            
        Returns:
            Dict[str, Any]: 检查结果统计
        """
        if not proxies:
            return {"total": 0, "available": 0, "unavailable": 0}
            
        results = {
            "total": len(proxies),
            "available": 0,
            "unavailable": 0,
            "avg_response_time": 0,
            "country_matched": 0,  # 新增：匹配目标国家的代理数量
            "country_mismatched": 0  # 新增：不匹配目标国家的代理数量
        }
        
        # 计算每个批次的大小
        batch_size = min(len(proxies), max(5, min(20, self.max_workers)))
        
        # 创建URL分组
        url_groups = self._create_url_groups(min(len(proxies), self.max_workers))
        
        # 总响应时间和可用代理计数
        total_response_time = 0
        available_count = 0
        
        # 按批次处理代理
        for i in range(0, len(proxies), batch_size):
            batch_proxies = proxies[i:i+batch_size]
            
            # 使用配置的max_workers作为并发控制参数，但不超过当前批次大小
            semaphore = asyncio.Semaphore(min(self.max_workers, len(batch_proxies)))
            
            async def _check_with_semaphore(proxy, test_url):
                async with semaphore:
                    # 添加随机延迟，使请求模式更自然
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    
                    # 检查代理，最多尝试max_retries次
                    for retry in range(self.max_retries):
                        success, result = await self.check_proxy_async(proxy, test_url)
                        
                        # 如果连通性测试成功，或者失败原因不是代理问题，则返回结果
                        if success or (not success and "代理连接错误" not in result.get('error', '')):
                            # 如果是IP地区不匹配导致的失败，记录相关统计
                            if not success and "IP地区不匹配" in result.get('error', ''):
                                result['ip_region_mismatch'] = True
                            return proxy, success, result
                        
                        # 如果是代理问题导致的失败，则获取新的代理重试
                        logger.debug(f"代理连接失败，跳过重试并返回失败结果")
                        break
                    
                    # 达到最大重试次数，返回最后一次的结果
                    return proxy, success, result
            
            # 为每个代理分配一个测试URL
            tasks = []
            for idx, proxy in enumerate(batch_proxies):
                # 优先使用IP检测API（如果需要检测IP地区）
                if not self.ignore_ip_check and self.ip_detector and self.ip_detector.ip_apis:
                    api_config = self.ip_detector.get_next_available_api()
                    if api_config:
                        test_url = api_config.get("url")
                        tasks.append(_check_with_semaphore(proxy, test_url))
                        continue
                
                # 如果不需要检测IP地区或没有可用的IP检测API，则使用普通测试URL
                group_idx = idx % len(url_groups)
                test_url = random.choice(url_groups[group_idx])
                tasks.append(_check_with_semaphore(proxy, test_url))
            
            # 执行批次任务
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果统计
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"代理检测异常: {str(result)}")
                    results["unavailable"] += 1
                    continue
                    
                _, success, check_result = result
                if success:
                    results["available"] += 1
                    available_count += 1
                    if 'response_time' in check_result:
                        total_response_time += check_result['response_time']
                    
                    # 记录国家匹配情况
                    if 'country_match' in check_result:
                        if check_result['country_match']:
                            results["country_matched"] += 1
                            logger.debug(f"统计: 匹配目标国家的代理 +1 (当前: {results['country_matched']}) "
                                         f"[{check_result.get('country_code')}({check_result.get('country_name')})]")
                else:
                    results["unavailable"] += 1
                    # 记录国家不匹配情况 - 仅在错误原因是"IP地区不匹配"时才计数
                    if 'error' in check_result and "IP地区不匹配" in check_result.get('error', ''):
                        results["country_mismatched"] += 1
                        logger.debug(f"统计: 不匹配目标国家的代理 +1 (当前: {results['country_mismatched']}) "
                                     f"[{check_result.get('country_code')}({check_result.get('country_name')})]")
                
                # 执行回调（如果有）
                if callback:
                    try:
                        await callback(_, success, check_result)
                    except Exception as e:
                        logger.error(f"执行回调函数时出错: {str(e)}")
            
            # 批次之间添加短暂延迟，避免触发反爬
            await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # 计算平均响应时间
        if available_count > 0:
            results["avg_response_time"] = round(total_response_time / available_count)
            
        return results
    
    def _create_url_groups(self, group_count: int) -> List[List[str]]:
        """创建URL分组，用于批量检查时分配不同的URL
        
        Args:
            group_count: 分组数量
            
        Returns:
            List[List[str]]: URL分组列表
        """
        with self.lock:
            # 获取可用的URL列表
            available_urls = [url for url in self._test_urls if url not in self._blocked_urls]
            if not available_urls:
                # 如果没有可用URL，重置状态并使用所有URL
                logger.warning("没有可用的测试URL，重置URL状态")
                self._initialize_url_tracking()
                available_urls = self._test_urls.copy()
            
            # 确保至少有一个URL可用
            if not available_urls:
                available_urls = ["https://api.vore.top/api/IPdata"]
            
            # 创建分组
            groups = []
            for _ in range(group_count):
                # 每个组至少包含一个URL，如果可用URL数量少于组数，则重复使用
                if len(available_urls) >= group_count:
                    # 随机选择不重复的URL
                    group_urls = random.sample(available_urls, min(3, len(available_urls)))
                else:
                    # 随机选择URLs，可能有重复
                    group_urls = [random.choice(available_urls) for _ in range(min(3, len(available_urls)))]
                
                groups.append(group_urls)
            
            return groups
    
    def update_test_urls(self, urls: List[str]) -> None:
        """更新测试URL列表
        
        Args:
            urls: 新的测试URL列表
        """
        with self.lock:
            if urls:
                self._test_urls = urls
                # 同时更新检查URL
                self.check_url = urls[0]
                # 重置URL状态跟踪
                self._initialize_url_tracking()
                logger.info(f"更新测试URL列表: {len(urls)}个URL")
    
    def add_test_url(self, url: str) -> None:
        """添加测试URL
        
        Args:
            url: 测试URL
        """
        with self.lock:
            if url and url not in self._test_urls:
                self._test_urls.append(url)
                # 初始化新URL的状态跟踪
                self._url_status[url] = True
                self._url_last_used[url] = 0
                self._url_cooldown[url] = 0
                logger.info(f"添加测试URL: {url}")
    
    def remove_test_url(self, url: str) -> bool:
        """移除测试URL
        
        Args:
            url: 测试URL
            
        Returns:
            bool: 是否成功移除
        """
        with self.lock:
            if url in self._test_urls:
                self._test_urls.remove(url)
                # 清理URL状态跟踪
                if url in self._url_status:
                    del self._url_status[url]
                if url in self._url_last_used:
                    del self._url_last_used[url]
                if url in self._url_cooldown:
                    del self._url_cooldown[url]
                if url in self._blocked_urls:
                    self._blocked_urls.remove(url)
                
                # 如果移除的是当前检查URL，则更新检查URL
                if url == self.check_url and self._test_urls:
                    self.check_url = self._test_urls[0]
                logger.info(f"移除测试URL: {url}")
                return True
            return False
    
    def get_test_urls(self) -> List[str]:
        """获取测试URL列表
        
        Returns:
            List[str]: 测试URL列表
        """
        with self.lock:
            return self._test_urls.copy()
    
    def get_url_status(self) -> Dict[str, Dict[str, Any]]:
        """获取每个URL的状态信息
        
        Returns:
            Dict: URL状态信息，包括是否可用、冷却时间等
        """
        with self.lock:
            current_time = time.time()
            status = {}
            
            for url in self._test_urls:
                remaining_cooldown = max(0, self._url_cooldown.get(url, 0) - current_time)
                status[url] = {
                    'available': url not in self._blocked_urls,
                    'cooldown_remaining': round(remaining_cooldown),
                    'last_used': round(current_time - self._url_last_used.get(url, 0))
                }
            
            return status
    
    def set_timeout(self, timeout: int) -> None:
        """设置检查超时时间
        
        Args:
            timeout: 超时时间（秒）
        """
        with self.lock:
            self.timeout = max(1, timeout)
            logger.info(f"设置代理检查超时时间: {self.timeout}秒")
    
    def set_max_retries(self, max_retries: int) -> None:
        """设置检查重试次数
        
        Args:
            max_retries: 重试次数
        """
        with self.lock:
            self.max_retries = max(0, max_retries)
            logger.info(f"设置代理检查重试次数: {self.max_retries}") 