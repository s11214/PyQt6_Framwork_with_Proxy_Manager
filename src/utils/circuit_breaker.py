import time
import asyncio
from typing import Callable, Dict, Any, Optional, List, Union, Tuple
from enum import Enum, auto
import threading
from src.utils.logger import get_logger

logger = get_logger()

class CircuitState(Enum):
    """熔断器状态枚举"""
    CLOSED = auto()     # 关闭状态（正常工作）
    OPEN = auto()       # 开启状态（熔断激活）
    HALF_OPEN = auto()  # 半开状态（尝试恢复）

class FailureType(Enum):
    """失败类型枚举"""
    CONSECUTIVE = auto()  # 连续失败
    PERCENTAGE = auto()   # 失败百分比
    TOTAL = auto()        # 总失败次数

class CircuitBreakerEvent:
    """熔断器事件类"""
    
    def __init__(self, state: CircuitState, failure_count: int, reason: str = None,
                 failure_percentage: float = None, context: Optional[Dict[str, Any]] = None):
        """初始化熔断器事件
        
        Args:
            state: 熔断器状态
            failure_count: 失败计数
            reason: 失败原因
            failure_percentage: 失败百分比（只在百分比模式下有值）
            context: 上下文信息
        """
        self.state = state
        self.failure_count = failure_count
        self.reason = reason
        self.failure_percentage = failure_percentage
        self.context = context or {}
        self.timestamp = time.time()

