from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QProgressBar, QLabel
from PyQt6.QtCore import Qt, QTimer
from datetime import datetime
from queue import Queue
from .custom_text_edit import LogTextEdit
from src.utils.logger import get_logger

class LogWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.auto_scroll = True  # 控制是否自动滚动
        self.log_queue = Queue()  # 日志队列
        self.log_timer = QTimer(self)  # 定时器用于处理队列中的日志
        self.log_timer.timeout.connect(self.process_log_queue)
        self.log_timer.start(100)  # 每100ms检查一次队列
        self.init_ui()
        self.connect_signals()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 0, 0)  # 添加左边距
        
        # 创建工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 8)  # 底部添加一点间距
        
        # 清空按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.setFixedWidth(80)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC3545;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
            QPushButton:pressed {
                background-color: #BD2130;
            }
        """)
        clear_btn.clicked.connect(self.clear_log)
        
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # 创建进度条布局
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1)  # 初始设置为1，避免0/0的情况，后续会动态调整
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(15)  # 增加高度以容纳文本
        self.progress_bar.setFormat("%v/%m")  # 设置格式为"当前值/最大值"
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 文本居中对齐
        # 初始状态下不显示文本
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #F8F9FA;
                border: none;
                border-radius: 3px;
                text-align: center;
                color: #6C757D;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #28A745;
                border-radius: 3px;
            }
        """)
        
        progress_layout.addWidget(self.progress_bar, stretch=1)  # 进度条占据大部分空间
        
        layout.addLayout(progress_layout)
        layout.addSpacing(8)  # 在进度条下方添加一点间距
        
        # 创建日志文本框
        self.log_text = LogTextEdit(placeholder="日志信息将在这里显示...")
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 4px;
                padding: 8px;
                font-family: "Microsoft YaHei", "微软雅黑";
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        
        # 连接滚动条值改变信号
        self.log_text.verticalScrollBar().valueChanged.connect(self.on_scroll)
        # 连接文档内容改变信号
        self.log_text.textChanged.connect(self.on_text_changed)
        
        layout.addWidget(self.log_text)
    
    def connect_signals(self):
        """连接日志管理器和进度管理器的信号"""
        try:
            # 获取Logger实例
            logger = get_logger()
            
            # 连接日志信号，确保使用Qt.QueuedConnection
            logger.signals.log_message.connect(self.on_log_message, Qt.ConnectionType.QueuedConnection)
            
            # 连接进度管理器信号
            from src.utils.progress_manager import get_progress_manager
            progress_manager = get_progress_manager()
            progress_manager.signals.progress_update.connect(self.update_progress, Qt.ConnectionType.QueuedConnection)
            progress_manager.signals.progress_reset.connect(self.reset_progress, Qt.ConnectionType.QueuedConnection)
        except Exception as e:
            print(f"连接信号失败: {str(e)}")
        
    def on_log_message(self, message: str):
        """接收日志信号并添加到队列
        
        日志消息已在logger中格式化，包含时间戳和级别
        """
        self.log_queue.put(message)
    
    def append_log(self, message: str):
        """添加日志信息到队列（保留此方法以兼容现有代码）
        
        为了兼容原有代码，这里仍然添加时间戳
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] [信息] {message}"
        self.log_queue.put(formatted_message)
    
    def process_log_queue(self):
        """处理队列中的日志消息"""
        messages = []
        # 一次性处理队列中的所有消息
        while not self.log_queue.empty() and len(messages) < 100:  # 限制每次处理的消息数量
            try:
                message = self.log_queue.get_nowait()
                messages.append(message)
            except:
                break
        
        if messages:
            # 批量添加消息
            self.log_text.append('\n'.join(messages))
            
            # 如果启用了自动滚动，滚动到底部
            if self.auto_scroll:
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self):
        """清空日志"""
        # 清空队列
        while not self.log_queue.empty():
            try:
                self.log_queue.get_nowait()
            except:
                break
        # 清空文本框
        self.log_text.clear()
        
    def on_scroll(self, value):
        """滚动条值改变时的处理函数"""
        scrollbar = self.log_text.verticalScrollBar()
        # 如果用户向上滚动，禁用自动滚动
        if value < scrollbar.maximum():
            self.auto_scroll = False
        # 如果用户滚动到底部，启用自动滚动
        else:
            self.auto_scroll = True
            
    def on_text_changed(self):
        """文本内容改变时的处理函数"""
        if self.auto_scroll:
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event):
        """窗口关闭时的处理"""
        self.log_timer.stop()
        super().closeEvent(event)

    def update_progress(self, current: int, total: int):
        """更新进度条和进度文本
        Args:
            current: 当前处理数量
            total: 总数量
        """
        try:
            if total > 0:
                # 设置进度条的最大值为总数量
                self.progress_bar.setMaximum(total)
                # 设置进度条的当前值为当前数量
                self.progress_bar.setValue(current)
                # 当current为0时隐藏文本
                self.progress_bar.setTextVisible(current > 0)
            else:
                self.progress_bar.setValue(0)
                self.progress_bar.setTextVisible(False)
        except Exception as e:
            print(f"更新进度条失败: {str(e)}")

    def reset_progress(self):
        """重置进度条和进度文本"""
        try:
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
        except Exception as e:
            print(f"重置进度条失败: {str(e)}") 