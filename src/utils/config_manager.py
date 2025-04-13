import os
import json
from src.utils.app_path import get_app_dir, get_config_file_path

class ConfigManager:
    def __init__(self):
        self.app_dir = get_app_dir()
        self.config_file = get_config_file_path("settings.json")
    
    def save_settings(self, settings):
        """保存设置到配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    
    def load_settings(self):
        """从配置文件加载设置"""
        if not os.path.exists(self.config_file):
            return {}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {} 