class CircuitBreaker:
    """通用熔断器类
    
    可以被任何任务复用的熔断器，支持同步和异步调用方式，
    提供事件通知机制，支持多种熔断策略。
    
    熔断器有三种状态：
    - CLOSED：正常状态，允许执行操作
    - OPEN：熔断状态，拒绝执行操作
    - HALF_OPEN：半开状态，允许有限的操作来测试系统是否恢复
    
    支持的熔断策略：
    - 连续失败次数：当连续失败次数达到阈值时触发熔断
    - 失败百分比：当在窗口期内的失败百分比达到阈值时触发熔断
    - 总失败次数：当在窗口期内的总失败次数达到阈值时触发熔断
    """
    
    def __init__(self, name: str = "default",
                 failure_threshold: int = 5,
                 reset_timeout: int = 60,
                 failure_type: FailureType = FailureType.CONSECUTIVE,
                 window_size: int = 10,
                 failure_rate_threshold: float = 0.5,
                 half_open_max_trials: int = 1):
        """初始化熔断器
        
        Args:
            name: 熔断器名称，用于日志和事件识别
            failure_threshold: 失败阈值，根据failure_type的不同有不同含义
            reset_timeout: 重置超时时间（秒）
            failure_type: 失败类型，控制熔断器的触发方式
            window_size: 窗口大小，在失败百分比和总失败次数模式下使用
            failure_rate_threshold: 失败率阈值，在失败百分比模式下使用
            half_open_max_trials: 半开状态下允许的最大尝试次数
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_type = failure_type
        self.window_size = window_size
        self.failure_rate_threshold = failure_rate_threshold
        self.half_open_max_trials = half_open_max_trials
        
        # 内部状态
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_reason = None
        self._last_state_change = time.time()
        self._half_open_trial_count = 0
        
        # 窗口期内的结果记录
        self._results_window: List[bool] = []
        
        # 锁：确保线程安全
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        
        # 事件监听器
        self._listeners: List[Callable[[CircuitBreakerEvent], None]] = []
        self._async_listeners: List[Callable[[CircuitBreakerEvent], asyncio.Future]] = []
        
        logger.debug(f"熔断器[{self.name}]已初始化: 类型={failure_type.name}, 阈值={failure_threshold}")
    
    @property
    def state(self) -> CircuitState:
        """获取当前熔断器状态"""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """熔断器是否关闭（正常状态）"""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """熔断器是否打开（熔断状态）"""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """熔断器是否半开（测试状态）"""
        return self._state == CircuitState.HALF_OPEN
        
    def add_listener(self, listener: Callable[[CircuitBreakerEvent], None]) -> None:
        """添加同步事件监听器
        
        Args:
            listener: 监听器函数，接收熔断器事件作为参数
        """
        with self._lock:
            self._listeners.append(listener)
    
    def add_async_listener(self, listener: Callable[[CircuitBreakerEvent], asyncio.Future]) -> None:
        """添加异步事件监听器
        
        Args:
            listener: 异步监听器函数，接收熔断器事件作为参数
        """
        with self._lock:
            self._async_listeners.append(listener)
    
    def remove_listener(self, listener: Callable) -> bool:
        """移除事件监听器
        
        Args:
            listener: 要移除的监听器函数
            
        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            try:
                self._listeners.remove(listener)
                return True
            except ValueError:
                pass
                
            try:
                self._async_listeners.remove(listener)
                return True
            except ValueError:
                pass
                
            return False
    
    def execute(self, action: Callable[[], Any], fallback: Optional[Callable[[], Any]] = None,
                on_success: Optional[Callable[[Any], None]] = None,
                on_failure: Optional[Callable[[Exception], None]] = None) -> Any:
        """执行受熔断器保护的同步操作
        
        Args:
            action: 要执行的操作函数
            fallback: 发生错误或熔断时的回退函数
            on_success: 操作成功时的回调函数
            on_failure: 操作失败时的回调函数
            
        Returns:
            Any: 操作结果或回退结果
            
        Raises:
            Exception: 如果没有提供回退函数，且操作失败，则抛出原始异常
        """
        allow_request = False
        
        with self._lock:
            # 检查熔断器状态
            if self._state == CircuitState.CLOSED:
                allow_request = True
            elif self._state == CircuitState.OPEN:
                # 检查是否超过重置超时时间
                if time.time() > self._last_state_change + self.reset_timeout:
                    # 转换到半开状态
                    self._transition_to_state(CircuitState.HALF_OPEN)
                    allow_request = True
                    self._half_open_trial_count = 1
                    logger.info(f"熔断器[{self.name}]从OPEN转为HALF_OPEN状态，允许测试请求")
                else:
                    allow_request = False
                    time_left = int(self._last_state_change + self.reset_timeout - time.time())
                    logger.debug(f"熔断器[{self.name}]拒绝请求，熔断状态，还需等待 {time_left} 秒")
            elif self._state == CircuitState.HALF_OPEN:
                # 检查是否已达到最大测试次数
                if self._half_open_trial_count < self.half_open_max_trials:
                    allow_request = True
                    self._half_open_trial_count += 1
                    logger.debug(f"熔断器[{self.name}]处于HALF_OPEN状态，允许测试请求 ({self._half_open_trial_count}/{self.half_open_max_trials})")
                else:
                    allow_request = False
                    logger.debug(f"熔断器[{self.name}]拒绝额外的测试请求，已达到最大测试次数")
        
        if not allow_request:
            # 如果请求被拒绝且提供了回退函数，则执行回退函数
            if fallback:
                return fallback()
            else:
                raise RuntimeError(f"熔断器[{self.name}]已打开，拒绝执行操作")
        
        # 执行受保护的操作
        try:
            result = action()
            self._on_success()
            if on_success:
                on_success(result)
            return result
        except Exception as e:
            self._on_failure(str(e))
            if on_failure:
                on_failure(e)
            if fallback:
                return fallback()
            raise
    
    async def execute_async(self, action: Callable[[], asyncio.Future], 
                           fallback: Optional[Callable[[], asyncio.Future]] = None,
                           on_success: Optional[Callable[[Any], asyncio.Future]] = None,
                           on_failure: Optional[Callable[[Exception], asyncio.Future]] = None) -> Any:
        """执行受熔断器保护的异步操作
        
        Args:
            action: 要执行的异步操作函数
            fallback: 发生错误或熔断时的异步回退函数
            on_success: 操作成功时的异步回调函数
            on_failure: 操作失败时的异步回调函数
            
        Returns:
            Any: 操作结果或回退结果
            
        Raises:
            Exception: 如果没有提供回退函数，且操作失败，则抛出原始异常
        """
        allow_request = False
        
        async with self._async_lock:
            # 检查熔断器状态
            if self._state == CircuitState.CLOSED:
                allow_request = True
            elif self._state == CircuitState.OPEN:
                # 检查是否超过重置超时时间
                if time.time() > self._last_state_change + self.reset_timeout:
                    # 转换到半开状态
                    await self._transition_to_state_async(CircuitState.HALF_OPEN)
                    allow_request = True
                    self._half_open_trial_count = 1
                    logger.info(f"熔断器[{self.name}]从OPEN转为HALF_OPEN状态，允许测试请求")
                else:
                    allow_request = False
                    time_left = int(self._last_state_change + self.reset_timeout - time.time())
                    logger.debug(f"熔断器[{self.name}]拒绝请求，熔断状态，还需等待 {time_left} 秒")
            elif self._state == CircuitState.HALF_OPEN:
                # 检查是否已达到最大测试次数
                if self._half_open_trial_count < self.half_open_max_trials:
                    allow_request = True
                    self._half_open_trial_count += 1
                    logger.debug(f"熔断器[{self.name}]处于HALF_OPEN状态，允许测试请求 ({self._half_open_trial_count}/{self.half_open_max_trials})")
                else:
                    allow_request = False
                    logger.debug(f"熔断器[{self.name}]拒绝额外的测试请求，已达到最大测试次数")
        
        if not allow_request:
            # 如果请求被拒绝且提供了回退函数，则执行回退函数
            if fallback:
                return await fallback()
            else:
                raise RuntimeError(f"熔断器[{self.name}]已打开，拒绝执行操作")
        
        # 执行受保护的操作
        try:
            result = await action()
            await self._on_success_async()
            if on_success:
                await on_success(result)
            return result
        except Exception as e:
            await self._on_failure_async(str(e))
            if on_failure:
                await on_failure(e)
            if fallback:
                return await fallback()
            raise
    
    def report_success(self) -> None:
        """手动报告操作成功"""
        self._on_success()
    
    def report_failure(self, reason: str = "未指定原因") -> None:
        """手动报告操作失败
        
        Args:
            reason: 失败原因
        """
        self._on_failure(reason)
    
    async def report_success_async(self) -> None:
        """手动报告操作成功（异步版本）"""
        await self._on_success_async()
    
    async def report_failure_async(self, reason: str = "未指定原因") -> None:
        """手动报告操作失败（异步版本）
        
        Args:
            reason: 失败原因
        """
        await self._on_failure_async(reason)
    
    def reset(self) -> None:
        """重置熔断器状态为关闭"""
        with self._lock:
            self._transition_to_state(CircuitState.CLOSED)
            self._consecutive_failures = 0
            self._results_window.clear()
            self._last_failure_reason = None
            self._half_open_trial_count = 0
            logger.info(f"熔断器[{self.name}]已手动重置为CLOSED状态")
    
    async def reset_async(self) -> None:
        """重置熔断器状态为关闭（异步版本）"""
        async with self._async_lock:
            await self._transition_to_state_async(CircuitState.CLOSED)
            self._consecutive_failures = 0
            self._results_window.clear()
            self._last_failure_reason = None
            self._half_open_trial_count = 0
            logger.info(f"熔断器[{self.name}]已手动重置为CLOSED状态")
    
    def _on_success(self) -> None:
        """处理操作成功"""
        with self._lock:
            # 更新状态
            self._consecutive_failures = 0
            
            # 更新窗口结果
            if self.failure_type in [FailureType.PERCENTAGE, FailureType.TOTAL]:
                self._results_window.append(True)
                if len(self._results_window) > self.window_size:
                    self._results_window.pop(0)
            
            # 如果当前是半开状态，则转换回关闭状态
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_state(CircuitState.CLOSED)
                logger.info(f"熔断器[{self.name}]从HALF_OPEN恢复到CLOSED状态")
    
    def _on_failure(self, reason: str) -> None:
        """处理操作失败
        
        Args:
            reason: 失败原因
        """
        with self._lock:
            # 更新失败原因
            self._last_failure_reason = reason
            
            # 更新窗口结果
            if self.failure_type in [FailureType.PERCENTAGE, FailureType.TOTAL]:
                self._results_window.append(False)
                if len(self._results_window) > self.window_size:
                    self._results_window.pop(0)
            
            # 对于连续失败模式，增加计数
            if self.failure_type == FailureType.CONSECUTIVE:
                self._consecutive_failures += 1
                
                # 检查是否达到熔断阈值
                if (self._state == CircuitState.CLOSED and 
                    self._consecutive_failures >= self.failure_threshold):
                    self._transition_to_state(CircuitState.OPEN)
                    logger.warning(f"熔断器[{self.name}]从CLOSED转为OPEN状态，连续失败{self._consecutive_failures}次，原因: {reason}")
            
            # 对于失败百分比模式
            elif self.failure_type == FailureType.PERCENTAGE and len(self._results_window) > 0:
                failure_count = self._results_window.count(False)
                failure_rate = failure_count / len(self._results_window)
                
                # 检查是否达到熔断阈值
                if (self._state == CircuitState.CLOSED and 
                    len(self._results_window) >= min(self.window_size, 3) and 
                    failure_rate >= self.failure_rate_threshold):
                    self._transition_to_state(CircuitState.OPEN)
                    logger.warning(
                        f"熔断器[{self.name}]从CLOSED转为OPEN状态，失败率{failure_rate:.1%}超过阈值{self.failure_rate_threshold:.1%}，"
                        f"窗口大小: {len(self._results_window)}，失败数: {failure_count}，原因: {reason}"
                    )
            
            # 对于总失败次数模式
            elif self.failure_type == FailureType.TOTAL:
                failure_count = self._results_window.count(False)
                
                # 检查是否达到熔断阈值
                if (self._state == CircuitState.CLOSED and 
                    failure_count >= self.failure_threshold):
                    self._transition_to_state(CircuitState.OPEN)
                    logger.warning(
                        f"熔断器[{self.name}]从CLOSED转为OPEN状态，失败数{failure_count}超过阈值{self.failure_threshold}，"
                        f"窗口大小: {len(self._results_window)}，原因: {reason}"
                    )
            
            # 如果当前是半开状态，任何失败都会导致重新打开
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_state(CircuitState.OPEN)
                logger.warning(f"熔断器[{self.name}]从HALF_OPEN转回OPEN状态，测试请求失败，原因: {reason}")
    
    async def _on_success_async(self) -> None:
        """处理操作成功（异步版本）"""
        async with self._async_lock:
            # 类似于同步版本，但可以发出异步事件
            self._consecutive_failures = 0
            
            if self.failure_type in [FailureType.PERCENTAGE, FailureType.TOTAL]:
                self._results_window.append(True)
                if len(self._results_window) > self.window_size:
                    self._results_window.pop(0)
            
            if self._state == CircuitState.HALF_OPEN:
                await self._transition_to_state_async(CircuitState.CLOSED)
                logger.info(f"熔断器[{self.name}]从HALF_OPEN恢复到CLOSED状态")
    
    async def _on_failure_async(self, reason: str) -> None:
        """处理操作失败（异步版本）
        
        Args:
            reason: 失败原因
        """
        async with self._async_lock:
            # 类似于同步版本，但可以发出异步事件
            self._last_failure_reason = reason
            
            if self.failure_type in [FailureType.PERCENTAGE, FailureType.TOTAL]:
                self._results_window.append(False)
                if len(self._results_window) > self.window_size:
                    self._results_window.pop(0)
            
            if self.failure_type == FailureType.CONSECUTIVE:
                self._consecutive_failures += 1
                
                if (self._state == CircuitState.CLOSED and 
                    self._consecutive_failures >= self.failure_threshold):
                    await self._transition_to_state_async(CircuitState.OPEN)
                    logger.warning(f"熔断器[{self.name}]从CLOSED转为OPEN状态，连续失败{self._consecutive_failures}次，原因: {reason}")
            
            elif self.failure_type == FailureType.PERCENTAGE and len(self._results_window) > 0:
                failure_count = self._results_window.count(False)
                failure_rate = failure_count / len(self._results_window)
                
                if (self._state == CircuitState.CLOSED and 
                    len(self._results_window) >= min(self.window_size, 3) and 
                    failure_rate >= self.failure_rate_threshold):
                    await self._transition_to_state_async(CircuitState.OPEN)
                    logger.warning(
                        f"熔断器[{self.name}]从CLOSED转为OPEN状态，失败率{failure_rate:.1%}超过阈值{self.failure_rate_threshold:.1%}，"
                        f"窗口大小: {len(self._results_window)}，失败数: {failure_count}，原因: {reason}"
                    )
            
            elif self.failure_type == FailureType.TOTAL:
                failure_count = self._results_window.count(False)
                
                if (self._state == CircuitState.CLOSED and 
                    failure_count >= self.failure_threshold):
                    await self._transition_to_state_async(CircuitState.OPEN)
                    logger.warning(
                        f"熔断器[{self.name}]从CLOSED转为OPEN状态，失败数{failure_count}超过阈值{self.failure_threshold}，"
                        f"窗口大小: {len(self._results_window)}，原因: {reason}"
                    )
            
            if self._state == CircuitState.HALF_OPEN:
                await self._transition_to_state_async(CircuitState.OPEN)
                logger.warning(f"熔断器[{self.name}]从HALF_OPEN转回OPEN状态，测试请求失败，原因: {reason}")
    
    def _transition_to_state(self, new_state: CircuitState) -> None:
        """转换熔断器状态并发出事件
        
        Args:
            new_state: 新状态
        """
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        
        # 创建事件对象
        failure_count = self._consecutive_failures
        failure_percentage = None
        
        if self.failure_type == FailureType.PERCENTAGE and self._results_window:
            failure_count = self._results_window.count(False)
            failure_percentage = failure_count / len(self._results_window)
        elif self.failure_type == FailureType.TOTAL and self._results_window:
            failure_count = self._results_window.count(False)
        
        event = CircuitBreakerEvent(
            state=new_state,
            failure_count=failure_count,
            reason=self._last_failure_reason,
            failure_percentage=failure_percentage
        )
        
        # 发送事件给所有监听器
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"熔断器事件监听器异常: {str(e)}")
    
    async def _transition_to_state_async(self, new_state: CircuitState) -> None:
        """转换熔断器状态并发出异步事件
        
        Args:
            new_state: 新状态
        """
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        
        # 创建事件对象
        failure_count = self._consecutive_failures
        failure_percentage = None
        
        if self.failure_type == FailureType.PERCENTAGE and self._results_window:
            failure_count = self._results_window.count(False)
            failure_percentage = failure_count / len(self._results_window)
        elif self.failure_type == FailureType.TOTAL and self._results_window:
            failure_count = self._results_window.count(False)
        
        event = CircuitBreakerEvent(
            state=new_state,
            failure_count=failure_count,
            reason=self._last_failure_reason,
            failure_percentage=failure_percentage
        )
        
        # 发送事件给所有同步监听器
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"熔断器事件监听器异常: {str(e)}")
        
        # 发送事件给所有异步监听器
        for listener in self._async_listeners:
            try:
                await listener(event)
            except Exception as e:
                logger.error(f"熔断器异步事件监听器异常: {str(e)}")
                
    def __str__(self) -> str:
        """返回熔断器的字符串表示"""
        return f"CircuitBreaker[{self.name}](state={self._state.name}, failures={self._consecutive_failures})"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取熔断器的统计信息
        
        Returns:
            Dict[str, Any]: 统计信息字典
        """
        with self._lock:
            stats = {
                "name": self.name,
                "state": self._state.name,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "failure_type": self.failure_type.name,
                "last_state_change": self._last_state_change,
                "time_in_current_state": int(time.time() - self._last_state_change)
            }
            
            if self._state == CircuitState.OPEN:
                stats["reset_timeout"] = self.reset_timeout
                stats["time_until_retry"] = max(0, int(self._last_state_change + self.reset_timeout - time.time()))
            
            if self.failure_type in [FailureType.PERCENTAGE, FailureType.TOTAL] and self._results_window:
                success_count = self._results_window.count(True)
                failure_count = self._results_window.count(False)
                stats["window_size"] = len(self._results_window)
                stats["success_count"] = success_count
                stats["failure_count"] = failure_count
                stats["failure_rate"] = failure_count / len(self._results_window)
            
            return stats


# 提供便捷的工厂函数来创建不同类型的熔断器
def create_consecutive_circuit_breaker(name: str, failure_threshold: int = 5, reset_timeout: int = 60) -> CircuitBreaker:
    """创建连续失败次数类型的熔断器
    
    Args:
        name: 熔断器名称
        failure_threshold: 连续失败阈值
        reset_timeout: 重置超时时间（秒）
        
    Returns:
        CircuitBreaker: 熔断器实例
    """
    return CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        reset_timeout=reset_timeout,
        failure_type=FailureType.CONSECUTIVE
    )

def create_percentage_circuit_breaker(name: str, window_size: int = 10,
                                     failure_rate_threshold: float = 0.5,
                                     reset_timeout: int = 60) -> CircuitBreaker:
    """创建失败百分比类型的熔断器
    
    Args:
        name: 熔断器名称
        window_size: 窗口大小
        failure_rate_threshold: 失败率阈值
        reset_timeout: 重置超时时间（秒）
        
    Returns:
        CircuitBreaker: 熔断器实例
    """
    return CircuitBreaker(
        name=name,
        window_size=window_size,
        failure_rate_threshold=failure_rate_threshold,
        reset_timeout=reset_timeout,
        failure_type=FailureType.PERCENTAGE
    )

def create_total_circuit_breaker(name: str, window_size: int = 10,
                                failure_threshold: int = 5,
                                reset_timeout: int = 60) -> CircuitBreaker:
    """创建总失败次数类型的熔断器
    
    Args:
        name: 熔断器名称
        window_size: 窗口大小
        failure_threshold: 失败次数阈值
        reset_timeout: 重置超时时间（秒）
        
    Returns:
        CircuitBreaker: 熔断器实例
    """
    return CircuitBreaker(
        name=name,
        window_size=window_size,
        failure_threshold=failure_threshold,
        reset_timeout=reset_timeout,
        failure_type=FailureType.TOTAL
    ) 