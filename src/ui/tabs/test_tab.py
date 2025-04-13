from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class TestTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)  # 减小顶部边距
        layout.setSpacing(6)  # 减小控件间距
        
        label = QLabel("测试标签页")
        layout.addWidget(label) 