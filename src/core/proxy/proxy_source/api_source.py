import requests
import time
from typing import List, Dict, Any, Tuple, Optional
from . import ProxySource
from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger()

class ApiProxySource(ProxySource):
    """API代理来源实现类"""
    
    def __init__(self):
        """初始化API代理来源"""
        self.config_manager = ConfigManager()
        self._last_call_time = 0
        self._call_interval = 2  # 默认API调用间隔（秒）
    
    @property
    def source_type(self) -> str:
        """获取代理来源类型"""
        return "api"
    
    def _get_api_config(self) -> Dict[str, Any]:
        """获取API配置
        
        Returns:
            Dict: API配置
        """
        settings = self.config_manager.load_settings() or {}
        proxy_settings = settings.get("proxy", {})
        api_settings = proxy_settings.get("api", {})
        
        return {
            "api_url": api_settings.get("api_url", ""),
            "proxy_type": api_settings.get("type", "HTTP")
        }
    
    def check_availability(self) -> Tuple[bool, str]:
        """检查API来源是否可用
        
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        api_config = self._get_api_config()
        api_url = api_config.get("api_url")
        
        if not api_url:
            return False, "API URL未配置"
            
        try:
            # 尝试调用API获取一个代理，验证API可用性
            response = self._call_api(api_url)
            
            if not response or not self._parse_api_response(response):
                return False, "API返回无效数据"
                
            return True, "API可用"
            
        except requests.exceptions.RequestException as e:
            return False, f"API请求失败: {str(e)}"
        except Exception as e:
            return False, f"API检查失败: {str(e)}"
    
    def get_proxies(self, count: int) -> List[Dict[str, Any]]:
        """从API获取指定数量的代理
        
        Args:
            count: 需要获取的代理数量
            
        Returns:
            List[Dict]: 代理列表
        """
        api_config = self._get_api_config()
        api_url = api_config.get("api_url")
        proxy_type = api_config.get("proxy_type")
        
        if not api_url:
            logger.error("API URL未配置")
            return []
            
        # 获取的代理列表
        proxies = []
        # 已尝试获取的次数
        attempts = 0
        # 最大尝试次数（预防无限循环）
        max_attempts = max(10, min(100, int(count * 0.5) + 10))
        
        # 循环获取代理，直到数量满足要求或达到最大尝试次数
        while len(proxies) < count and attempts < max_attempts:
            try:
                # 限制API调用频率
                self._respect_rate_limit()
                
                # 调用API
                response = self._call_api(api_url)
                if not response:
                    logger.error("API调用失败")
                    attempts += 1
                    continue
                    
                # 解析响应
                batch_proxies = self._parse_api_response(response)
                if not batch_proxies:
                    logger.error("解析API响应失败")
                    attempts += 1
                    continue
                    
                # 格式化并添加代理
                for proxy_data in batch_proxies:
                    # 跳过已存在的代理（去重）
                    if self._is_duplicate(proxy_data, proxies):
                        continue
                        
                    proxy = self._format_proxy(proxy_data, proxy_type)
                    if proxy:
                        proxies.append(proxy)
                        
                        # 如果已经获取到足够数量的代理，则跳出循环
                        if len(proxies) >= count:
                            break
                
                # 增加尝试次数
                attempts += 1
                
            except Exception as e:
                logger.error(f"获取代理时出错: {str(e)}")
                attempts += 1
                # 出错时暂停一秒
                time.sleep(1)
        
        logger.info(f"从API获取了 {len(proxies)} 个代理")
        return proxies[:int(count)]  # 返回最多count个代理，确保count是整数
    
    def _respect_rate_limit(self):
        """尊重API调用频率限制"""
        current_time = time.time()
        elapsed = current_time - self._last_call_time
        
        if elapsed < self._call_interval:
            # 如果距离上次调用时间不足，则等待
            time.sleep(self._call_interval - elapsed)
            
        # 更新最后调用时间
        self._last_call_time = time.time()
    
    def _call_api(self, api_url: str) -> Optional[Dict[str, Any]]:
        """调用API获取代理
        
        Args:
            api_url: API URL
            
        Returns:
            Optional[Dict]: API响应，失败时返回None
        """
        try:
            response = requests.get(
                api_url, 
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            if response.status_code != 200:
                logger.error(f"API请求失败，状态码: {response.status_code}")
                return None
                
            # 尝试解析JSON响应
            try:
                return response.json()
            except ValueError:
                # 如果不是JSON，则返回文本内容
                return {"text": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求异常: {str(e)}")
            return None
    
    def _parse_api_response(self, response: Any) -> List[Dict[str, Any]]:
        """解析API响应，提取代理信息
        
        Args:
            response: API响应
            
        Returns:
            List[Dict]: 解析后的代理列表
        """
        # 如果响应不是字典类型，尝试解析文本
        if not isinstance(response, dict):
            if isinstance(response, str):
                return self._parse_text_response(response)
            return []
            
        # 检查错误信息
        error_msg = None
        if 'msg' in response:
            error_msg = response['msg']
        elif 'message' in response:
            error_msg = response['message']
        
        # 检查IP白名单错误
        if error_msg and ('whitelist' in error_msg.lower() or 'not in whitelist' in error_msg.lower()):
            request_ip = response.get('request_ip') or response.get('ip')
            logger.error(f"IP未加入白名单: {request_ip}")
            return []
        
        # 检查成功状态
        success = True  # 默认为成功，除非明确指出失败
        if 'code' in response:
            success = response['code'] == 0
        elif 'Code' in response:
            success = response['Code'] == 0
        elif 'success' in response:
            success = response['success'] is True
        
        if not success:
            logger.error(f"API请求失败: {error_msg or '未知错误'}")
            return []
        
        # 获取代理数据
        proxy_list = []
        
        # 尝试从不同字段获取代理列表
        if 'data' in response and isinstance(response['data'], list):
            proxy_list = response['data']
        elif 'Data' in response and isinstance(response['Data'], list):
            proxy_list = response['Data']
        elif 'proxies' in response and isinstance(response['proxies'], list):
            proxy_list = response['proxies']
        elif 'result' in response and isinstance(response['result'], list):
            proxy_list = response['result']
        elif 'text' in response:
            # 尝试解析文本格式
            return self._parse_text_response(response['text'])
            
        # 如果无法从常见字段获取代理列表，尝试遍历所有元素
        if not proxy_list:
            for key, value in response.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and self._is_proxy_item(item):
                            proxy_list.append(item)
        
        if not proxy_list:
            logger.error("API返回的代理列表为空")
            
        return proxy_list
    
    def _parse_text_response(self, text: str) -> List[Dict[str, Any]]:
        """解析文本格式的API响应
        
        Args:
            text: 文本响应
            
        Returns:
            List[Dict]: 解析后的代理列表
        """
        result = []
        
        # 按行分割
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 尝试按照常见格式解析
            # 格式1: ip:port
            # 格式2: ip:port:username:password
            parts = line.split(':')
            if len(parts) >= 2:
                proxy_data = {
                    "ip": parts[0],
                    "port": parts[1]
                }
                
                # 如果有用户名密码
                if len(parts) >= 4:
                    proxy_data["username"] = parts[2]
                    proxy_data["password"] = parts[3]
                    
                result.append(proxy_data)
        
        return result
    
    def _is_proxy_item(self, item: Dict[str, Any]) -> bool:
        """检查字典是否像是代理项
        
        Args:
            item: 字典对象
            
        Returns:
            bool: 是否是代理项
        """
        # 检查是否包含代理常见字段
        has_ip = any(key for key in item if key.lower() in ('ip', 'host', 'addr', 'address'))
        has_port = any(key for key in item if key.lower() in ('port', 'p'))
        
        # 如果同时包含IP和端口字段，则认为是代理项
        return has_ip and has_port
    
    def _format_proxy(self, proxy_data: Dict[str, Any], proxy_type: str) -> Optional[Dict[str, Any]]:
        """格式化代理数据
        
        Args:
            proxy_data: 原始代理数据
            proxy_type: 代理类型
            
        Returns:
            Optional[Dict]: 格式化后的代理，无效数据返回None
        """
        # 提取代理IP
        host = None
        for key in ('ip', 'host', 'addr', 'address'):
            if key in proxy_data:
                host = proxy_data[key]
                break
                
        # 提取代理端口
        port = None
        for key in ('port', 'p'):
            if key in proxy_data:
                port = proxy_data[key]
                break
                
        # 如果没有IP或端口，则判定为无效代理
        if not host or not port:
            return None
            
        # 提取用户名和密码（如果有）
        username = None
        password = None
        for u_key in ('username', 'user', 'login'):
            if u_key in proxy_data:
                username = proxy_data[u_key]
                break
                
        for p_key in ('password', 'pass', 'pwd'):
            if p_key in proxy_data:
                password = proxy_data[p_key]
                break
                
        # 格式化代理数据
        return {
            'host': host,
            'port': port,
            'protocol': proxy_type.lower(),
            'username': username,
            'password': password,
            'source': 'API'
        }
    
    def _is_duplicate(self, proxy_data: Dict[str, Any], proxies: List[Dict[str, Any]]) -> bool:
        """检查代理是否重复
        
        Args:
            proxy_data: 代理数据
            proxies: 已有代理列表
            
        Returns:
            bool: 是否重复
        """
        # 提取代理IP和端口
        host = None
        for key in ('ip', 'host', 'addr', 'address'):
            if key in proxy_data:
                host = proxy_data[key]
                break
                
        port = None
        for key in ('port', 'p'):
            if key in proxy_data:
                port = proxy_data[key]
                break
                
        # 如果没有IP或端口，无法判断重复
        if not host or not port:
            return False
            
        # 检查是否与已有代理重复
        for proxy in proxies:
            if proxy.get('host') == host and str(proxy.get('port')) == str(port):
                return True
                
        return False 