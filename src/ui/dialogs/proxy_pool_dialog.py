from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QLabel, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QCoreApplication
from src.core.proxy.imported_proxy_pool import ImportedProxyPool

class ProxyLoaderThread(QThread):
    """加载代理的后台线程"""
    proxies_loaded = pyqtSignal(list)  # 信号：加载完成
    
    def __init__(self, proxy_pool):
        super().__init__()
        self.proxy_pool = proxy_pool
        
    def run(self):
        """线程执行函数，在后台加载代理"""
        # 先强制从数据库重新加载代理
        self.proxy_pool._load_proxies_from_db()
        # 然后获取代理列表
        proxies = self.proxy_pool.get_proxies()
        self.proxies_loaded.emit(proxies)

class ProxyPoolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 使用全局单例代理池
        self.proxy_pool = ImportedProxyPool()
        self.init_ui()
        
        # 加载中指示器
        self.loading_indicator = QProgressBar(self)
        self.loading_indicator.setTextVisible(False)
        self.loading_indicator.setFixedHeight(4)
        self.loading_indicator.setRange(0, 0)  # 设置为循环模式
        self.loading_indicator.hide()
        
        # 将加载指示器添加到布局中 - 在表格上方
        self.main_layout.insertWidget(1, self.loading_indicator)
        
        # 创建加载线程
        self.loader_thread = None
        
        # 添加定时刷新功能 - 每30秒刷新一次(增加到30秒减少刷新频率)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_proxies)
        self.refresh_timer.start(30000)  # 30秒刷新一次
        
        # 设置分页加载
        self.page_size = 100  # 每页显示数量
        self.current_page = 0
        self.all_proxies = []  # 存储所有代理
        
        # 加载第一页数据
        self.load_proxies()
        
    def showEvent(self, event):
        """对话框显示时触发"""
        super().showEvent(event)
        # 每次显示对话框时都刷新数据
        self.load_proxies()
        # 启动定时刷新
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(30000)
            
    def hideEvent(self, event):
        """对话框隐藏时触发"""
        super().hideEvent(event)
        # 停止定时刷新，节省资源
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            
    def closeEvent(self, event):
        """对话框关闭时触发"""
        super().closeEvent(event)
        # 停止定时刷新，节省资源
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        
    def init_ui(self):
        self.setWindowTitle("代理池管理")
        self.setMinimumWidth(800)
        self.setMinimumHeight(400)
        
        self.main_layout = QVBoxLayout(self)
        
        # 头部按钮布局
        header_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(100)
        refresh_btn.setStyleSheet("""
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
        refresh_btn.clicked.connect(self.load_proxies)
        
        clear_btn = QPushButton("清空")
        clear_btn.setFixedWidth(100)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC3545;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
            QPushButton:pressed {
                background-color: #BD2130;
            }
        """)
        clear_btn.clicked.connect(self.clear_proxies)
        
        # 添加代理计数器
        self.proxy_counter = QLabel("代理数量: 0")
        
        header_layout.addWidget(refresh_btn)
        header_layout.addWidget(clear_btn)
        header_layout.addStretch()
        header_layout.addWidget(self.proxy_counter)
        
        self.main_layout.addLayout(header_layout)
        
        # 代理列表表格
        self.proxy_table = QTableWidget()
        self.proxy_table.setColumnCount(7)  # 增加国家列
        self.proxy_table.setHorizontalHeaderLabels(["类型", "主机", "端口", "用户名", "密码", "国家", "状态"])
        self.proxy_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #DDE1E6;
                border-radius: 4px;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #DDE1E6;
            }
            QTableWidget::item {
                padding: 8px;
            }
        """)
        
        # 设置表格为只读
        self.proxy_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 设置列宽
        self.proxy_table.setColumnWidth(0, 80)   # 类型
        self.proxy_table.setColumnWidth(1, 150)  # 主机
        self.proxy_table.setColumnWidth(2, 80)   # 端口
        self.proxy_table.setColumnWidth(3, 100)  # 用户名
        self.proxy_table.setColumnWidth(4, 100)  # 密码
        self.proxy_table.setColumnWidth(5, 80)   # 国家
        self.proxy_table.setColumnWidth(6, 80)   # 状态
        
        self.main_layout.addWidget(self.proxy_table)
        
        # 分页导航
        page_layout = QHBoxLayout()
        prev_btn = QPushButton("上一页")
        prev_btn.setFixedWidth(80)
        prev_btn.clicked.connect(self.prev_page)
        
        next_btn = QPushButton("下一页")
        next_btn.setFixedWidth(80)
        next_btn.clicked.connect(self.next_page)
        
        self.page_info = QLabel("第 1 页")
        
        page_layout.addStretch()
        page_layout.addWidget(prev_btn)
        page_layout.addWidget(self.page_info)
        page_layout.addWidget(next_btn)
        page_layout.addStretch()
        
        self.main_layout.addLayout(page_layout)
        
    def load_proxies(self):
        """异步加载代理列表"""
        
        # 处理线程逻辑前先处理UI
        self.loading_indicator.show()
        QCoreApplication.processEvents()  # 强制处理事件队列，确保UI更新
        
        if self.loader_thread and self.loader_thread.isRunning():
            return
            
        # 创建并启动加载线程
        self.loader_thread = ProxyLoaderThread(self.proxy_pool)
        self.loader_thread.proxies_loaded.connect(self.on_proxies_loaded)
        self.loader_thread.finished.connect(self.on_loading_finished)
        self.loader_thread.start()
    
    def on_proxies_loaded(self, proxies):
        """当代理加载完成后更新UI"""
        self.all_proxies = proxies
        self.current_page = 0
        self.update_table()
        
        # 更新代理计数
        self.proxy_counter.setText(f"代理数量: {len(self.all_proxies)}")
        
    def on_loading_finished(self):
        """当加载线程完成时隐藏加载指示器"""
        self.loading_indicator.hide()
    
    def update_table(self):
        """根据当前页码更新表格"""
        self.proxy_table.setRowCount(0)
        
        # 如果没有代理，直接返回
        if not self.all_proxies:
            self.page_info.setText("没有代理")
            return
            
        # 计算当前页的代理
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.all_proxies))
        current_proxies = self.all_proxies[start_idx:end_idx]
        
        # 更新页码信息
        total_pages = max(1, (len(self.all_proxies) + self.page_size - 1) // self.page_size)
        self.page_info.setText(f"第 {self.current_page + 1} 页 / 共 {total_pages} 页")
        
        # 填充表格
        for proxy in current_proxies:
            row = self.proxy_table.rowCount()
            self.proxy_table.insertRow(row)
            
            # 设置代理信息
            self.proxy_table.setItem(row, 0, QTableWidgetItem(proxy.get("proxy_type", "")))
            self.proxy_table.setItem(row, 1, QTableWidgetItem(proxy.get("host", "")))
            self.proxy_table.setItem(row, 2, QTableWidgetItem(str(proxy.get("port", ""))))
            self.proxy_table.setItem(row, 3, QTableWidgetItem(proxy.get("username", "")))
            self.proxy_table.setItem(row, 4, QTableWidgetItem(proxy.get("password", "")))
            self.proxy_table.setItem(row, 5, QTableWidgetItem(proxy.get("country", "未知")))
            
            # 设置状态 - 从"可用/不可用"改为"已使用/未使用"
            status = proxy.get("status", "unused")
            is_used = status == "used"
            status_text = "已使用" if is_used else "未使用"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(Qt.GlobalColor.red if is_used else Qt.GlobalColor.green)
            self.proxy_table.setItem(row, 6, status_item)
    
    def prev_page(self):
        """查看上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_table()
    
    def next_page(self):
        """查看下一页"""
        if (self.current_page + 1) * self.page_size < len(self.all_proxies):
            self.current_page += 1
            self.update_table()
            
    def clear_proxies(self):
        """清空代理池"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认清空")
        msg_box.setText("确定要清空代理池吗？")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        confirm_btn = msg_box.addButton("确认", QMessageBox.ButtonRole.YesRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(cancel_btn)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == confirm_btn:
            self.proxy_pool.clear_all()
            self.all_proxies = []
            self.current_page = 0
            self.update_table()
            self.proxy_counter.setText("代理数量: 0") 