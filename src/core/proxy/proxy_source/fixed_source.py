from typing import List, Dict, Any, Tuple, Optional
from . import ProxySource
from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
from src.core.proxy.proxy_checker import ProxyChecker

logger = get_logger()

class FixedProxySource(ProxySource):
    """固定代理来源实现类"""
    
    def __init__(self):
        """初始化固定代理来源"""
        self.config_manager = ConfigManager()
        self.proxy_checker = ProxyChecker(self.config_manager)
        self._cached_proxy = None
        self._cached_check_result = None
    
    @property
    def source_type(self) -> str:
        """获取代理来源类型"""
        return "fixed"
    
    def _get_fixed_proxy_config(self) -> Dict[str, Any]:
        """获取固定代理配置
        
        Returns:
            Dict: 固定代理配置
        """
        settings = self.config_manager.load_settings() or {}
        proxy_settings = settings.get("proxy", {})
        fixed_settings = proxy_settings.get("fixed", {})
        
        return {
            "proxy_type": fixed_settings.get("proxy_type", "HTTP"),
            "host": fixed_settings.get("host", ""),
            "port": fixed_settings.get("port", ""),
            "username": fixed_settings.get("username", ""),
            "password": fixed_settings.get("password", "")
        }
    
    def check_availability(self) -> Tuple[bool, str]:
        """检查固定代理是否可用
        
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        config = self._get_fixed_proxy_config()
        host = config.get("host")
        port = config.get("port")
        
        if not host or not port:
            return False, "固定代理未配置"
            
        try:
            # 创建代理对象
            proxy = {
                'host': host,
                'port': port,
                'protocol': config.get("proxy_type", "HTTP").lower(),
                'username': config.get("username"),
                'password': config.get("password")
            }
            
            # 检测代理是否可用
            success, check_result = self.proxy_checker.check_proxy(proxy)
            
            # 缓存检测结果
            self._cached_proxy = proxy
            self._cached_check_result = check_result
            
            if success:
                # 获取响应时间
                response_time = check_result.get('response_time', 0)
                # 判断是否匿名
                is_anonymous = check_result.get('anonymous', False)
                # 获取国家/地区信息(如果有)
                country_info = ""
                if check_result.get('country_code'):
                    country_code = check_result.get('country_code')
                    country_name = check_result.get('country_name') or self.proxy_checker.country_mapper.get_country_name(country_code)
                    country_info = f"，所在地: {country_name}({country_code})"
                
                return True, f"固定代理可用，响应时间: {response_time}ms，匿名性: {'匿名' if is_anonymous else '透明'}{country_info}"
            else:
                error = check_result.get('error', '未知错误')
                return False, f"固定代理不可用: {error}"
                
        except Exception as e:
            return False, f"检测固定代理失败: {str(e)}"
    
    def get_proxies(self, count: int) -> List[Dict[str, Any]]:
        """获取固定代理
        
        注意：无论请求多少个代理，固定代理来源始终只返回一个代理
        
        Args:
            count: 需要获取的代理数量（对于固定代理忽略此参数）
            
        Returns:
            List[Dict]: 包含一个固定代理的列表
        """
        config = self._get_fixed_proxy_config()
        host = config.get("host")
        port = config.get("port")
        
        if not host or not port:
            logger.error("固定代理未配置")
            return []
            
        # 创建代理对象
        proxy = {
            'host': host,
            'port': port,
            'protocol': config.get("proxy_type", "HTTP").lower(),
            'username': config.get("username"),
            'password': config.get("password"),
            'source': 'FIXED'
        }
        
        # 如果没有缓存的检测结果，则进行检测
        if self._cached_proxy is None or self._cached_check_result is None:
            try:
                success, check_result = self.proxy_checker.check_proxy(proxy)
                if not success:
                    error = check_result.get('error', '未知错误')
                    logger.error(f"固定代理不可用: {error}")
                    return []
            except Exception as e:
                logger.error(f"检测固定代理失败: {str(e)}")
                return []
                
        # 返回固定代理，对于固定代理来源只返回一个代理
        # 无论请求多少个，其余任务将共享此代理
        return [proxy] 