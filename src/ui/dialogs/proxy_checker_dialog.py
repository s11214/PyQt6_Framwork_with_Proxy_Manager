from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QLineEdit, QSpinBox,
    QFormLayout, QGroupBox, QMessageBox, QCheckBox,
    QComboBox, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import json
import aiohttp
import asyncio
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger()

class ApiTestThread(QThread):
    """测试API的后台线程"""
    test_finished = pyqtSignal(bool, dict)  # 信号：测试完成(是否成功, 结果)
    
    def __init__(self, api_url, ip_path, country_path, cnip_path):
        super().__init__()
        self.api_url = api_url
        self.ip_path = ip_path
        self.country_path = country_path
        self.cnip_path = cnip_path
        
    def run(self):
        """线程执行函数，测试API"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.test_api())
            self.test_finished.emit(result[0], result[1])
        except Exception as e:
            self.test_finished.emit(False, {"error": str(e)})
        finally:
            loop.close()
            
    async def test_api(self):
        """异步测试API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, timeout=10) as response:
                    if response.status != 200:
                        return False, {"error": f"HTTP错误: {response.status}"}
                    
                    response_text = await response.text()
                    try:
                        response_json = json.loads(response_text)
                        
                        # 提取IP地址
                        ip_address = None
                        if self.ip_path:
                            paths = self.ip_path.split(".")
                            ip_value = response_json
                            for path in paths:
                                if isinstance(ip_value, dict) and path in ip_value:
                                    ip_value = ip_value[path]
                                else:
                                    ip_value = None
                                    break
                                    
                            if ip_value:
                                ip_address = str(ip_value)
                        
                        # 提取国家/地区信息
                        country_code = None
                        country_name = None
                        
                        # 首先尝试从country_path获取国家名称或代码
                        if self.country_path:
                            paths = self.country_path.split(".")
                            country_value = response_json
                            for path in paths:
                                if isinstance(country_value, dict) and path in country_value:
                                    country_value = country_value[path]
                                else:
                                    country_value = None
                                    break
                                    
                            if country_value:
                                country_name = country_value
                                # 尝试将国家名称映射为代码
                                if country_name == "中国":
                                    country_code = "CN"
                                elif country_name == "香港":
                                    country_code = "HK"
                                elif country_name == "澳门":
                                    country_code = "MO"
                                elif country_name == "台湾":
                                    country_code = "TW"
                        
                        # 检查中国IP标识
                        cnip = False
                        if self.cnip_path:
                            paths = self.cnip_path.split(".")
                            cnip_value = response_json
                            for path in paths:
                                if isinstance(cnip_value, dict) and path in cnip_value:
                                    cnip_value = cnip_value[path]
                                else:
                                    cnip_value = None
                                    break
                                    
                            if cnip_value is True:
                                cnip = True
                                # 如果是中国IP且上面没有获取到具体地区，设置为中国大陆
                                if country_code is None and country_name not in ["香港", "澳门", "台湾"]:
                                    country_code = "CN"
                        
                        # 显示更详细的结果
                        result = {
                            "response": response_json,
                            "ip": ip_address,
                            "country_code": country_code,
                            "country_name": country_name,
                            "cnip": cnip
                        }
                        
                        return True, result
                    except json.JSONDecodeError:
                        return False, {"error": "无法解析JSON响应"}
        except aiohttp.ClientError as e:
            return False, {"error": f"请求错误: {str(e)}"}
        except Exception as e:
            return False, {"error": f"未知错误: {str(e)}"}

