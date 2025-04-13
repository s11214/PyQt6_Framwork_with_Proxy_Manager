# 基础使用方法

## 应用目录获取方法

应用使用统一的目录结构来存储配置文件、日志和数据，确保在不同操作系统上的一致性。

### 获取应用目录路径

```python
# 导入路径管理模块
from src.utils.app_path import get_app_name, get_user_dir, get_app_dir
from src.utils.app_path import get_logs_dir, get_config_dir, get_db_dir, get_cache_dir

# 获取应用名称
app_name = get_app_name()

# 获取用户主目录
user_dir = get_user_dir()

# 获取应用数据主目录路径（如果不存在会自动创建）
app_dir_path = get_app_dir()

# 日志、配置、数据库、缓存目录也会自动创建
logs_dir = get_logs_dir()
config_dir = get_config_dir()
db_dir = get_db_dir()
cache_dir = get_cache_dir()

# 或者一次性初始化所有目录并获取路径信息
from src.utils.app_path import initialize_app_dirs
app_paths = initialize_app_dirs()
# app_paths 包含所有路径信息的字典
```

### 常见的子目录结构

应用目录下通常包含以下子目录：

```python
# 日志目录
logs_dir = os.path.join(app_dir_path, "logs")

# 配置文件目录
config_dir = os.path.join(app_dir_path, "config")

# 数据库目录
db_dir = os.path.join(app_dir_path, "db")

# 缓存目录
cache_dir = os.path.join(app_dir_path, "cache")

# 确保这些目录存在
for directory in [logs_dir, config_dir, db_dir, cache_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory)
```

### 文件路径生成

使用以下方式生成特定文件的完整路径：

```python
# 配置文件路径
config_file = os.path.join(config_dir, "settings.json")

# 数据库文件路径
db_file = os.path.join(db_dir, "proxies.db")

# 日志文件路径（通常由日志模块自动管理）
log_file = os.path.join(logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
```

### 最佳实践

- 所有文件操作应使用应用目录下的路径，避免使用相对路径或硬编码路径
- 使用专用函数获取路径，而不是在代码中重复路径构建逻辑
- 确保在使用前检查目录是否存在，并在必要时创建目录
- 对临时文件使用专用的缓存目录，并实现清理机制

## 日志模块使用方法

日志模块提供了统一的日志记录机制，支持不同级别的日志输出，并自动将日志显示在界面日志框中。

### 获取日志实例

```python
from src.utils.logger import get_logger

# 获取日志实例
logger = get_logger()
```

### 日志级别

日志模块支持以下几个级别，按严重程度递增：

```python
# 调试信息 - 仅在开发时使用
logger.debug("这是调试信息")

# 一般信息 - 记录正常操作
logger.info("操作成功完成")

# 警告信息 - 不影响主要功能但需要注意的问题
logger.warning("检测到潜在问题")

# 错误信息 - 功能出现错误
logger.error("操作失败")

# 严重错误 - 可能导致程序崩溃的错误
logger.critical("系统遇到严重错误")
```

### 日志存储和显示

- 所有日志会自动显示在应用程序右侧的日志面板中
- 日志文件保存在用户目录的 `[应用名]/logs` 文件夹下，按日期分文件存储
- INFO 及以上级别的日志会显示在界面上，所有级别的日志会保存到文件

### 最佳实践

- 在关键功能入口和出口处添加日志
- 异常捕获处理时记录错误日志
- 避免在循环中过度记录日志，可能影响性能
- 敏感信息（如密码）不要直接记录到日志中

## 进度条使用方法

进度条管理系统提供了在多线程环境下管理和显示任务进度的功能。

### 基本用法

进度条管理系统采用单例模式，通过函数接口操控：

```python
from src.utils.progress_manager import start_progress, increment_progress, complete_progress, reset_progress

# 开始一个包含100个任务项的任务
start_progress(100)

# 每完成一个任务项，增加进度
increment_progress()

# 任务全部完成
complete_progress()

# 任务中断或需要重置进度
reset_progress()
```

### 在多线程环境中使用

在多线程环境中使用进度条时，所有方法都是线程安全的：

```python
# 在主线程中启动进度跟踪
start_progress(total_tasks)

# 在工作线程中更新进度
def worker_task():
    # 执行任务...
    increment_progress()  # 安全地更新进度

# 在主线程中完成或重置进度
complete_progress()  # 或 reset_progress()
```

### 线程池管理示例

结合线程池使用进度条的完整示例：

