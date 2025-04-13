from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

class ProxySource(ABC):
    """代理来源抽象基类"""
    
    @abstractmethod
    def get_proxies(self, count: int) -> List[Dict[str, Any]]:
        """获取指定数量的代理
        
        Args:
            count: 需要获取的代理数量
            
        Returns:
            List[Dict]: 代理列表
        """
        pass
    
    @abstractmethod
    def check_availability(self) -> Tuple[bool, str]:
        """检查代理来源是否可用
        
        Returns:
            Tuple[bool, str]: (是否可用, 错误信息)
        """
        pass
        
    @property
    @abstractmethod
    def source_type(self) -> str:
        """获取代理来源类型
        
        Returns:
            str: 代理来源类型
        """
        pass

# 导出代理来源接口和实现类
from .api_source import ApiProxySource
from .import_source import ImportedProxySource
from .fixed_source import FixedProxySource
from .direct_source import DirectConnectionSource 