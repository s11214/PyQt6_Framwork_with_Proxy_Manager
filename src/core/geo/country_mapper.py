"""国家/地区代码映射模块
提供国家/地区代码与名称的映射功能。

此模块为了向后兼容性而保留，实际实现已移至mapper.py文件中。
"""
from .mapper import CountryMapper, get_mapper

# 为了保持向后兼容，导出相同的符号
__all__ = ['CountryMapper', 'get_mapper'] 