```python
from src.utils.progress_manager import start_progress, increment_progress, complete_progress, reset_progress
from concurrent.futures import ThreadPoolExecutor
import threading

# 任务计数器，用于跟踪完成的任务数
completed_tasks = 0
task_lock = threading.Lock()

def process_item(item):
    # 处理单个任务
    # ...
    
    # 安全地更新进度
    global completed_tasks
    with task_lock:
        increment_progress()
        completed_tasks += 1
        
        # 检查是否所有任务都已完成
        if completed_tasks >= total_tasks:
            complete_progress()

# 使用线程池执行多个任务
def run_tasks(items):
    global completed_tasks
    completed_tasks = 0
    
    # 启动进度跟踪
    total_tasks = len(items)
    start_progress(total_tasks)
    
    # 创建线程池
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有任务
        futures = [executor.submit(process_item, item) for item in items]
        
        # 等待所有任务完成
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"任务执行出错: {str(e)}")
                
    # 确保进度条完成
    if completed_tasks < total_tasks:
        complete_progress()
```

### ThreadPoolManager 用法

项目中提供了 `ThreadPoolManager` 类来简化多线程任务管理，使用示例：

```python
from src.ui.tabs.detection_tab import ThreadPoolManager

# 创建线程池管理器
thread_manager = ThreadPoolManager(max_threads=10)

# 定义任务完成回调
def on_all_tasks_finished():
    print("所有任务已完成")

# 启动100个任务
thread_manager.start_tasks(100, on_all_tasks_finished)

# 可以随时停止所有任务
# thread_manager.stop_all_tasks()
```

### 注意事项

- 确保在任务开始前调用 `start_progress`
- 对于可能中断的任务，确保调用 `reset_progress` 重置进度条
- 在有大量任务的情况下，考虑批量更新进度而不是每个任务都更新
- 进度条管理器是线程安全的，可以在任何线程中调用相关方法

## 代理管理系统

代理管理系统提供了统一的接口来获取、验证和管理不同来源的代理，支持直连、固定代理、API代理和导入代理池等多种模式。

### 初始化代理管理器

代理管理器采用单例模式，可以通过以下方式获取实例：

```python
from src.core.proxy.proxy_manager import get_proxy_manager

# 获取代理管理器实例
proxy_manager = get_proxy_manager()
```

### 代理来源类型

系统支持以下几种代理来源类型：

1. **direct**: 直连模式，不使用代理
2. **fixed**: 固定代理，使用配置中指定的代理
3. **api**: API代理，从配置的API接口获取代理
4. **pool**: 导入代理池，从导入的代理列表中获取代理

### 获取单个代理

可以使用以下方法异步获取单个代理：

```python
# 获取单个代理（使用默认配置的代理来源）
proxy = await proxy_manager.get_proxy()

# 获取指定来源的代理
direct_proxy = await proxy_manager.get_proxy("direct")  # 直连模式
fixed_proxy = await proxy_manager.get_proxy("fixed")    # 固定代理模式

# 检查代理是否获取成功
if proxy:
    print(f"成功获取代理: {proxy.get('host')}:{proxy.get('port')}")
else:
    print("获取代理失败")
```

### 批量获取代理

对于API或导入代理池模式，可以批量获取代理：

```python
# 批量获取10个代理
proxies = await proxy_manager.get_proxies_batch(count=10, source_type="api")

# 批量获取并保存到任务代理池
proxies = await proxy_manager.get_proxies_batch(
    count=20, 
    source_type="pool",
    save_to_task_pool=True
)

print(f"成功获取 {len(proxies)} 个代理")
```

### 从任务代理池获取代理

任务代理池是为多任务场景设计的代理管理机制，可以防止代理重复使用：

```python
# 从任务代理池获取一个代理
task_proxy = await proxy_manager.get_proxy_from_task_pool()

# 使用代理执行任务...

# 标记代理为已使用
if task_proxy:
    await proxy_manager.mark_task_proxy_used(task_proxy['id'])
```

### 任务代理池监听和自动补充

任务代理池支持自动监听和动态补充功能，确保任务执行过程中始终有足够的可用代理：

```python
from src.core.proxy.task_proxy_pool import TaskProxyPool

# 获取任务代理池实例
task_pool = TaskProxyPool()

# 开始监听任务代理池，指定总任务数和代理来源
await task_pool.monitor_pool_for_tasks(
    total_tasks=100,     # 指定总任务数量
    proxy_source="api"   # 代理来源，可选值: "api"或"pool"
)

# 执行任务...

# 任务完成后停止监听
await task_pool.stop_monitoring()
```

