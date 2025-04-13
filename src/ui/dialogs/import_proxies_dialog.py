from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QComboBox
)
from PyQt6.QtCore import Qt
from src.core.geo.country_mapper import get_mapper

class ImportProxiesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导入代理")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        # 获取国家映射器
        self.country_mapper = get_mapper()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 代理类型和国家选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("代理类型:"))
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["HTTP", "SOCKS5"])
        type_layout.addWidget(self.proxy_type)
        
        type_layout.addWidget(QLabel("国家:"))
        self.country = QComboBox()
        # 获取界面使用的国家列表
        self.country_data = self.country_mapper.get_ui_country_data()
        self.country.addItems(self.country_data.keys())
        type_layout.addWidget(self.country)
        
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # 说明文本
        help_text = QLabel(
            "请输入代理信息，格式：host:port:username:password\n"
            "每行一条代理，例如：\n"
            "192.168.1.1:8080:user1:pass1\n"
            "192.168.1.2:8081:user2:pass2"
        )
        help_text.setStyleSheet("color: #666666; padding: 10px 0;")
        layout.addWidget(help_text)
        
        # 文本输入框
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("在此粘贴代理信息...")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #DDE1E6;
                border-radius: 4px;
                padding: 8px;
                font-family: Consolas, Monaco, monospace;
            }
        """)
        layout.addWidget(self.text_edit)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        import_btn = QPushButton("导入")
        import_btn.setFixedWidth(100)
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
        import_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
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
        
        button_layout.addStretch()
        button_layout.addWidget(import_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
    def get_proxies(self) -> list:
        """获取处理后的代理列表"""
        proxy_type = self.proxy_type.currentText()
        country_name = self.country.currentText()
        country_code = self.country_data.get(country_name, "OTHER")
        text = self.text_edit.toPlainText().strip()
        
        # 使用列表推导式和更高效的字符串处理
        proxies = [
            f"{proxy_type}:{host}:{port}:{username}:{password}:{country_code}"
            for line in text.splitlines()
            if line.strip() and len(line.split(':')) == 4
            for host, port, username, password in [line.strip().split(':')]
        ]
                
        return proxies 