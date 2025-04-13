"""地理信息处理包

提供国家/地区代码映射、地理位置识别等功能。
"""

from .mapper import get_mapper, CountryMapper

__all__ = ['get_mapper', 'CountryMapper'] 