#### 代理池监听原理

代理池监听会在后台异步运行，定期检查代理池状态并根据需要自动补充代理：

1. 系统维护一个安全系数(默认为1.2)，确保可用代理数量总是略多于实际需要
2. 如果可用代理数量低于阈值(总任务数 × 安全系数)，系统会自动获取新代理
3. 监听过程完全异步，不会阻塞主线程或任务执行

#### 获取代理池统计信息

可以随时获取代理池的统计信息：

```python
# 获取代理池统计信息
stats = task_pool.get_pool_stats()
print(f"代理池统计: 总数 {stats['total']}, "
      f"可用 {stats['available']}, "
      f"使用中 {stats['in_use']}, "
      f"已使用 {stats['used']}, "
      f"失败 {stats['failed']}")
```

#### 在实际任务中集成代理池监听

```python
async def run_batch_tasks():
    # 获取任务代理池和代理管理器
    task_pool = TaskProxyPool()
    proxy_manager = get_proxy_manager()
    
    # 设置任务数量和代理来源
    total_tasks = 100
    proxy_source = "api"
    
    # 清理旧数据
    task_pool.clear_task_proxy_pool_da()
    
    # 预填充初始代理(30%的任务数)
    initial_proxies = await proxy_manager.get_proxies_batch(
        count=max(5, int(total_tasks * 0.3)),
        source_type=proxy_source,
        save_to_task_pool=True
    )
    
    # 启动代理池监听
    await task_pool.monitor_pool_for_tasks(
        total_tasks=total_tasks,
        proxy_source=proxy_source
    )
    
    try:
        # 执行任务...
        for i in range(total_tasks):
            proxy = await proxy_manager.get_proxy_from_task_pool()
            if proxy:
                # 使用代理执行任务
                success = await perform_task(proxy)
                if success:
                    await proxy_manager.mark_task_proxy_used(proxy['id'])
    finally:
        # 确保停止监听
        await task_pool.stop_monitoring()
```

### 检查代理有效性

可以使用以下方法检查代理是否可用：

```python
# 检查单个代理
success, result = await proxy_manager.check_proxy(proxy)
if success:
    print(f"代理可用，IP: {result.get('ip')}")
else:
    print(f"代理不可用: {result.get('error')}")

# 检查直连
success, result = await proxy_manager.check_proxy(None)  # 传入None表示检查直连
```

### 批量检查代理

对于大量代理的场景，可以使用批量检查方法：

```python
# 定义回调函数处理检查结果
async def on_proxy_checked(proxy, success, result):
    if success:
        print(f"代理可用: {proxy['host']}:{proxy['port']}")
    else:
        print(f"代理不可用: {proxy['host']}:{proxy['port']}, 原因: {result.get('error')}")

# 批量检查代理
stats = await proxy_manager.check_proxies_batch(proxies, on_proxy_checked)
print(f"检查结果: 总共 {stats['total']}，可用 {stats['available']}，不可用 {stats['unavailable']}")
```

### 代理缓存机制

为了提高性能，系统对直连和固定代理模式提供了缓存机制：

```python
# 代理缓存在一定时间内有效，无需重复检查
proxy = await proxy_manager.get_proxy("fixed")  # 首次会检查并缓存结果

# 手动报告代理失败（应用层检测到代理实际使用出错时）
await proxy_manager.report_proxy_failure("fixed")

# 手动刷新代理缓存
success = await proxy_manager.refresh_proxy_cache("direct")
```

### 实际使用流程

在应用中通常遵循以下流程使用代理系统：

1. **直连/固定代理模式**:
   ```python
   proxy = await proxy_manager.get_proxy(source_type)
   if proxy:
       # 使用代理执行任务...
       if task_failed:
           await proxy_manager.report_proxy_failure(source_type)
   ```

2. **API/导入代理池模式（手动管理）**:
   ```python
   # 初始化时批量获取代理填充任务代理池
   await proxy_manager.get_proxies_batch(count=50, save_to_task_pool=True)
   
   # 每个任务获取一个未使用的代理
   proxy = await proxy_manager.get_proxy_from_task_pool()
   if proxy:
       # 使用代理执行任务...
       if task_success:
           await proxy_manager.mark_task_proxy_used(proxy['id'])
   ```

