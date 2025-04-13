from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QRadioButton, QLineEdit, 
                             QComboBox, QPushButton, QLabel, 
                             QFormLayout, QFrame, QDialog, QCheckBox, QSpinBox, QProgressBar)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger
from src.core.geo.country_mapper import get_mapper

class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.import_proxies_dialog = None
        self.proxy_pool_dialog = None
        
        # 获取国家映射器
        self.country_mapper = get_mapper()
        
        self.init_ui()
        
        # 使用延迟加载设置
        QTimer.singleShot(100, self.load_settings)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)  # 减小顶部边距
        layout.setSpacing(6)  # 减小控件间距
        
        # 代理设置组
        proxy_group = self.create_proxy_group()
        layout.addWidget(proxy_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 添加保存按钮
        save_btn = QPushButton("保存设置")
        save_btn.setFixedWidth(120)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069D9;
            }
            QPushButton:pressed {
                background-color: #0056B3;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        
        # 创建状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #28A745;
                font-weight: bold;
            }
        """)
        
        # 底部按钮布局
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addWidget(save_btn)
        layout.addLayout(bottom_layout)
        
        # 初始化界面状态 - 如果当前选中直连模式，确保API链接输入框是禁用的
        current_proxy_type = self.proxy_type.currentText()
        if current_proxy_type == "直连":
            self.api_url.setEnabled(False)
            self.api_url.setStyleSheet("""
                QLineEdit {
                    background-color: #F8F9FA;
                    color: #6C757D;
                    border: 1px solid #DDE1E6;
                }
            """)
        else:
            self.api_url.setEnabled(True)
            self.api_url.setStyleSheet("")
        
    def create_proxy_group(self) -> QGroupBox:
        group = QGroupBox("代理设置")
        layout = QVBoxLayout()
        
        # 代理来源选择
        source_layout = QHBoxLayout()
        self.api_radio = QRadioButton("API获取")
        self.pool_radio = QRadioButton("代理池")
        self.fixed_radio = QRadioButton("固定代理")  # 新增固定代理选项
        self.direct_radio = QRadioButton("直连")  # 新增直连选项
        self.api_radio.setChecked(True)
        source_layout.addWidget(self.api_radio)
        source_layout.addWidget(self.pool_radio)
        source_layout.addWidget(self.fixed_radio)  # 添加到布局
        source_layout.addWidget(self.direct_radio)  # 添加直连到布局
        source_layout.addStretch()
        layout.addLayout(source_layout)
        
        # API设置
        self.api_widget = QWidget()
        api_layout = QFormLayout(self.api_widget)
        
        # 代理类型选择
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["HTTP", "SOCKS5"])
        self.proxy_type.setFixedWidth(120)
        self.proxy_type.currentTextChanged.connect(self.on_proxy_type_changed)
        api_layout.addRow("代理类型:", self.proxy_type)
        
        # API链接输入框
        self.api_url = QLineEdit()
        api_layout.addRow("API链接:", self.api_url)
        
        layout.addWidget(self.api_widget)
        
        # 代理池设置
        self.pool_widget = QWidget()
        pool_layout = QVBoxLayout(self.pool_widget)
        
        # 代理池使用设置
        pool_settings_layout = QVBoxLayout()
        
        # 其他选项
        options_layout = QHBoxLayout()
        self.allow_reuse = QCheckBox("允许重复使用")
        self.allow_reuse.setChecked(True)
        options_layout.addWidget(self.allow_reuse)
        options_layout.addStretch()
        pool_settings_layout.addLayout(options_layout)
        
        pool_layout.addLayout(pool_settings_layout)
        
        # 代理池操作按钮
        buttons_layout = QHBoxLayout()
        
        import_btn = QPushButton("导入代理")
        import_btn.setFixedWidth(120)
        import_btn.setStyleSheet("""
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
        import_btn.clicked.connect(self.show_import_dialog)
        
        manage_btn = QPushButton("代理池管理")
        manage_btn.setFixedWidth(120)
        manage_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B728E;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5C677D;
            }
            QPushButton:pressed {
                background-color: #50586C;
            }
        """)
        manage_btn.clicked.connect(self.show_proxy_pool_dialog)
        
        buttons_layout.addWidget(import_btn)
        buttons_layout.addWidget(manage_btn)
        buttons_layout.addStretch()
        pool_layout.addLayout(buttons_layout)
        
        layout.addWidget(self.pool_widget)
        
        # 固定代理设置 - 新增
        self.fixed_proxy_widget = QWidget()
        fixed_proxy_layout = QFormLayout(self.fixed_proxy_widget)
        
        # 代理类型选择和清空按钮布局
        proxy_type_layout = QHBoxLayout()
        
        self.fixed_proxy_type = QComboBox()
        self.fixed_proxy_type.addItems(["HTTP", "SOCKS5"])
        self.fixed_proxy_type.setFixedWidth(120)
        proxy_type_layout.addWidget(self.fixed_proxy_type)
        
        # 添加清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFixedWidth(80)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC3545;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
            QPushButton:pressed {
                background-color: #BD2130;
            }
        """)
        clear_btn.clicked.connect(self.clear_fixed_proxy)
        proxy_type_layout.addWidget(clear_btn)

        # 添加代理检测按钮
        check_proxy_btn = QPushButton("代理检测")
        check_proxy_btn.setFixedWidth(80)
        check_proxy_btn.setStyleSheet("""
            QPushButton {
                background-color: #17A2B8;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117A8B;
            }
        """)
        check_proxy_btn.clicked.connect(self.check_fixed_proxy)
        proxy_type_layout.addWidget(check_proxy_btn)
        proxy_type_layout.addStretch()
        
        fixed_proxy_layout.addRow("代理类型:", proxy_type_layout)
        
        # 主机输入框
        self.fixed_proxy_host = QLineEdit()
        self.fixed_proxy_host.setPlaceholderText("例如: 192.168.1.1 或粘贴完整格式 host:port:username:password")
        # 连接文本变化事件用于自动解析代理信息
        self.fixed_proxy_host.textChanged.connect(self.parse_proxy_info)
        fixed_proxy_layout.addRow("主机:", self.fixed_proxy_host)
        
        # 端口输入框
        self.fixed_proxy_port = QLineEdit()
        self.fixed_proxy_port.setPlaceholderText("例如: 8080")
        self.fixed_proxy_port.setFixedWidth(120)
        fixed_proxy_layout.addRow("端口:", self.fixed_proxy_port)
        
        # 用户名输入框（可选）
        self.fixed_proxy_username = QLineEdit()
        self.fixed_proxy_username.setPlaceholderText("可选")
        fixed_proxy_layout.addRow("用户名:", self.fixed_proxy_username)
        
        # 密码输入框（可选）- 改为明文显示
        self.fixed_proxy_password = QLineEdit()
        self.fixed_proxy_password.setPlaceholderText("可选")
        fixed_proxy_layout.addRow("密码:", self.fixed_proxy_password)
        
        layout.addWidget(self.fixed_proxy_widget)
        
        # 直连设置 - 新增
        self.direct_widget = QWidget()
        direct_layout = QVBoxLayout(self.direct_widget)
        
        direct_info = QLabel("直连模式将不使用任何代理，直接连接目标服务器。")
        direct_info.setStyleSheet("color: #6C757D; font-style: italic;")
        direct_layout.addWidget(direct_info)
        
        layout.addWidget(self.direct_widget)
        
        # 添加分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #DDE1E6;")
        layout.addWidget(line)
        
        # 忽略IP检查
        ignore_ip_layout = QHBoxLayout()
        self.ignore_ip_check = QCheckBox("忽略IP所在地检查")
        self.ignore_ip_check.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
            }
        """)
        # 连接信号，当选中状态变化时更新国家选择框的可见性
        self.ignore_ip_check.stateChanged.connect(self.update_country_selector_visibility)
        ignore_ip_layout.addWidget(self.ignore_ip_check)
        
        # 添加国家选择下拉框
        self.country_label = QLabel("检查IP所在国家/地区:")
        self.country_selector = QComboBox()
        
        # 获取界面使用的国家列表
        self.country_data = self.country_mapper.get_ui_country_data()
        
        for country_name in self.country_data.keys():
            self.country_selector.addItem(country_name)
            
        ignore_ip_layout.addWidget(self.country_label)
        ignore_ip_layout.addWidget(self.country_selector)
        layout.addLayout(ignore_ip_layout)

        # 添加代理检查设置按钮
        checker_settings_btn = QPushButton("代理检查设置")
        checker_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B728E;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5C677D;
            }
            QPushButton:pressed {
                background-color: #50586C;
            }
        """)
        checker_settings_btn.clicked.connect(self.show_proxy_checker_dialog)
        ignore_ip_layout.addWidget(checker_settings_btn)
        ignore_ip_layout.addStretch()
        
        # 并行线程数设置
        thread_layout = QFormLayout()
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 150)
        self.thread_count.setValue(30)
        self.thread_count.setFixedWidth(120)
        thread_tip = QLabel("(支持1-150个线程)")
        thread_tip.setStyleSheet("color: #6C757D; font-size: 12px;")
        thread_container = QWidget()
        thread_container_layout = QHBoxLayout(thread_container)
        thread_container_layout.setContentsMargins(0, 0, 0, 0)
        thread_container_layout.addWidget(self.thread_count)
        thread_container_layout.addWidget(thread_tip)
        thread_container_layout.addStretch()
        thread_layout.addRow("并行线程数:", thread_container)
        layout.addLayout(thread_layout)
        
        # 连接单选按钮信号
        self.api_radio.toggled.connect(self.on_proxy_source_changed)
        self.pool_radio.toggled.connect(self.on_proxy_source_changed)
        self.fixed_radio.toggled.connect(self.on_proxy_source_changed)  # 连接新的单选按钮信号
        self.direct_radio.toggled.connect(self.on_proxy_source_changed)  # 连接直连单选按钮信号
        
        # 初始化界面状态
        self.on_proxy_source_changed()
        
        group.setLayout(layout)
        return group
        
    def on_proxy_type_changed(self, proxy_type: str):
        # 不再需要处理"直连"类型，因为它已经移到独立的代理来源
        self.api_url.setEnabled(True)
        self.api_url.setStyleSheet("")
            
    def on_proxy_source_changed(self):
        """处理代理来源变化"""
        # 判断当前选中的是哪种代理来源
        is_api = self.api_radio.isChecked()
        is_pool = self.pool_radio.isChecked()
        is_fixed = self.fixed_radio.isChecked()
        is_direct = self.direct_radio.isChecked()
        
        # 显示/隐藏相应的设置界面
        self.api_widget.setVisible(is_api)
        self.pool_widget.setVisible(is_pool)
        self.fixed_proxy_widget.setVisible(is_fixed)
        self.direct_widget.setVisible(is_direct)
        
    def on_use_mode_changed(self, mode: str):
        """处理使用模式变化"""
        # 固定代理模式已移除，仅保留允许重复使用选项
        pass

    def update_fixed_proxy_list(self):
        """更新固定代理下拉列表 - 已不再需要"""
        pass
        
    def show_import_dialog(self):
        """显示导入代理对话框"""
        # 懒加载对话框
        if self.import_proxies_dialog is None:
            from ..dialogs.import_proxies_dialog import ImportProxiesDialog
            self.import_proxies_dialog = ImportProxiesDialog(self)
            
        if self.import_proxies_dialog.exec() == QDialog.DialogCode.Accepted:
            proxies = self.import_proxies_dialog.get_proxies()
            # 将代理添加到代理池
            from src.core.proxy.imported_proxy_pool import ImportedProxyPool
            proxy_pool = ImportedProxyPool()
            
            # 准备批量导入的代理列表
            proxy_list = []
            for proxy in proxies:
                try:
                    # 解析代理信息
                    proxy_type, host, port, username, password, country = proxy.split(':')
                    # 添加到批量导入列表
                    proxy_list.append({
                        'proxy_type': proxy_type,
                        'host': host,
                        'port': port,
                        'username': username,
                        'password': password,
                        'country': country
                    })
                except Exception as e:
                    print(f"处理代理时出错: {str(e)}")
                    continue
            
            # 批量导入代理
            if proxy_list:
                success_count, fail_count, error_msg = proxy_pool.batch_add_proxies(proxy_list)
                if error_msg:
                    print(f"批量导入代理出错: {error_msg}")
                print(f"成功导入 {success_count} 个代理，{fail_count} 个代理导入失败")
                
                # 显示导入结果到状态标签
                self.status_label.setText(f"成功导入 {success_count} 个代理，{fail_count} 个代理导入失败")
                QTimer.singleShot(5000, lambda: self.status_label.setText(""))
                
                # 如果代理池管理对话框已经打开，则刷新显示
                if hasattr(self, 'proxy_pool_dialog') and self.proxy_pool_dialog is not None and self.proxy_pool_dialog.isVisible():
                    print("正在刷新已打开的代理池管理对话框...")
                    # 强制刷新代理池对话框
                    self.proxy_pool_dialog.load_proxies()
                
    def show_proxy_pool_dialog(self):
        """显示代理池管理对话框"""
        # 懒加载对话框
        if not hasattr(self, 'proxy_pool_dialog') or self.proxy_pool_dialog is None:
            from ..dialogs.proxy_pool_dialog import ProxyPoolDialog
            self.proxy_pool_dialog = ProxyPoolDialog(self)
            
        # 如果对话框已经打开，则刷新并激活
        if self.proxy_pool_dialog.isVisible():
            self.proxy_pool_dialog.load_proxies()
            self.proxy_pool_dialog.activateWindow()
        else:
            # 显示非模态对话框
            self.proxy_pool_dialog.show()
        
    def save_settings(self):
        """保存设置到配置文件"""
        # 重置状态标签样式为默认颜色
        self.status_label.setStyleSheet("color: #28A745; font-weight: bold;")
        
        # 确定当前使用的代理来源
        if self.api_radio.isChecked():
            proxy_source = "api"
        elif self.pool_radio.isChecked():
            proxy_source = "pool"
        elif self.fixed_radio.isChecked():
            proxy_source = "fixed"
        else:
            proxy_source = "direct"
            
        # 如果选择了固定代理，验证必填字段
        if proxy_source == "fixed":
            if not self.fixed_proxy_host.text().strip():
                self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                self.status_label.setText("错误: 固定代理的主机地址不能为空")
                QTimer.singleShot(5000, lambda: self.reset_status_label())
                return
                
            if not self.fixed_proxy_port.text().strip():
                self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                self.status_label.setText("错误: 固定代理的端口不能为空")
                QTimer.singleShot(5000, lambda: self.reset_status_label())
                return
                
            # 尝试验证端口是否为数字
            try:
                port = int(self.fixed_proxy_port.text().strip())
                if port <= 0 or port > 65535:
                    self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                    self.status_label.setText("错误: 端口必须在1-65535之间")
                    QTimer.singleShot(5000, lambda: self.reset_status_label())
                    return
            except ValueError:
                self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                self.status_label.setText("错误: 端口必须是数字")
                QTimer.singleShot(5000, lambda: self.reset_status_label())
                return
        
        # 如果选择了API获取，验证API URL不能为空
        if proxy_source == "api" and not self.api_url.text().strip():
            self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.status_label.setText("错误: API链接不能为空")
            QTimer.singleShot(5000, lambda: self.reset_status_label())
            return
            
        # 不再需要验证线程数，因为QSpinBox已经限制了输入范围
        
        # 先加载现有设置，以保留其他代理来源的配置
        existing_settings = self.config_manager.load_settings() or {}
        
        # 获取现有代理设置，如果不存在则创建新的结构
        proxy_settings = existing_settings.get("proxy", {})
        
        # 设置当前选择的代理来源
        proxy_settings["source"] = proxy_source
        
        # 为每种代理来源准备单独的配置部分
        # API 设置
        api_settings = proxy_settings.get("api", {})
        if proxy_source == "api":
            api_settings.update({
                "type": self.proxy_type.currentText(),
                "api_url": self.api_url.text()
            })
        proxy_settings["api"] = api_settings
        
        # 代理池设置
        pool_settings = proxy_settings.get("pool", {})
        if proxy_source == "pool":
            pool_settings.update({
                "allow_reuse": self.allow_reuse.isChecked()
            })
        proxy_settings["pool"] = pool_settings
        
        # 固定代理设置
        fixed_settings = proxy_settings.get("fixed", {})
        if proxy_source == "fixed":
            fixed_settings.update({
                "proxy_type": self.fixed_proxy_type.currentText(),
                "host": self.fixed_proxy_host.text(),
                "port": self.fixed_proxy_port.text(),
                "username": self.fixed_proxy_username.text(),
                "password": self.fixed_proxy_password.text()
            })
        proxy_settings["fixed"] = fixed_settings
        
        # 直连设置（为将来扩展预留）
        direct_settings = proxy_settings.get("direct", {})
        proxy_settings["direct"] = direct_settings
        
        # 更新代理设置
        existing_settings["proxy"] = proxy_settings
        
        # 更新通用设置
        existing_settings["general"] = {
            "ignore_ip_check": self.ignore_ip_check.isChecked(),
            "ip_country": self.country_data.get(self.country_selector.currentText(), "CN") if not self.ignore_ip_check.isChecked() else "",
            "thread_count": str(self.thread_count.value())
        }
        
        try:
            self.config_manager.save_settings(existing_settings)
            # 显示保存成功的消息在标签上，而不是弹窗
            self.status_label.setStyleSheet("color: #28A745; font-weight: bold;")
            self.status_label.setText("设置保存成功")
            # 3秒后清除消息
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        except Exception as e:
            self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.status_label.setText(f"保存失败: {str(e)}")
            # 5秒后清除错误消息
            QTimer.singleShot(5000, lambda: self.reset_status_label())
            
    def reset_status_label(self):
        """重置状态标签为默认状态"""
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #28A745; font-weight: bold;")
        
    def load_settings(self):
        """从配置文件加载设置"""
        settings = self.config_manager.load_settings()
        if not settings:
            return
            
        # 加载代理设置
        if "proxy" in settings:
            proxy = settings["proxy"]
            
            # 设置代理来源
            source = proxy.get("source", "api")
            if source == "api":
                self.api_radio.setChecked(True)
            elif source == "pool":
                self.pool_radio.setChecked(True)
            elif source == "fixed":
                self.fixed_radio.setChecked(True)
            elif source == "direct":
                self.direct_radio.setChecked(True)
                
            # 加载API设置
            api_settings = proxy.get("api", {})
            if api_settings:
                # 设置代理类型
                proxy_type = api_settings.get("type", "HTTP")
                index = self.proxy_type.findText(proxy_type)
                if index >= 0:
                    self.proxy_type.setCurrentIndex(index)
                    
                # 设置API链接
                self.api_url.setText(api_settings.get("api_url", ""))
                
            # 加载代理池设置
            pool_settings = proxy.get("pool", {})
            if pool_settings:
                # 设置允许重复使用
                self.allow_reuse.setChecked(pool_settings.get("allow_reuse", True))
                
            # 加载固定代理设置
            fixed_settings = proxy.get("fixed", {})
            if fixed_settings:
                # 设置代理类型
                fixed_proxy_type = fixed_settings.get("proxy_type", "HTTP")
                index = self.fixed_proxy_type.findText(fixed_proxy_type)
                if index >= 0:
                    self.fixed_proxy_type.setCurrentIndex(index)
                    
                # 设置主机、端口、用户名和密码
                self.fixed_proxy_host.setText(fixed_settings.get("host", ""))
                self.fixed_proxy_port.setText(fixed_settings.get("port", ""))
                self.fixed_proxy_username.setText(fixed_settings.get("username", ""))
                self.fixed_proxy_password.setText(fixed_settings.get("password", ""))
            
        # 加载通用设置
        if "general" in settings:
            general = settings["general"]
            
            # 设置忽略IP检查
            ignore_ip = general.get("ignore_ip_check", False)
            self.ignore_ip_check.setChecked(ignore_ip)
            
            # 设置IP所在地国家
            if not ignore_ip:
                country_code = general.get("ip_country", "CN")
                # 根据国家代码找到对应的国家名称
                country_name = next((name for name, code in self.country_data.items() if code == country_code), "中国")
                index = self.country_selector.findText(country_name)
                if index >= 0:
                    self.country_selector.setCurrentIndex(index)
            
            # 设置线程数
            try:
                thread_count = int(general.get("thread_count", "30"))
                self.thread_count.setValue(thread_count)
            except (ValueError, TypeError):
                self.thread_count.setValue(30)
            
            # 更新国家选择器的可见性
            self.update_country_selector_visibility()
        
    def parse_proxy_info(self, text):
        """解析输入的代理信息，如果是完整格式则自动填充各输入框"""
        # 检查文本中是否包含冒号，至少需要主机:端口格式
        if ":" in text:
            parts = text.split(":")
            # 如果有足够的部分
            if len(parts) >= 2:
                # 阻断textChanged信号，防止递归调用
                self.fixed_proxy_host.blockSignals(True)
                
                # 设置主机（第一部分）
                self.fixed_proxy_host.setText(parts[0])
                
                # 设置端口（第二部分）
                self.fixed_proxy_port.setText(parts[1])
                
                # 如果有用户名（第三部分）
                if len(parts) >= 3:
                    self.fixed_proxy_username.setText(parts[2])
                    
                # 如果有密码（第四部分）
                if len(parts) >= 4:
                    # 如果有多个冒号，后面的部分全部作为密码
                    self.fixed_proxy_password.setText(":".join(parts[3:]))
                
                # 恢复信号
                self.fixed_proxy_host.blockSignals(False) 

    def clear_fixed_proxy(self):
        """清空固定代理信息"""
        # 阻断主机输入框的信号，防止自动解析触发
        self.fixed_proxy_host.blockSignals(True)
        
        # 清空所有输入框
        self.fixed_proxy_host.clear()
        self.fixed_proxy_port.clear()
        self.fixed_proxy_username.clear()
        self.fixed_proxy_password.clear()
        
        # 恢复信号
        self.fixed_proxy_host.blockSignals(False)
        
        # 显示提示消息
        self.status_label.setStyleSheet("color: #28A745; font-weight: bold;")
        self.status_label.setText("固定代理信息已清空")
        # 2秒后清除消息
        QTimer.singleShot(2000, lambda: self.status_label.setText("")) 

    def update_country_selector_visibility(self):
        """更新国家选择器的可见性，根据是否勾选"忽略IP所在地检查"""
        is_ignored = self.ignore_ip_check.isChecked()
        self.country_label.setVisible(not is_ignored)
        self.country_selector.setVisible(not is_ignored)
        
    def preload_components(self):
        """预加载组件，用于后台异步初始化"""
        try:
            from src.utils.logger import get_logger
            logger = get_logger()
            logger.debug("预加载代理检查对话框组件...")
            
            # 预加载代理检查对话框类
            from ..dialogs.proxy_checker_dialog import ProxyCheckerDialog
            
            # 预初始化ProxyChecker（这会同时初始化IPDetector和国家映射器）
            from src.core.proxy.proxy_checker import ProxyChecker
            from src.utils.config_manager import ConfigManager
            
            # 初始化但不显示对话框
            self._proxy_checker_dialog = ProxyCheckerDialog(self)
            
            logger.debug("代理检查对话框组件预加载完成")
            
        except Exception as e:
            # 预加载失败不应该影响主程序，只记录日志
            from src.utils.logger import get_logger
            logger = get_logger()
            logger.error(f"预加载代理检查对话框组件失败: {str(e)}")
    
    def show_proxy_checker_dialog(self):
        """显示代理检查器设置对话框"""
        # 如果已经预加载，则直接使用
        if hasattr(self, '_proxy_checker_dialog'):
            self._proxy_checker_dialog.exec()
            return
            
        # 否则按需加载
        from ..dialogs.proxy_checker_dialog import ProxyCheckerDialog
        dialog = ProxyCheckerDialog(self)
        dialog.exec()
        
    def check_fixed_proxy(self):
        """检测固定代理
        
        使用_check_connection_async方法直接检测代理连接
        """
        # 检查是否填写了代理信息
        host = self.fixed_proxy_host.text().strip()
        port = self.fixed_proxy_port.text().strip()
        
        if not host or not port:
            self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.status_label.setText("错误: 请先填写代理主机和端口")
            QTimer.singleShot(3000, lambda: self.reset_status_label())
            return
            
        try:
            # 尝试将端口转换为整数
            port = int(port)
            if port <= 0 or port > 65535:
                self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                self.status_label.setText("错误: 端口必须在1-65535之间")
                QTimer.singleShot(3000, lambda: self.reset_status_label())
                return
        except ValueError:
            self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.status_label.setText("错误: 端口必须是数字")
            QTimer.singleShot(3000, lambda: self.reset_status_label())
            return
        
        # 构建代理信息
        proxy = {
            "host": host,
            "port": port,
            "protocol": self.fixed_proxy_type.currentText().lower(),
            "username": self.fixed_proxy_username.text(),
            "password": self.fixed_proxy_password.text()
        }
        
        # 更新状态提示
        self.status_label.setStyleSheet("color: #17A2B8; font-weight: bold;")
        self.status_label.setText("正在检测代理，请稍候...")
        
        # 禁用检测按钮，防止重复点击
        sender = self.sender()
        if sender:
            sender.setEnabled(False)
            sender.setText("检测中...")
            
        # 异步检测代理
        self._run_proxy_check(proxy, sender)
    
    def _run_proxy_check(self, proxy, button):
        """运行代理检测
        
        Args:
            proxy: 代理信息字典
            button: 触发检测的按钮
        """
        from src.core.proxy.proxy_checker import ProxyChecker
        from src.utils.config_manager import ConfigManager
        from src.utils.logger import get_logger
        import asyncio
        from PyQt6.QtCore import QThread, pyqtSignal, QTimer
        
        logger = get_logger()
        
        # 创建工作线程类
        class ProxyCheckThread(QThread):
            # 结果信号
            check_finished = pyqtSignal(bool, dict)
            
            def __init__(self, proxy_info, config_manager):
                super().__init__()
                self.proxy_info = proxy_info
                self.config_manager = config_manager
                
            def run(self):
                try:
                    # 创建事件循环
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # 初始化代理检查器
                    checker = ProxyChecker(self.config_manager)
                    
                    # 格式化代理URL
                    proxy_url = checker.format_proxy_url(self.proxy_info)
                    if not proxy_url:
                        self.check_finished.emit(False, {'success': False, 'error': "代理格式无效"})
                        return
                    
                    # 执行检测
                    success, result = loop.run_until_complete(checker._check_connection_async(None, proxy_url))
                    self.check_finished.emit(success, result)
                    
                except Exception as e:
                    logger.error(f"代理检测线程中发生错误: {str(e)}")
                    self.check_finished.emit(False, {'success': False, 'error': f"检测错误: {str(e)}"})
                finally:
                    if loop:
                        loop.close()
        
        # 创建并启动线程
        self.check_thread = ProxyCheckThread(proxy, self.config_manager)
        
        # 连接结果信号
        def on_check_finished(success, result):
            try:
                # 处理检测结果
                if success:
                    # 提取响应时间和国家/地区信息
                    response_time = result.get('response_time', 0)
                    country_code = result.get('country_code')
                    ip_address = result.get('ip', '未知')
                    
                    # 检查如果不忽略IP所在地检测，但没有获取到国家代码
                    if not self.ignore_ip_check.isChecked() and not country_code:
                        # 显示错误信息
                        self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                        self.status_label.setText("代理检测失败: 无法获取IP所在地信息")
                        logger.error(f"固定代理检测失败: {proxy.get('host')}:{proxy.get('port')} - 无法获取IP所在地信息")
                        return
                    
                    # 构建结果消息
                    msg = f"代理检测成功: 响应时间 {response_time}ms, IP: {ip_address}"
                    
                    # 如果有国家代码，显示国家/地区信息
                    if country_code:
                        from src.core.geo.country_mapper import get_mapper
                        country_mapper = get_mapper()
                        country_name = country_mapper.get_country_name(country_code) or "未知"
                        msg += f", 所在地: {country_name}({country_code})"
                    
                    # 更新状态显示
                    self.status_label.setStyleSheet("color: #28A745; font-weight: bold;")
                    self.status_label.setText(msg)
                    logger.info(f"固定代理检测成功: {proxy.get('host')}:{proxy.get('port')} - {msg}")
                else:
                    # 获取错误信息
                    error = result.get('error', '未知错误')
                    
                    # 更新状态显示
                    self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                    self.status_label.setText(f"代理检测失败: {error}")
                    logger.error(f"固定代理检测失败: {proxy.get('host')}:{proxy.get('port')} - {error}")
            except Exception as e:
                # 处理意外异常
                logger.error(f"处理代理检测结果时出错: {str(e)}")
                self.status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                self.status_label.setText(f"检测发生错误: {str(e)}")
            finally:
                # 恢复按钮状态
                if button:
                    button.setEnabled(True)
                    button.setText("代理检测")
                # 设置定时器，5秒后清除状态消息
                QTimer.singleShot(5000, lambda: self.reset_status_label())
        
        # 连接信号
        self.check_thread.check_finished.connect(on_check_finished)
        
        # 启动线程
        self.check_thread.start()
    
    def _reset_check_button(self, button):
        """重置检测按钮状态"""
        if button:
            button.setEnabled(True)
            button.setText("代理检测")
        
    # 移除 on_proxy_check_result 方法，由自定义实现替代 