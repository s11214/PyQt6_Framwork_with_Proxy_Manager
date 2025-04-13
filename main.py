import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QThread, pyqtSignal
import os
import time

class PreloadThread(QThread):
    """预加载关键模块的后台线程"""
    finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        """在后台线程中预加载关键模块"""
        try:
            # 延迟一小段时间，确保主窗口已完全加载
            time.sleep(0.5)
            
            # 预加载ProxyChecker和IPDetector - 仅加载非UI组件
            from src.core.proxy.proxy_checker import ProxyChecker
            from src.utils.config_manager import ConfigManager
            from src.utils.logger import get_logger
            
            logger = get_logger()
            logger.debug("开始预加载核心模块...")
            
            # 初始化ConfigManager
            config_manager = ConfigManager()
            
            # 预初始化ProxyChecker，这会同时初始化IPDetector和国家映射器
            proxy_checker = ProxyChecker(config_manager)
            
            # 不要在工作线程中加载/创建UI组件
            # 不再尝试加载SettingsTab组件和ProxyCheckerDialog
            
            logger.debug("核心模块预加载完成")
            
        except Exception as e:
            # 预加载失败不应该影响主程序，只记录日志
            from src.utils.logger import get_logger
            logger = get_logger()
            logger.error(f"预加载模块失败: {str(e)}")
        
        # 发送完成信号
        self.finished.emit()

def main():
    app_name = "PyQt6_Framework_with_Proxy_Manager"
    app = QApplication(sys.argv)
    app.setApplicationName(app_name)
    app.setOrganizationName(app_name)
    
    # 在用户目录下创建应用程序文件夹
    app_dir_name = app.applicationName()
    user_dir = os.path.expanduser("~")
    app_dir_path = os.path.join(user_dir, app_dir_name)
    if not os.path.exists(app_dir_path):
        os.makedirs(app_dir_path)
    
    # 调用统一的目录初始化函数
    from src.utils.app_path import initialize_app_dirs
    app_paths = initialize_app_dirs()
    
    # 记录应用路径初始化
    from src.utils.logger import get_logger
    logger = get_logger()
    logger.debug(f"应用路径初始化完成: {app_paths}")
    
    # 设置应用程序图标 - 懒加载，只在需要时加载
    def load_app_icon():
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if not os.path.exists(icon_path) and getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件，尝试从资源目录获取图标
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_path, 'icon.ico')
        
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            app.setWindowIcon(app_icon)
    
    # 初始化日志模块 - 仅导入模块，不立即初始化
    from src.utils import logger
    from src.utils import progress_manager
    
    # 延迟导入MainWindow类，减少启动时间
    from src.ui.main_window import MainWindow
    
    # 在展示窗口前加载图标
    load_app_icon()
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 启动预加载线程
    preload_thread = PreloadThread()
    preload_thread.finished.connect(window.on_preload_finished)
    preload_thread.start()
    
    # 退出前记录日志
    exit_code = app.exec()
    logger.info("应用程序退出")
    return exit_code

if __name__ == '__main__':
    sys.exit(main()) 