3. **API/导入代理池模式（自动监听）**:
   ```python
   # 获取任务代理池
   task_pool = TaskProxyPool()
   
   # 清理旧数据并预填充
   task_pool.clear_task_proxy_pool_da()
   await proxy_manager.get_proxies_batch(count=20, save_to_task_pool=True)
   
   # 启动监听
   await task_pool.monitor_pool_for_tasks(total_tasks=100, proxy_source="api")
   
   try:
       # 执行任务...
       for task in tasks:
           proxy = await proxy_manager.get_proxy_from_task_pool()
           # 使用代理...
   finally:
       # 停止监听
       await task_pool.stop_monitoring()
   ```

### 最佳实践

- 使用异步方法与代理管理器交互，避免阻塞主线程
- 为不同类型的任务使用不同的代理来源策略
- 合理设置代理检测超时和重试次数，避免因网络波动导致可用代理被误判
- 对于批量任务，先批量获取足够数量的代理，而不是每个任务单独获取
- 使用任务代理池管理模式避免代理重复使用导致IP被封
- 对于大规模任务，使用任务代理池监听功能自动管理代理数量
- 根据任务性质调整代理缓存时间，高频任务可适当延长缓存有效期
- 定期清理任务代理池中的无效代理，提高代理质量
- 在任务结束后务必调用`stop_monitoring()`停止代理池监听，避免资源泄漏

## 熔断机制

熔断机制是一种保护系统的模式，当检测到连续失败超过阈值时，自动"断开"操作，避免持续尝试可能已经失效的资源，系统提供了灵活且可扩展的熔断器实现。

### 熔断器概念

熔断器有三种状态：
- **关闭状态(CLOSED)**: 正常工作状态，允许操作执行
- **开启状态(OPEN)**: 熔断激活状态，拒绝所有操作
- **半开状态(HALF_OPEN)**: 恢复测试状态，允许有限操作来测试系统是否恢复

### 创建熔断器

系统提供了三种类型的熔断器工厂函数，可以根据不同场景选择：

```python
from src.utils.circuit_breaker import (
    create_consecutive_circuit_breaker,
    create_percentage_circuit_breaker,
    create_total_circuit_breaker
)

# 连续失败计数熔断器（当连续失败达到阈值时触发）
breaker = create_consecutive_circuit_breaker(
    name="proxy_test",             # 熔断器名称
    failure_threshold=5,           # 连续失败阈值
    reset_timeout=60               # 重置超时时间(秒)
)

# 失败百分比熔断器（当窗口期内失败率超过阈值时触发）
breaker = create_percentage_circuit_breaker(
    name="api_requests",
    window_size=10,                # 窗口大小
    failure_rate_threshold=0.5,    # 失败率阈值(50%)
    reset_timeout=120              # 重置超时时间(秒)
)

# 总失败次数熔断器（当窗口期内总失败次数达到阈值时触发）
breaker = create_total_circuit_breaker(
    name="database_conn",
    window_size=20,                # 窗口大小
    failure_threshold=8,           # 失败次数阈值
    reset_timeout=300              # 重置超时时间(秒)
)
```

### 使用熔断器保护操作

熔断器提供了同步和异步两种操作模式：

#### 同步操作保护

```python
from src.utils.circuit_breaker import create_consecutive_circuit_breaker

# 创建熔断器
breaker = create_consecutive_circuit_breaker("http_requests", 3)

# 定义要执行的操作
def make_request():
    # 执行可能失败的操作...
    response = requests.get("https://api.example.com/data")
    if response.status_code != 200:
        raise Exception(f"请求失败: {response.status_code}")
    return response.json()

# 定义备用操作（当熔断器打开或操作失败时执行）
def fallback_operation():
    return {"status": "error", "message": "使用缓存数据"}

# 使用熔断器保护操作
try:
    result = breaker.execute(
        action=make_request,                   # 主要操作
        fallback=fallback_operation,           # 备用操作
        on_success=lambda r: print("成功!"),   # 成功回调
        on_failure=lambda e: print(f"失败: {e}")  # 失败回调
    )
    print(result)
except Exception as e:
    print(f"操作失败且没有可用的回退: {str(e)}")
```

#### 异步操作保护

