from PyQt6.QtCore import QObject, pyqtSignal
import threading

# 定义进度条信号类
class ProgressSignals(QObject):
    """进度信号类，用于在UI中更新进度条"""
    progress_update = pyqtSignal(int, int)  # 参数: current, total
    progress_reset = pyqtSignal()

# 单例模式的进度管理器
class ProgressManager:
    _instance = None
    _initialized = False
    _lock = threading.RLock()  # 添加线程锁确保并发安全
    
    @classmethod
    def instance(cls):
        """获取ProgressManager单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """初始化进度管理器，只在第一次调用时执行"""
        if ProgressManager._initialized:
            return
            
        self.signals = ProgressSignals()
        # 内部状态
        self._current = 0
        self._total = 0
        self._active = False  # 是否有活动的任务
        ProgressManager._initialized = True
        
    def start(self, total):
        """开始一个新任务并设置总数
        Args:
            total: 任务总数量
        """
        with self._lock:
            if not isinstance(total, int) or total <= 0:
                print("任务总数必须是大于0的整数")
                return False
                
            # 重置计数器
            self._current = 0
            self._total = total
            self._active = True
            
            # 发送初始进度信号
            self.signals.progress_update.emit(0, total)
            return True
    
    def increment(self, amount=1):
        """增加当前进度计数
        Args:
            amount: 增加的数量，默认为1
        Returns:
            bool: 是否成功更新
        """
        with self._lock:
            # 检查是否有活动任务
            if not self._active:
                print("没有活动的任务，请先调用start()")
                return False
                
            # 增加当前计数
            self._current += amount
            
            # 确保不超过总数
            if self._current > self._total:
                self._current = self._total
                
            # 发送进度更新信号
            self.signals.progress_update.emit(self._current, self._total)
            
            # 如果已完成，自动调用complete
            if self._current >= self._total:
                self.complete()
                
            return True
    
    def complete(self):
        """标记当前任务完成（将current设为等于total）"""
        with self._lock:
            if not self._active:
                return False
                
            # 设置当前计数为总数
            self._current = self._total
            
            # 发送最终进度更新
            self.signals.progress_update.emit(self._current, self._total)
            
            # 重置活动状态
            self._active = False
            return True
    
    def reset(self):
        """重置进度条，取消当前任务"""
        with self._lock:
            self._current = 0
            self._total = 0
            self._active = False
            self.signals.progress_reset.emit()
            
    def get_progress(self):
        """获取当前进度状态
        Returns:
            tuple: (current, total, active)
        """
        with self._lock:
            return self._current, self._total, self._active

# 便捷函数，用于快速访问进度条功能
def get_progress_manager():
    """获取ProgressManager实例的便捷方法"""
    return ProgressManager.instance()

# 快捷函数
def start_progress(total):
    """开始一个新的进度任务"""
    return get_progress_manager().start(total)
    
def increment_progress(amount=1):
    """增加进度计数"""
    return get_progress_manager().increment(amount)
    
def complete_progress():
    """完成当前进度任务"""
    return get_progress_manager().complete()
    
def reset_progress():
    """重置进度"""
    return get_progress_manager().reset() 