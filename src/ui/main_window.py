from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, 
                             QTabWidget, QSplitter, QStatusBar, QLabel, QProgressBar)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
import os
import sys

def get_screen_size():
    """获取屏幕尺寸"""
    from PyQt6.QtWidgets import QApplication
    screen = QApplication.primaryScreen().geometry()
    return screen.width(), screen.height()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._test_tab = None
        self._settings_tab = None
        self._log_widget = None
        
        self.init_ui()
        self.set_window_icon()
        self.init_statusbar()
        
    def init_ui(self):
        self.setWindowTitle("带代理管理器的pyqt6框架")
        
        # 获取屏幕尺寸并设置窗口大小为屏幕的0.62
        screen_width, screen_height = get_screen_size()
        self.resize(int(screen_width * 0.62), int(screen_height * 0.62))
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(8, 8, 8, 8)  # 减小边距
        layout.setSpacing(0)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)  # 减小分割器手柄宽度
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #DDE1E6;
                margin: 0px 1px;  /* 减小边距 */
            }
        """)
        
        # 创建左侧标签页
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #DDE1E6;
                border-radius: 4px;
                background: white;
                top: -1px;  /* 将内容区向上移动，减少标签与内容的间距 */
            }
            QTabBar::tab {
                padding: 4px 10px;  /* 减小内边距 */
                margin-right: 2px;  /* 减小标签间距 */
                border: 1px solid #DDE1E6;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                background: #F8F9FA;
                min-width: 60px;  /* 设置最小宽度 */
                max-width: 100px; /* 设置最大宽度 */
            }
            QTabBar::tab:selected {
                background: white;
                margin-bottom: -1px;
                padding-bottom: 5px;  /* 选中标签底部加点内边距 */
            }
        """)
        
        # 使用懒加载方式添加标签页
        tab_widget.addTab(self.test_tab, "测试")
        tab_widget.addTab(self.settings_tab, "设置")
        
        # 将组件添加到分割器
        splitter.addWidget(tab_widget)
        splitter.addWidget(self.log_widget)
        
        # 设置分割器的初始大小
        screen_width = get_screen_size()[0]
        splitter.setSizes([int(screen_width * 0.7), int(screen_width * 0.3)])
        
        # 将分割器添加到主布局
        layout.addWidget(splitter)
        
    def init_statusbar(self):
        """初始化状态栏，包含加载指示器"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # 创建加载指示器
        self.loading_label = QLabel("正在后台加载核心模块...")
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)  # 不确定进度模式
        self.loading_progress.setMaximumSize(QSize(120, 16))  # 设置最大尺寸
        self.loading_progress.setTextVisible(False)  # 不显示文本
        self.loading_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #F8F9FA;
                border-radius: 2px;
                max-height: 4px;
            }
            QProgressBar::chunk {
                background-color: #007BFF;
                border-radius: 2px;
            }
        """)
        
        # 将加载指示器添加到状态栏
        status_bar.addWidget(self.loading_label)
        status_bar.addWidget(self.loading_progress)
        
    def on_preload_finished(self):
        """预加载完成回调"""
        # 移除加载指示器
        if hasattr(self, 'loading_label'):
            self.loading_label.setText("核心模块加载完成")
            self.loading_progress.setRange(0, 100)
            self.loading_progress.setValue(100)
            
            # 0.5秒后隐藏加载指示器和状态栏
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self.statusBar().clearMessage())
            QTimer.singleShot(500, self.loading_label.hide)
            QTimer.singleShot(500, self.loading_progress.hide)
            # 完全隐藏状态栏
            QTimer.singleShot(500, lambda: self.statusBar().hide())

    @property
    def test_tab(self):
        """懒加载测试标签页"""
        if self._test_tab is None:
            from .tabs.test_tab import TestTab
            self._test_tab = TestTab()
        return self._test_tab
    
    @property
    def settings_tab(self):
        """懒加载设置标签页"""
        if self._settings_tab is None:
            from .tabs.settings_tab import SettingsTab
            self._settings_tab = SettingsTab()
        return self._settings_tab
    
    @property
    def log_widget(self):
        """懒加载日志组件"""
        if self._log_widget is None:
            from .widgets.log_widget import LogWidget
            self._log_widget = LogWidget()
        return self._log_widget
        
    def set_window_icon(self):
        """设置窗口图标"""
        # 尝试从不同位置查找图标
        icon_paths = [
            'icon.ico',  # 当前目录
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../icon.ico'),  # 项目根目录
        ]
        
        # 如果是打包后的可执行文件，尝试从资源目录获取图标
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_paths.append(os.path.join(base_path, 'icon.ico'))
        
        # 尝试设置图标
        for path in icon_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break
        
    def get_log_widget(self):
        """获取日志框组件"""
        return self.log_widget 