```python
import asyncio
from src.utils.circuit_breaker import create_consecutive_circuit_breaker

# 创建熔断器
breaker = create_consecutive_circuit_breaker("async_api", 3)

# 定义异步操作
async def async_request():
    # 模拟异步请求
    await asyncio.sleep(0.1)
    # 模拟失败
    if random.random() < 0.3:
        raise Exception("请求超时")
    return {"data": "success"}

# 定义异步备用操作
async def async_fallback():
    return {"data": "fallback"}

# 异步回调函数
async def on_success(result):
    print(f"请求成功: {result}")

async def on_failure(exception):
    print(f"请求失败: {exception}")

# 使用熔断器保护异步操作
async def protected_operation():
    try:
        result = await breaker.execute_async(
            action=async_request,
            fallback=async_fallback,
            on_success=on_success,
            on_failure=on_failure
        )
        return result
    except Exception as e:
        print(f"保护操作失败: {str(e)}")
        return None

# 执行异步操作
asyncio.run(protected_operation())
```

### 手动报告成功/失败

对于不便于使用execute方法包装的场景，可以手动报告操作结果：

```python
# 同步报告
def custom_operation():
    try:
        # 执行操作...
        result = perform_action()
        breaker.report_success()
        return result
    except Exception as e:
        breaker.report_failure(str(e))
        raise

# 异步报告
async def async_custom_operation():
    try:
        # 执行异步操作...
        result = await perform_async_action()
        await breaker.report_success_async()
        return result
    except Exception as e:
        await breaker.report_failure_async(str(e))
        raise
```

### 事件监听

熔断器提供了事件监听机制，可以在状态变化时执行回调：

```python
# 添加同步事件监听器
def on_circuit_state_change(event):
    print(f"熔断器状态变化: {event.state.name}, 失败次数: {event.failure_count}")
    if event.state.name == "OPEN":
        # 通知管理员或记录严重问题
        send_alert(f"服务熔断! 原因: {event.reason}")

breaker.add_listener(on_circuit_state_change)

# 添加异步事件监听器
async def async_circuit_listener(event):
    if event.state.name == "OPEN":
        await async_log_service.log(f"熔断器[{event.name}]已激活，原因: {event.reason}")

breaker.add_async_listener(async_circuit_listener)

# 移除监听器
breaker.remove_listener(on_circuit_state_change)
```

### 手动重置和状态查询

```python
# 查询熔断器当前状态
if breaker.is_open:
    print("熔断器当前处于熔断状态")
elif breaker.is_half_open:
    print("熔断器当前处于半开状态")
else:
    print("熔断器当前处于正常状态")

# 获取详细统计信息
stats = breaker.get_stats()
print(f"熔断器[{stats['name']}] 状态: {stats['state']}")
print(f"失败次数: {stats['consecutive_failures']}/{stats['failure_threshold']}")

# 手动重置熔断器
breaker.reset()  # 同步版本
await breaker.reset_async()  # 异步版本
```

### 在UI组件中使用熔断器

结合事件系统，可以在UI组件中优雅地使用熔断器：

```python
from PyQt6.QtCore import QThread, pyqtSignal
from src.utils.circuit_breaker import create_consecutive_circuit_breaker, CircuitBreakerEvent, CircuitState

class WorkerThread(QThread):
    circuit_broken = pyqtSignal(int, str)  # 熔断信号(失败次数, 原因)
    
    def __init__(self):
        super().__init__()
        self.circuit_breaker = create_consecutive_circuit_breaker(
            name="ui_worker", 
            failure_threshold=5
        )
        self.circuit_breaker.add_listener(self._on_circuit_breaker_event)
    
    def _on_circuit_breaker_event(self, event: CircuitBreakerEvent):
        # 当熔断器状态变为OPEN时触发UI信号
        if event.state == CircuitState.OPEN:
            self.circuit_broken.emit(event.failure_count, event.reason or "未知原因")
    
    def run(self):
        # 线程执行逻辑...
        pass
```

### 熔断器配置注意事项

- **失败阈值(failure_threshold)**: 设置太低会导致系统过于敏感，设置太高则保护不足
- **重置超时(reset_timeout)**: 设置合理的恢复时间，避免系统长时间不可用
- **窗口大小(window_size)**: 对于百分比和总失败次数模式，窗口大小决定了系统"记忆"的时间跨度
- **半开状态最大尝试次数(half_open_max_trials)**: 控制系统恢复测试的谨慎程度

### 最佳实践

- 根据不同类型的操作选择合适的熔断器类型
- 对于网络请求，使用连续失败模式更为合适
- 对于数据库操作，百分比模式可以更好地处理间歇性故障
- 在分布式系统中，考虑在重要接口处添加熔断保护
- 设置合理的日志记录，便于问题排查
- 结合缓存机制，为熔断期间提供降级服务
- 定期检查和调整熔断器参数以适应业务变化
