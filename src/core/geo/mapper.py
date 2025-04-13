"""国家/地区映射器实现模块
提供国家/地区代码与名称映射的核心功能实现。
"""
from typing import Dict, Optional, Any
from .data import (
    CODE_TO_CHINESE_NAME,
    CODE_TO_ENGLISH_NAME,
    UI_COUNTRY_DATA,
    COUNTRY_CODE_ALIASES
)
from src.utils.logger import get_logger

logger = get_logger()

class CountryMapper:
    """国家/地区代码映射器类
    
    负责提供国家/地区代码与名称之间的映射服务，支持中英文名称。
    采用单例模式实现，确保应用中只有一个映射器实例。
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'CountryMapper':
        """获取映射器实例（单例模式）
        
        Returns:
            CountryMapper: 映射器实例
        """
        if cls._instance is None:
            cls._instance = CountryMapper()
        return cls._instance
    
    def __init__(self):
        """初始化映射器"""
        # 检查是否已存在实例
        if CountryMapper._instance is not None:
            raise RuntimeError("CountryMapper 是单例类，请使用 get_instance() 方法获取实例")
            
        # 初始化映射表
        self._mapping_cache = self._init_country_mapping()
    
    def _init_country_mapping(self) -> Dict[str, str]:
        """初始化国家/地区映射表
        
        构建双向映射表（代码->名称，名称->代码）
        
        Returns:
            Dict[str, str]: 映射表
        """
        mapping = {}
        
        # 1. 代码 -> 中文名称的映射
        mapping.update(CODE_TO_CHINESE_NAME)
        
        # 2. 代码 -> 英文名称的映射
        mapping.update(CODE_TO_ENGLISH_NAME)
        
        # 3. 中文名称 -> 代码的反向映射
        for code, name in CODE_TO_CHINESE_NAME.items():
            if name not in mapping:
                mapping[name] = code
        
        # 4. 英文名称 -> 代码的反向映射
        for code, name in CODE_TO_ENGLISH_NAME.items():
            if name not in mapping:
                mapping[name] = code
                
        # 5. 处理常见别名和大小写变体
        for code, aliases in COUNTRY_CODE_ALIASES.items():
            for alias in aliases:
                if alias not in mapping:
                    mapping[alias] = code
        
        # 6. 建立大写映射以优化查找
        upper_mapping = {}
        for key, value in list(mapping.items()):
            if isinstance(key, str):
                upper_key = key.upper()
                if upper_key not in mapping and upper_key not in upper_mapping:
                    upper_mapping[upper_key] = value
        
        # 添加大写映射
        mapping.update(upper_mapping)
        
        return mapping
    
    @property
    def country_mapping(self) -> Dict[str, str]:
        """获取国家/地区映射表
        
        Returns:
            Dict[str, str]: 映射表
        """
        return self._mapping_cache
    
    def get_country_code(self, country_name: str) -> Optional[str]:
        """根据国家/地区名称获取ISO代码
        
        Args:
            country_name: 国家/地区名称
            
        Returns:
            Optional[str]: ISO代码，未找到则返回None
        """
        if not country_name:
            return None
            
        # 标准化输入
        country_name = str(country_name).strip()
        
        # 直接查找
        if country_name in self._mapping_cache:
            return self._mapping_cache[country_name]
            
        # 尝试大写查找
        upper_name = country_name.upper()
        if upper_name in self._mapping_cache:
            return self._mapping_cache[upper_name]
            
        # 特殊处理中国相关名称
        if country_name.startswith('中国'):
            return "CN"
            
        # 未找到映射
        logger.debug(f"未找到国家名称的映射: {country_name}")
        return None
        
    def get_country_name(self, country_code: str) -> Optional[str]:
        """根据ISO代码获取国家/地区名称
        
        Args:
            country_code: ISO代码
            
        Returns:
            Optional[str]: 国家/地区名称，未找到则返回None
        """
        if not country_code:
            return None
            
        # 标准化输入
        country_code = str(country_code).strip().upper()
        
        # 查找映射
        if country_code in CODE_TO_CHINESE_NAME:
            return CODE_TO_CHINESE_NAME[country_code]
            
        # 未找到映射
        logger.debug(f"未找到国家代码的映射: {country_code}")
        return None
    
    def get_country_english_name(self, country_code: str) -> Optional[str]:
        """根据ISO代码获取国家/地区英文名称
        
        Args:
            country_code: ISO代码
            
        Returns:
            Optional[str]: 国家/地区英文名称，未找到则返回None
        """
        if not country_code:
            return None
            
        # 标准化输入
        country_code = str(country_code).strip().upper()
        
        # 直接从英文名称映射中查找
        if country_code in CODE_TO_ENGLISH_NAME:
            return CODE_TO_ENGLISH_NAME[country_code]
            
        # 未找到映射
        logger.debug(f"未找到国家代码的英文名称映射: {country_code}")
        return None
    
    def match_country_code(self, detected_code: str, target_code: str) -> bool:
        """检查检测到的国家/地区代码是否匹配目标国家
        
        Args:
            detected_code: 检测到的国家/地区代码
            target_code: 目标国家/地区代码
            
        Returns:
            bool: 是否匹配
        """
        if not detected_code or not target_code:
            return False
        
        # 标准化国家/地区代码
        detected_code = str(detected_code).strip().upper()
        target_code = str(target_code).strip().upper()
        
        # 1. 直接比较，如果相等则立即返回匹配成功
        if detected_code == target_code:
            logger.debug(f"国家代码直接匹配: 检测到 {detected_code}, 目标 {target_code}")
            return True
        
        # 2. 尝试将国家名称转换为ISO代码
        mapped_detected = self.get_country_code(detected_code)
        if mapped_detected:
            mapped_detected = mapped_detected.upper()
            logger.debug(f"将检测到的代码 {detected_code} 映射为 {mapped_detected}")
            detected_code = mapped_detected
        
        mapped_target = self.get_country_code(target_code)
        if mapped_target:
            mapped_target = mapped_target.upper()
            logger.debug(f"将目标代码 {target_code} 映射为 {mapped_target}")
            target_code = mapped_target
        
        # 3. 再次比较映射后的代码
        if detected_code == target_code:
            logger.debug(f"国家代码映射后匹配: 检测到 {detected_code}, 目标 {target_code}")
            return True
            
        # 4. 特殊处理中国大陆与港澳台地区
        # 4.1 如果目标是中国大陆(CN)，检测到的是港澳台(HK/TW/MO)，则不匹配
        if target_code == 'CN' and detected_code in ['HK', 'TW', 'MO']:
            logger.debug(f"目标是中国大陆(CN)，但检测到港澳台地区({detected_code})，不匹配")
            return False
            
        # 4.2 如果目标是港澳台(HK/TW/MO)，检测到的是中国大陆(CN)，则不匹配
        if target_code in ['HK', 'TW', 'MO'] and detected_code == 'CN':
            logger.debug(f"目标是港澳台地区({target_code})，但检测到中国大陆(CN)，不匹配")
            return False
            
        # 如果经过上述所有判断后仍未返回，则视为不匹配
        logger.debug(f"国家代码不匹配: 检测到 {detected_code}, 目标 {target_code}")
        return False
        
    def get_ui_country_data(self) -> Dict[str, str]:
        """获取UI界面使用的国家/地区数据
        
        Returns:
            Dict[str, str]: 国家/地区名称与代码的映射
        """
        return UI_COUNTRY_DATA.copy()


# 快捷访问方法
def get_mapper() -> CountryMapper:
    """获取国家/地区代码映射器实例
    
    Returns:
        CountryMapper: 映射器实例
    """
    return CountryMapper.get_instance() 