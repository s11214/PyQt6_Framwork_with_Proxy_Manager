from typing import List, Dict, Any, Tuple, Optional
from . import ProxySource
from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
from src.core.proxy.proxy_checker import ProxyChecker

logger = get_logger()

class DirectConnectionSource(ProxySource):
    """直连代理来源实现类（不使用代理）"""
    
    def __init__(self):
        """初始化直连代理来源"""
        self.config_manager = ConfigManager()
        self.proxy_checker = ProxyChecker(self.config_manager)
        self._cached_check_result = None
    
    @property
    def source_type(self) -> str:
        """获取代理来源类型"""
        return "direct"
    
    def _get_direct_config(self) -> Dict[str, Any]:
        """获取直连配置
        
        Returns:
            Dict: 直连配置
        """
        settings = self.config_manager.load_settings() or {}
        proxy_settings = settings.get("proxy", {})
        direct_settings = proxy_settings.get("direct", {})
        
        return direct_settings
    
    def check_availability(self) -> Tuple[bool, str]:
        """检查直连是否可用
        
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        try:
            # 检测直连是否可用
            success, check_result = self.proxy_checker.check_direct_connection()
            
            # 缓存检测结果
            self._cached_check_result = check_result
            
            if success:
                # 获取响应时间
                response_time = check_result.get('response_time', 0)
                # 获取IP
                ip = check_result.get('ip', 'unknown')
                # 获取国家/地区信息(如果有)
                country_info = ""
                if check_result.get('country_code'):
                    country_code = check_result.get('country_code')
                    country_name = check_result.get('country_name') or self.proxy_checker.country_mapper.get_country_name(country_code)
                    country_info = f"，所在地: {country_name}({country_code})"
                
                return True, f"直连可用，响应时间: {response_time}ms，IP: {ip}{country_info}"
            else:
                error = check_result.get('error', '未知错误')
                return False, f"直连不可用: {error}"
                
        except Exception as e:
            return False, f"检测直连失败: {str(e)}"
    
    def get_proxies(self, count: int) -> List[Dict[str, Any]]:
        """获取直连代理（实际上不使用代理）
        
        Args:
            count: 需要获取的代理数量（对于直连模式忽略此参数）
            
        Returns:
            List[Dict]: 空列表，表示不使用代理
        """
        try:
            success, check_result = self.proxy_checker.check_direct_connection()
            if not success:
                error = check_result.get('error', '未知错误')
                logger.error(f"直连不可用: {error}")
                return []
            
        except Exception as e:
            logger.error(f"检测直连失败: {str(e)}")
            return []
        
        # 对于直连模式，返回空列表，表示不使用代理
        # 无论请求多少个，都不使用代理
        return []
        
    def get_direct_ip(self) -> Optional[str]:
        """获取直连的IP地址
        
        Returns:
            Optional[str]: IP地址，如果未检测则返回None
        """
        if self._cached_check_result:
            return self._cached_check_result.get('ip')
        return None 