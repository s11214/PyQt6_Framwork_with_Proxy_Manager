from typing import List, Dict, Any, Tuple, Optional
from . import ProxySource
from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
from src.core.proxy.imported_proxy_pool import ImportedProxyPool

logger = get_logger()

class ImportedProxySource(ProxySource):
    """导入代理来源实现类"""
    
    def __init__(self):
        """初始化导入代理来源"""
        self.config_manager = ConfigManager()
        self.proxy_pool = ImportedProxyPool()
    
    @property
    def source_type(self) -> str:
        """获取代理来源类型"""
        return "import"
    
    def _get_import_config(self) -> Dict[str, Any]:
        """获取导入代理配置
        
        Returns:
            Dict: 导入代理配置
        """
        settings = self.config_manager.load_settings() or {}
        proxy_settings = settings.get("proxy", {})
        import_settings = proxy_settings.get("pool", {})
        
        return {
            "allow_reuse": import_settings.get("allow_reuse", True)
        }
    
    def check_availability(self) -> Tuple[bool, str]:
        """检查导入代理池是否可用
        
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        try:
            # 获取代理池中的代理数量
            proxies = self.proxy_pool.get_proxies()
            
            if not proxies:
                return False, "导入代理池为空"
                
            # 获取配置中是否允许重复使用
            config = self._get_import_config()
            allow_reuse = config.get("allow_reuse", True)
            
            # 检查可用的代理数量
            available_count = 0
            if allow_reuse:
                # 如果允许重复使用，则所有代理都可用
                available_count = len(proxies)
            else:
                # 如果不允许重复使用，则只有未使用的代理可用
                available_count = sum(1 for p in proxies if p.get('status') != 'used')
            
            if available_count == 0:
                return False, "导入代理池中没有可用代理"
                
            return True, f"导入代理池可用，共有 {available_count} 个可用代理"
            
        except Exception as e:
            return False, f"检查导入代理池失败: {str(e)}"
    
    def get_proxies(self, count: int) -> List[Dict[str, Any]]:
        """从导入代理池获取指定数量的代理
        
        Args:
            count: 需要获取的代理数量
            
        Returns:
            List[Dict]: 代理列表
        """
        # 获取配置中是否允许重复使用
        config = self._get_import_config()
        allow_reuse = config.get("allow_reuse", True)
        
        # 获取IP所在地检查配置
        settings = self.config_manager.load_settings() or {}
        general_settings = settings.get("general", {})
        ignore_ip_check = general_settings.get("ignore_ip_check", True)
        target_iso = general_settings.get("ip_country", "")
        
        try:
            # 获取代理池中的所有代理
            all_proxies = self.proxy_pool.get_proxies()
            
            # 筛选可用代理
            available_proxies = []
            if allow_reuse:
                # 如果允许重复使用，则所有代理都可用，但需要确保同一批次内唯一
                # 我们可以复制一份代理列表，避免修改原列表
                available_proxies = all_proxies.copy()
            else:
                # 如果不允许重复使用，则只获取未使用的代理
                available_proxies = [p for p in all_proxies if p.get('status') != 'used']
            
            # 如果需要检查IP所在地，则筛选出符合要求的代理
            if not ignore_ip_check and target_iso:
                # 仅保留与目标国家/地区匹配的代理
                country_filtered_proxies = []
                for proxy in available_proxies:
                    proxy_country = proxy.get('country', '')
                    if proxy_country and (proxy_country == target_iso or self._is_country_match(proxy_country, target_iso)):
                        country_filtered_proxies.append(proxy)
                
                logger.info(f"根据国家/地区筛选: 目标={target_iso}, 匹配数量={len(country_filtered_proxies)}/{len(available_proxies)}")
                available_proxies = country_filtered_proxies
            
            # 如果可用代理不足，则记录警告
            if len(available_proxies) < count:
                logger.warning(f"导入代理池中的可用代理数量({len(available_proxies)})不足，请求数量为{count}")
            
            # 最多获取可用数量和请求数量中的较小值
            actual_count = min(len(available_proxies), count)
            selected_proxies = available_proxies[:actual_count]
            
            # 如果不允许重复使用，则标记为已使用
            if not allow_reuse:
                for proxy in selected_proxies:
                    self.proxy_pool.update_proxy_status(proxy['id'], 'used')
            
            # 转换为统一格式
            result = []
            for proxy in selected_proxies:
                result.append({
                    'host': proxy.get('host'),
                    'port': proxy.get('port'),
                    'protocol': proxy.get('proxy_type', 'http').lower(),
                    'username': proxy.get('username'),
                    'password': proxy.get('password'),
                    'source': 'IMPORT',
                    'original_id': proxy.get('id'),  # 保存原始ID，便于后续处理
                    'country': proxy.get('country', '')  # 保留国家/地区信息
                })
            
            logger.info(f"从导入代理池获取了 {len(result)} 个代理")
            return result
            
        except Exception as e:
            logger.error(f"从导入代理池获取代理失败: {str(e)}")
            return []
            
    def _is_country_match(self, proxy_country: str, target_iso: str) -> bool:
        """检查代理的国家/地区是否与目标国家/地区匹配
        
        Args:
            proxy_country: 代理的国家/地区代码
            target_iso: 目标国家/地区代码
            
        Returns:
            bool: 是否匹配
        """
        # 标准化国家/地区代码
        proxy_country = proxy_country.upper()
        target_iso = target_iso.upper()
        
        # 直接相等时匹配
        if proxy_country == target_iso:
            return True
            
        # 特殊处理中国大陆与港澳台地区
        # 如果目标是中国大陆(CN)，检测到的是港澳台(HK/TW/MO)，则不匹配
        if target_iso == 'CN' and proxy_country in ['HK', 'TW', 'MO']:
            return False
            
        # 如果目标是港澳台(HK/TW/MO)，检测到的是中国大陆(CN)，则不匹配
        if target_iso in ['HK', 'TW', 'MO'] and proxy_country == 'CN':
            return False
            
        # 其他情况，考虑简单的别名匹配
        country_aliases = {
            'CN': ['CHINA', 'MAINLAND', 'ZHONGGUO'],
            'US': ['USA', 'AMERICA', 'UNITED STATES'],
            'GB': ['UK', 'UNITED KINGDOM', 'ENGLAND'],
            'HK': ['HONG KONG', 'HONGKONG'],
            'TW': ['TAIWAN'],
            'MO': ['MACAO', 'MACAU']
        }
        
        # 检查代理国家是否在目标国家的别名列表中
        if target_iso in country_aliases and proxy_country in country_aliases[target_iso]:
            return True
            
        # 反向检查目标国家是否在代理国家的别名列表中
        for code, aliases in country_aliases.items():
            if proxy_country == code and target_iso in aliases:
                return True
                
        return False 