class ProxyCheckerDialog(QDialog):
    """IP地区检测API设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IP地区检测API设置")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.config_manager = ConfigManager()
        self.init_ui()
        self.load_settings()
        
        # 添加API测试线程
        self.test_thread = None
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # API列表设置
        api_group = QGroupBox("IP地区检测API列表")
        api_layout = QVBoxLayout()
        
        # API列表
        self.api_list = QListWidget()
        self.api_list.currentRowChanged.connect(self.on_api_selection_changed)
        api_layout.addWidget(self.api_list)
        
        # 调整API顺序的按钮
        order_btn_layout = QHBoxLayout()
        
        self.move_up_btn = QPushButton("↑ 上移")
        self.move_up_btn.setToolTip("提高选中API的优先级")
        self.move_up_btn.clicked.connect(self.move_api_up)
        self.move_up_btn.setEnabled(False)  # 初始禁用
        
        self.move_down_btn = QPushButton("↓ 下移")
        self.move_down_btn.setToolTip("降低选中API的优先级")
        self.move_down_btn.clicked.connect(self.move_api_down)
        self.move_down_btn.setEnabled(False)  # 初始禁用
        
        order_btn_layout.addWidget(self.move_up_btn)
        order_btn_layout.addWidget(self.move_down_btn)
        order_btn_layout.addStretch()
        
        api_layout.addLayout(order_btn_layout)
        api_group.setLayout(api_layout)
        
        # API详细配置
        config_group = QGroupBox("API详细配置")
        config_layout = QFormLayout()
        
        # API URL输入框
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("例如: https://api.vore.top/api/IPdata")
        config_layout.addRow("API URL:", self.api_url)
        
        # IP路径输入框
        self.ip_path = QLineEdit()
        self.ip_path.setPlaceholderText("例如: ipinfo.text（留空表示不提取IP）")
        config_layout.addRow("IP路径:", self.ip_path)
        
        # 国家/地区信息路径
        self.country_path = QLineEdit()
        self.country_path.setPlaceholderText("例如: ipdata.info1 或 country_code")
        config_layout.addRow("国家/地区路径:", self.country_path)
        
        # 中国IP标识路径
        self.cnip_path = QLineEdit()
        self.cnip_path.setPlaceholderText("例如: ipinfo.cnip (留空表示不使用)")
        config_layout.addRow("中国标识路径:", self.cnip_path)
        
        # 是否支持跨域
        self.supports_cors = QCheckBox("支持跨域")
        self.supports_cors.setToolTip("API是否支持跨域请求 (CORS)")
        config_layout.addRow("", self.supports_cors)
        
        # API操作按钮
        api_btn_layout = QHBoxLayout()
        
        self.add_api_btn = QPushButton("添加API")
        self.add_api_btn.clicked.connect(self.add_api)
        
        self.update_api_btn = QPushButton("更新API")
        self.update_api_btn.clicked.connect(self.update_api)
        self.update_api_btn.setEnabled(False)  # 初始禁用
        
        self.delete_api_btn = QPushButton("删除API")
        self.delete_api_btn.clicked.connect(self.delete_api)
        self.delete_api_btn.setEnabled(False)  # 初始禁用
        
        self.test_api_btn = QPushButton("测试API")
        self.test_api_btn.clicked.connect(self.test_api)
        
        api_btn_layout.addWidget(self.add_api_btn)
        api_btn_layout.addWidget(self.update_api_btn)
        api_btn_layout.addWidget(self.delete_api_btn)
        api_btn_layout.addWidget(self.test_api_btn)
        
        config_layout.addRow("", api_btn_layout)
        
        # 预设API下拉菜单
        preset_layout = QHBoxLayout()
        preset_label = QLabel("从预设添加:")
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- 选择预设API --")
        self.preset_combo.addItems(list(self.get_preset_apis().keys()))
        self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        
        config_layout.addRow("", preset_layout)
        
        config_group.setLayout(config_layout)
        
        # 超时和重试设置
        param_group = QGroupBox("检查参数")
        param_layout = QFormLayout()
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setToolTip("API请求的超时时间")
        
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 5)
        self.retries_spin.setToolTip("请求失败时的重试次数")
        
        self.max_proxy_retries_spin = QSpinBox()
        self.max_proxy_retries_spin.setRange(1, 10)
        self.max_proxy_retries_spin.setToolTip("代理失败时的最大更换次数")
        
        param_layout.addRow("超时时间:", self.timeout_spin)
        param_layout.addRow("重试次数:", self.retries_spin)
        param_layout.addRow("最大代理更换次数:", self.max_proxy_retries_spin)
        
        param_group.setLayout(param_layout)
        
        # 保存和取消按钮
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1E7E34;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5A6268;
            }
            QPushButton:pressed {
                background-color: #545B62;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # 添加所有组件到主布局
        layout.addWidget(api_group)
        layout.addWidget(config_group)
        layout.addWidget(param_group)
        layout.addLayout(buttons_layout)
        
    def get_preset_apis(self):
        """获取预设API配置"""
        return {
            "api.vore.top": {
                "url": "https://api.vore.top/api/IPdata",
                "ip_path": "ipinfo.text",
                "country_path": "ipdata.info1",
                "cnip_path": "ipinfo.cnip",
                "supports_cors": True
            },
            "ip-api.io": {
                "url": "https://ip-api.io/json",
                "ip_path": "ip",
                "country_path": "country_code",
                "cnip_path": "",
                "supports_cors": True
            },
            "api.ip.sb": {
                "url": "https://api.ip.sb/geoip",
                "ip_path": "ip",
                "country_path": "country_code",
                "cnip_path": "",
                "supports_cors": True
            },
            "freeipapi.com": {
                "url": "https://freeipapi.com/api/json",
                "ip_path": "ipAddress",
                "country_path": "countryCode",
                "cnip_path": "",
                "supports_cors": True
            },
            "ipwhois.app": {
                "url": "https://ipwhois.app/json/?format=json",
                "ip_path": "ip",
                "country_path": "country_code",
                "cnip_path": "",
                "supports_cors": True
            },
            "geolocation-db.com": {
                "url": "https://geolocation-db.com/json",
                "ip_path": "IPv4",
                "country_path": "country_code",
                "cnip_path": "",
                "supports_cors": True
            }
        }
        
    def on_preset_selected(self, index):
        """处理预设API选择"""
        if index <= 0:  # 忽略第一个占位项
            return
            
        preset_name = self.preset_combo.currentText()
        preset_apis = self.get_preset_apis()
        
        if preset_name in preset_apis:
            api_config = preset_apis[preset_name]
            self.api_url.setText(api_config["url"])
            self.ip_path.setText(api_config["ip_path"])
            self.country_path.setText(api_config["country_path"])
            self.cnip_path.setText(api_config["cnip_path"])
            self.supports_cors.setChecked(api_config["supports_cors"])
            
        # 重置下拉框
        self.preset_combo.setCurrentIndex(0)
            
    def load_settings(self):
        """从配置加载设置"""
        settings = self.config_manager.load_settings() or {}
        
        # 获取代理检查器设置
        proxy_settings = settings.get("proxy", {})
        checker_settings = proxy_settings.get("checker", {})
        
        # 加载IP APIs
        ip_apis = checker_settings.get("ip_apis", [])
        if not ip_apis:
            # 使用默认API
            ip_apis = [
                {
                    "url": "https://api.vore.top/api/IPdata",
                    "ip_path": "ipinfo.text",
                    "country_path": "ipdata.info1",
                    "cnip_path": "ipinfo.cnip",
                    "supports_cors": True
                }
            ]
            
        # 加载到列表中
        self.api_list.clear()
        for api in ip_apis:
            item = QListWidgetItem(api["url"])
            item.setData(Qt.ItemDataRole.UserRole, api)
            self.api_list.addItem(item)
            
        # 加载超时时间
        timeout = checker_settings.get("timeout", 10)
        self.timeout_spin.setValue(timeout)
        
        # 加载重试次数
        max_retries = checker_settings.get("max_retries", 3)
        self.retries_spin.setValue(max_retries)
        
        # 加载最大代理更换次数
        max_proxy_retries = checker_settings.get("max_proxy_retries", 5)
        self.max_proxy_retries_spin.setValue(max_proxy_retries)
        
    def on_api_selection_changed(self, row):
        """API选择改变时更新UI"""
        has_selection = row >= 0
        self.update_api_btn.setEnabled(has_selection)
        self.delete_api_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection and row > 0)
        self.move_down_btn.setEnabled(has_selection and row < self.api_list.count() - 1)
        
        if has_selection:
            item = self.api_list.item(row)
            api_config = item.data(Qt.ItemDataRole.UserRole)
            
            self.api_url.setText(api_config.get("url", ""))
            self.ip_path.setText(api_config.get("ip_path", ""))
            self.country_path.setText(api_config.get("country_path", ""))
            self.cnip_path.setText(api_config.get("cnip_path", ""))
            self.supports_cors.setChecked(api_config.get("supports_cors", False))
        else:
            # 清空输入框
            self.api_url.clear()
            self.ip_path.clear()
            self.country_path.clear()
            self.cnip_path.clear()
            self.supports_cors.setChecked(False)
            
    def move_api_up(self):
        """将选中的API上移一位（提高优先级）"""
        current_row = self.api_list.currentRow()
        if current_row > 0:
            current_item = self.api_list.takeItem(current_row)
            self.api_list.insertItem(current_row - 1, current_item)
            self.api_list.setCurrentRow(current_row - 1)
            
    def move_api_down(self):
        """将选中的API下移一位（降低优先级）"""
        current_row = self.api_list.currentRow()
        if current_row < self.api_list.count() - 1 and current_row >= 0:
            current_item = self.api_list.takeItem(current_row)
            self.api_list.insertItem(current_row + 1, current_item)
            self.api_list.setCurrentRow(current_row + 1)
            
    def add_api(self):
        """添加新API"""
        url = self.api_url.text().strip()
        ip_path = self.ip_path.text().strip()
        country_path = self.country_path.text().strip()
        cnip_path = self.cnip_path.text().strip()
        supports_cors = self.supports_cors.isChecked()
        
        if not url:
            QMessageBox.warning(self, "输入错误", "API URL不能为空")
            return
            
        if not country_path and not cnip_path:
            QMessageBox.warning(self, "输入错误", "国家/地区信息路径和中国标识路径至少需要填写一项")
            return
            
        # 检查是否已存在相同URL的API
        for i in range(self.api_list.count()):
            item = self.api_list.item(i)
            api_config = item.data(Qt.ItemDataRole.UserRole)
            if api_config.get("url") == url:
                reply = QMessageBox.question(
                    self, 
                    "API已存在", 
                    f"API '{url}' 已存在，是否更新？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # 更新现有API
                    api_config["ip_path"] = ip_path
                    api_config["country_path"] = country_path
                    api_config["cnip_path"] = cnip_path
                    api_config["supports_cors"] = supports_cors
                    item.setData(Qt.ItemDataRole.UserRole, api_config)
                    self.api_list.setCurrentItem(item)
                return
        
        # 创建新API配置
        api_config = {
            "url": url,
            "ip_path": ip_path,
            "country_path": country_path,
            "cnip_path": cnip_path,
            "supports_cors": supports_cors
        }
        
        # 添加到列表
        item = QListWidgetItem(url)
        item.setData(Qt.ItemDataRole.UserRole, api_config)
        self.api_list.addItem(item)
        self.api_list.setCurrentItem(item)
        
        # 清空输入框
        self.api_url.clear()
        self.ip_path.clear()
        self.country_path.clear()
        self.cnip_path.clear()
        self.supports_cors.setChecked(False)
        
    def update_api(self):
        """更新选中的API"""
        current_row = self.api_list.currentRow()
        if current_row < 0:
            return
            
        url = self.api_url.text().strip()
        ip_path = self.ip_path.text().strip()
        country_path = self.country_path.text().strip()
        cnip_path = self.cnip_path.text().strip()
        supports_cors = self.supports_cors.isChecked()
        
        if not url:
            QMessageBox.warning(self, "输入错误", "API URL不能为空")
            return
            
        if not country_path and not cnip_path:
            QMessageBox.warning(self, "输入错误", "国家/地区信息路径和中国标识路径至少需要填写一项")
            return
            
        # 更新API配置
        item = self.api_list.item(current_row)
        api_config = item.data(Qt.ItemDataRole.UserRole)
        api_config["url"] = url
        api_config["ip_path"] = ip_path
        api_config["country_path"] = country_path
        api_config["cnip_path"] = cnip_path
        api_config["supports_cors"] = supports_cors
        
        item.setText(url)
        item.setData(Qt.ItemDataRole.UserRole, api_config)
        
    def delete_api(self):
        """删除选中的API"""
        current_row = self.api_list.currentRow()
        if current_row < 0:
            return
            
        # 如果只剩一个API，不允许删除
        if self.api_list.count() <= 1:
            QMessageBox.warning(self, "无法删除", "至少需要保留一个IP地区检测API")
            return
            
        # 确认删除
        item = self.api_list.item(current_row)
        url = item.text()
        
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定要删除API '{url}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.api_list.takeItem(current_row)
            
    def test_api(self):
        """测试当前配置的API"""
        url = self.api_url.text().strip()
        ip_path = self.ip_path.text().strip()
        country_path = self.country_path.text().strip()
        cnip_path = self.cnip_path.text().strip()
        
        if not url:
            QMessageBox.warning(self, "输入错误", "请输入要测试的API URL")
            return
            
        if not country_path and not cnip_path:
            QMessageBox.warning(self, "输入错误", "国家/地区信息路径和中国标识路径至少需要填写一项")
            return
            
        # 禁用测试按钮，防止重复点击
        self.test_api_btn.setEnabled(False)
        self.test_api_btn.setText("测试中...")
        
        # 创建并启动测试线程
        self.test_thread = ApiTestThread(url, ip_path, country_path, cnip_path)
        self.test_thread.test_finished.connect(self.on_test_finished)
        self.test_thread.start()
        
    def on_test_finished(self, success, result):
        """API测试完成回调"""
        # 恢复按钮状态
        self.test_api_btn.setEnabled(True)
        self.test_api_btn.setText("测试API")
        
        if success:
            # 提取详细信息
            ip_address = result.get("ip")
            country_code = result.get("country_code")
            country_name = result.get("country_name")
            cnip = result.get("cnip", False)
            
            # 组合显示信息
            location_info = []
            if ip_address:
                location_info.append(f"IP地址: {ip_address}")
            if country_code:
                location_info.append(f"国家/地区代码: {country_code}")
            if country_name:
                location_info.append(f"国家/地区名称: {country_name}")
            if cnip:
                location_info.append("中国IP标识: 是")
                
            location_text = ", ".join(location_info) if location_info else "未能解析地区信息"
            
            # 显示成功消息
            QMessageBox.information(self, "测试成功", f"API 连接成功\n{location_text}")
        else:
            # 显示错误消息
            error = result.get("error", "未知错误")
            QMessageBox.critical(self, "测试失败", f"API 测试失败: {error}")
        
    def save_settings(self):
        """保存设置到配置文件"""
        # 收集所有API配置
        ip_apis = []
        for i in range(self.api_list.count()):
            item = self.api_list.item(i)
            api_config = item.data(Qt.ItemDataRole.UserRole)
            ip_apis.append(api_config)
            
        # 获取其他设置
        timeout = self.timeout_spin.value()
        max_retries = self.retries_spin.value()
        max_proxy_retries = self.max_proxy_retries_spin.value()
        
        # 加载现有设置
        settings = self.config_manager.load_settings() or {}
        
        # 确保proxy和checker节点存在
        if "proxy" not in settings:
            settings["proxy"] = {}
        if "checker" not in settings["proxy"]:
            settings["proxy"]["checker"] = {}
            
        # 更新设置
        settings["proxy"]["checker"]["ip_apis"] = ip_apis
        settings["proxy"]["checker"]["timeout"] = timeout
        settings["proxy"]["checker"]["max_retries"] = max_retries
        settings["proxy"]["checker"]["max_proxy_retries"] = max_proxy_retries
        
        # 保存设置
        try:
            self.config_manager.save_settings(settings)
            QMessageBox.information(self, "成功", "IP地区检测API设置已保存")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}") 