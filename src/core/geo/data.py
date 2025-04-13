"""国家/地区数据模块
提供国家/地区代码与名称的映射数据。
"""
from typing import Dict

# 国家/地区代码到中文名称的映射
CODE_TO_CHINESE_NAME: Dict[str, str] = {
    # 中国大陆及港澳台地区
    "CN": "中国",
    "HK": "香港",
    "TW": "台湾",
    "MO": "澳门",
    
    # 亚洲
    "JP": "日本",
    "KR": "韩国",
    "SG": "新加坡",
    "IN": "印度",
    "TH": "泰国",
    "MY": "马来西亚",
    "ID": "印度尼西亚",
    "PH": "菲律宾",
    "VN": "越南",
    
    # 欧洲
    "GB": "英国",
    "DE": "德国",
    "FR": "法国",
    "IT": "意大利",
    "ES": "西班牙",
    "CH": "瑞士",
    "NL": "荷兰",
    "SE": "瑞典",
    "NO": "挪威",
    "DK": "丹麦",
    "FI": "芬兰",
    "PL": "波兰",
    "PT": "葡萄牙",
    "GR": "希腊",
    "RU": "俄罗斯",
    
    # 北美洲
    "US": "美国",
    "CA": "加拿大",
    "MX": "墨西哥",
    
    # 南美洲
    "BR": "巴西",
    "AR": "阿根廷",
    "CL": "智利",
    
    # 大洋洲
    "AU": "澳大利亚",
    "NZ": "新西兰",
    
    # 非洲
    "ZA": "南非",
    "EG": "埃及",
    
    # 中东
    "TR": "土耳其",
    "AE": "阿联酋",
    "SA": "沙特阿拉伯",
    "IL": "以色列"
}

# 国家/地区代码到英文名称的映射
CODE_TO_ENGLISH_NAME: Dict[str, str] = {
    # 中国大陆及港澳台地区
    "CN": "China",
    "HK": "Hong Kong",
    "TW": "Taiwan",
    "MO": "Macau",
    
    # 亚洲
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
    "IN": "India",
    "TH": "Thailand",
    "MY": "Malaysia",
    "ID": "Indonesia",
    "PH": "Philippines",
    "VN": "Vietnam",
    
    # 欧洲
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "CH": "Switzerland",
    "NL": "Netherlands",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "PL": "Poland",
    "PT": "Portugal",
    "GR": "Greece",
    "RU": "Russia",
    
    # 北美洲
    "US": "United States",
    "CA": "Canada",
    "MX": "Mexico",
    
    # 南美洲
    "BR": "Brazil",
    "AR": "Argentina",
    "CL": "Chile",
    
    # 大洋洲
    "AU": "Australia",
    "NZ": "New Zealand",
    
    # 非洲
    "ZA": "South Africa",
    "EG": "Egypt",
    
    # 中东
    "TR": "Turkey",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "IL": "Israel"
}

# 常用国家列表（UI显示用）
UI_COUNTRY_DATA: Dict[str, str] = {
    "中国": "CN",
    "香港": "HK",
    "台湾": "TW",
    "澳门": "MO",
    "美国": "US", 
    "日本": "JP",
    "韩国": "KR",
    "英国": "GB",
    "德国": "DE",
    "法国": "FR",
    "加拿大": "CA",
    "澳大利亚": "AU",
    "新加坡": "SG",
    "印度": "IN",
    "巴西": "BR",
    "俄罗斯": "RU",
    "意大利": "IT",
    "西班牙": "ES",
    "瑞士": "CH",
    "荷兰": "NL",
    "瑞典": "SE",
    "挪威": "NO",
    "丹麦": "DK", 
    "芬兰": "FI",
    "波兰": "PL",
    "土耳其": "TR",
    "埃及": "EG",
    "南非": "ZA",
    "阿根廷": "AR",
    "墨西哥": "MX",
    "新西兰": "NZ"
}

# 国家/地区代码别名映射
COUNTRY_CODE_ALIASES: Dict[str, list] = {
    "CN": ["CHINA", "MAINLAND", "ZHONGGUO", "中国大陆", "中国内地", "中华人民共和国", "中华", "大陆"],
    "US": ["USA", "AMERICA", "UNITED STATES", "美国", "美利坚", "美利坚合众国"], 
    "GB": ["UK", "UNITED KINGDOM", "ENGLAND", "英国", "英格兰", "大不列颠", "英"],
    "HK": ["HONG KONG", "HONGKONG", "香港", "香港特别行政区", "港"],
    "TW": ["TAIWAN", "台湾", "中国台湾", "台湾省", "台"],
    "MO": ["MACAO", "MACAU", "澳门", "澳门特别行政区", "澳"],
    "JP": ["JAPAN", "日本", "日"],
    "KR": ["SOUTH KOREA", "KOREA", "韩国", "南韩", "大韩民国"],
    "SG": ["SINGAPORE", "新加坡", "新"],
    "IN": ["INDIA", "印度"],
    "RU": ["RUSSIA", "俄罗斯", "俄", "俄罗斯联邦"],
    "DE": ["GERMANY", "德国", "德意志"],
    "FR": ["FRANCE", "法国", "法兰西"],
    "CA": ["CANADA", "加拿大", "加"],
    "AU": ["AUSTRALIA", "澳大利亚", "澳洲"]
} 