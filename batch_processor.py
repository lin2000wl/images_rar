#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量图片处理队列系统
实现多线程并发图片压缩功能
"""

import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

from image_compressor import ImageCompressor


class ProcessingLogger:
    """批量处理专用日志记录器"""
    
    def __init__(self, log_file: Optional[str] = None, log_level: int = logging.INFO):
        """
        初始化日志记录器
        
        Args:
            log_file: 日志文件路径，None则只输出到控制台
            log_level: 日志级别
        """
        self.logger = logging.getLogger("BatchProcessor")
        self.logger.setLevel(log_level)
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器（如果指定了文件）
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        self.logger.propagate = False
    
    def info(self, message: str, **kwargs):
        """记录信息日志"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """记录警告日志"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """记录错误日志"""
        self.logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """记录调试日志"""
        self.logger.debug(message, **kwargs)


class ProcessingMonitor:
    """批量处理监控器"""
    
    def __init__(self, save_to_file: bool = True, report_interval: float = 5.0):
        """
        初始化监控器
        
        Args:
            save_to_file: 是否保存监控数据到文件
            report_interval: 报告间隔（秒）
        """
        self.save_to_file = save_to_file
        self.report_interval = report_interval
        
        # 监控数据
        self.start_time = None
        self.end_time = None
        self.session_id = str(uuid.uuid4())
        
        # 任务统计
        self.task_history = []
        self.performance_samples = []
        
        # 实时统计
        self.current_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'processing_rate': 0.0,
            'average_compression_ratio': 0.0,
            'total_size_saved': 0,
            'active_workers': 0
        }
        
        self.logger = ProcessingLogger()
    
    def start_monitoring(self):
        """开始监控"""
        self.start_time = datetime.now()
        self.logger.info(f"开始监控批量处理会话: {self.session_id}")
    
    def stop_monitoring(self):
        """停止监控"""
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        self.logger.info(f"批量处理会话结束: {self.session_id}")
        self.logger.info(f"总处理时间: {duration:.2f}秒")
        
        if self.save_to_file:
            self._save_session_report()
    
    def record_task_start(self, task: CompressionTask):
        """记录任务开始"""
        self.logger.debug(f"任务开始: {task.task_id} - {task.input_path}")
        
        task_record = {
            'task_id': task.task_id,
            'input_path': task.input_path,
            'output_path': task.output_path,
            'compression_method': task.compression_method,
            'target_size_kb': task.target_size_kb,
            'start_time': datetime.now().isoformat(),
            'status': 'started'
        }
        
        self.task_history.append(task_record)
    
    def record_task_complete(self, task: CompressionTask):
        """记录任务完成"""
        # 查找对应的任务记录
        task_record = None
        for record in reversed(self.task_history):
            if record['task_id'] == task.task_id:
                task_record = record
                break
        
        if task_record:
            # 更新任务记录
            task_record.update({
                'end_time': datetime.now().isoformat(),
                'status': 'completed' if task.is_successful else 'failed',
                'original_size_bytes': task.original_size_bytes,
                'final_size_bytes': task.final_size_bytes,
                'compression_ratio': task.compression_ratio,
                'processing_time_seconds': task.processing_time_seconds,
                'error_message': task.error_message
            })
            
            # 更新统计
            self._update_statistics(task)
            
            if task.is_successful:
                self.logger.info(
                    f"任务完成: {Path(task.input_path).name} - "
                    f"压缩比: {task.compression_ratio:.2f}x, "
                    f"耗时: {task.processing_time_seconds:.2f}s"
                )
            else:
                self.logger.error(f"任务失败: {task.input_path} - {task.error_message}")
    
    def record_performance_sample(self, stats: Dict[str, Any]):
        """记录性能采样"""
        sample = {
            'timestamp': datetime.now().isoformat(),
            'stats': stats.copy()
        }
        self.performance_samples.append(sample)
        
        # 限制样本数量
        if len(self.performance_samples) > 1000:
            self.performance_samples = self.performance_samples[-500:]
    
    def _update_statistics(self, task: CompressionTask):
        """更新统计信息"""
        if task.is_successful:
            self.current_stats['completed_tasks'] += 1
            
            # 更新压缩比统计
            if task.compression_ratio:
                total_ratio = (self.current_stats['average_compression_ratio'] * 
                              (self.current_stats['completed_tasks'] - 1) + 
                              task.compression_ratio)
                self.current_stats['average_compression_ratio'] = total_ratio / self.current_stats['completed_tasks']
            
            # 更新节省的空间
            if task.original_size_bytes and task.final_size_bytes:
                saved_bytes = task.original_size_bytes - task.final_size_bytes
                self.current_stats['total_size_saved'] += saved_bytes
        else:
            self.current_stats['failed_tasks'] += 1
    
    def _save_session_report(self):
        """保存会话报告"""
        try:
            report_dir = Path("batch_processing_reports")
            report_dir.mkdir(exist_ok=True)
            
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            report_file = report_dir / f"session_{timestamp}_{self.session_id[:8]}.json"
            
            report_data = {
                'session_id': self.session_id,
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat(),
                'duration_seconds': (self.end_time - self.start_time).total_seconds(),
                'final_stats': self.current_stats.copy(),
                'task_history': self.task_history,
                'performance_samples': self.performance_samples
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"会话报告已保存: {report_file}")
            
        except Exception as e:
            self.logger.error(f"保存会话报告失败: {e}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        stats = self.current_stats.copy()
        
        if self.start_time:
            elapsed_time = (datetime.now() - self.start_time).total_seconds()
            stats['elapsed_time_seconds'] = elapsed_time
            
            # 计算处理速度
            if elapsed_time > 0:
                stats['processing_rate'] = self.current_stats['completed_tasks'] / elapsed_time * 60
        
        return stats
    
    def print_summary(self):
        """打印处理摘要"""
        if not self.start_time:
            return
        
        stats = self.get_current_stats()
        
        print("\n" + "=" * 50)
        print("批量处理摘要")
        print("=" * 50)
        print(f"会话ID: {self.session_id[:8]}...")
        print(f"处理时间: {stats.get('elapsed_time_seconds', 0):.2f}秒")
        print(f"总任务数: {stats['total_tasks']}")
        print(f"成功完成: {stats['completed_tasks']}")
        print(f"处理失败: {stats['failed_tasks']}")
        print(f"成功率: {stats['completed_tasks']/max(1, stats['total_tasks'])*100:.1f}%")
        print(f"平均压缩比: {stats['average_compression_ratio']:.2f}x")
        print(f"总节省空间: {stats['total_size_saved']/1024/1024:.2f}MB")
        print(f"处理速度: {stats['processing_rate']:.1f}个/分钟")
        print("=" * 50)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待处理
    RUNNING = "running"      # 正在处理
    COMPLETED = "completed"  # 完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class CompressionTask:
    """图片压缩任务类"""
    
    # 必需参数
    input_path: str
    output_path: str
    
    # 可选参数
    target_size_kb: int = 100
    replace_original: bool = False
    compression_method: str = "standard"  # standard, advanced_jpeg, webp, best
    
    # 任务元数据
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 处理结果
    original_size_bytes: Optional[int] = None
    final_size_bytes: Optional[int] = None
    compression_ratio: Optional[float] = None
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    
    # 进度信息
    progress_percentage: float = 0.0
    current_step: str = "等待开始"
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保路径是Path对象
        self.input_path = str(Path(self.input_path))
        self.output_path = str(Path(self.output_path))
        
        # 如果是替换原图，输出路径应该是输入路径
        if self.replace_original:
            self.output_path = self.input_path
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """获取任务执行时长（秒）"""
        if self.started_at is None:
            return None
        
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def is_finished(self) -> bool:
        """检查任务是否已完成（无论成功或失败）"""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
    
    @property
    def is_successful(self) -> bool:
        """检查任务是否成功完成"""
        return self.status == TaskStatus.COMPLETED
    
    def start(self):
        """标记任务开始"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        self.progress_percentage = 0.0
        self.current_step = "正在处理"
    
    def complete(self, result: Dict[str, Any]):
        """标记任务完成并保存结果"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.progress_percentage = 100.0
        self.current_step = "处理完成"
        
        # 保存处理结果
        self.original_size_bytes = result.get('original_size_bytes')
        self.final_size_bytes = result.get('final_size_bytes')
        self.compression_ratio = result.get('compression_ratio')
        self.processing_time_seconds = result.get('processing_time_seconds')
    
    def fail(self, error_message: str):
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.progress_percentage = 0.0
        self.current_step = "处理失败"
        self.error_message = error_message
    
    def cancel(self):
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        self.progress_percentage = 0.0
        self.current_step = "已取消"
    
    def update_progress(self, percentage: float, step: str):
        """更新任务进度"""
        self.progress_percentage = max(0.0, min(100.0, percentage))
        self.current_step = step
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'task_id': self.task_id,
            'input_path': self.input_path,
            'output_path': self.output_path,
            'target_size_kb': self.target_size_kb,
            'replace_original': self.replace_original,
            'compression_method': self.compression_method,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'original_size_bytes': self.original_size_bytes,
            'final_size_bytes': self.final_size_bytes,
            'compression_ratio': self.compression_ratio,
            'processing_time_seconds': self.processing_time_seconds,
            'error_message': self.error_message,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'duration_seconds': self.duration_seconds
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        input_name = Path(self.input_path).name
        status_text = self.status.value
        progress_text = f"{self.progress_percentage:.1f}%" if self.progress_percentage > 0 else ""
        
        if self.is_successful and self.compression_ratio:
            size_text = f"压缩比 {self.compression_ratio:.2f}x"
        elif self.error_message:
            size_text = f"错误: {self.error_message[:30]}..."
        else:
            size_text = self.current_step
        
        return f"Task({input_name}, {status_text}, {progress_text}, {size_text})"


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class PriorityTask:
    """带优先级的任务包装器"""
    task: CompressionTask
    priority: TaskPriority = TaskPriority.NORMAL
    
    def __lt__(self, other):
        """优先级比较（数值越大优先级越高）"""
        return self.priority.value > other.priority.value


def create_compression_tasks(image_files: List[str], output_dir: str, 
                           target_size_kb: int = 100, replace_original: bool = False,
                           compression_method: str = "standard") -> List[CompressionTask]:
    """
    批量创建压缩任务
    
    Args:
        image_files: 输入图片文件路径列表
        output_dir: 输出目录
        target_size_kb: 目标文件大小（KB）
        replace_original: 是否替换原图
        compression_method: 压缩方法
        
    Returns:
        List[CompressionTask]: 任务列表
    """
    tasks = []
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for input_file in image_files:
        input_path = Path(input_file)
        
        if replace_original:
            # 替换原图
            output_file = str(input_path)
        else:
            # 生成新文件
            stem = input_path.stem
            suffix = input_path.suffix.lower()
            
            # 根据压缩方法确定输出格式
            if compression_method == "webp":
                output_suffix = ".webp"
            else:
                output_suffix = ".jpg" if suffix in ['.jpeg', '.jpg'] else ".jpg"
            
            output_file = str(output_path / f"{stem}_compressed{output_suffix}")
        
        # 创建任务
        task = CompressionTask(
            input_path=str(input_path),
            output_path=output_file,
            target_size_kb=target_size_kb,
            replace_original=replace_original,
            compression_method=compression_method
        )
        
        tasks.append(task)
    
    return tasks


class TaskQueue:
    """线程安全的任务队列管理器"""
    
    def __init__(self, max_size: int = 0, use_priority: bool = False):
        """
        初始化队列管理器
        
        Args:
            max_size: 队列最大大小，0表示无限制
            use_priority: 是否使用优先级队列
        """
        self.max_size = max_size
        self.use_priority = use_priority
        
        # 选择队列类型
        if use_priority:
            self.queue = queue.PriorityQueue(maxsize=max_size)
        else:
            self.queue = queue.Queue(maxsize=max_size)
        
        # 统计信息
        self._total_added = 0
        self._total_completed = 0
        self._lock = threading.Lock()
        
        # 任务状态跟踪
        self._tasks = {}  # task_id -> CompressionTask
        self._active_tasks = set()  # 正在处理的任务ID
        
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(f"TaskQueue_{id(self)}")
        logger.handlers.clear()  # 清除现有处理器
        logger.setLevel(logging.INFO)
        logger.propagate = False  # 防止重复输出
        return logger
    
    def add_task(self, task: CompressionTask, priority: TaskPriority = TaskPriority.NORMAL) -> bool:
        """
        添加任务到队列
        
        Args:
            task: 压缩任务对象
            priority: 任务优先级（仅在使用优先级队列时有效）
            
        Returns:
            bool: 是否成功添加
        """
        try:
            with self._lock:
                # 检查任务是否已存在
                if task.task_id in self._tasks:
                    # self.logger.warning(f"任务已存在: {task.task_id}")  # 暂时禁用日志
                    return False
                
                # 添加到队列
                if self.use_priority:
                    priority_task = PriorityTask(task, priority)
                    self.queue.put(priority_task, timeout=1.0)
                else:
                    self.queue.put(task, timeout=1.0)
                
                # 更新统计和跟踪
                self._tasks[task.task_id] = task
                self._total_added += 1
                
                # self.logger.info(f"任务已添加到队列: {task.task_id} ({task.input_path})")  # 暂时禁用日志
                return True
                
        except queue.Full:
            # self.logger.error(f"队列已满，无法添加任务: {task.task_id}")  # 暂时禁用日志
            return False
        except Exception as e:
            # self.logger.error(f"添加任务时发生错误: {e}")  # 暂时禁用日志
            return False
    
    def add_tasks(self, tasks: List[CompressionTask], 
                  priority: TaskPriority = TaskPriority.NORMAL) -> int:
        """
        批量添加任务
        
        Args:
            tasks: 任务列表
            priority: 任务优先级
            
        Returns:
            int: 成功添加的任务数量
        """
        success_count = 0
        for task in tasks:
            if self.add_task(task, priority):
                success_count += 1
        
        self.logger.info(f"批量添加任务完成: {success_count}/{len(tasks)} 成功")
        return success_count
    
    def get_task(self, timeout: Optional[float] = None) -> Optional[CompressionTask]:
        """
        从队列获取任务
        
        Args:
            timeout: 超时时间（秒），None表示阻塞等待
            
        Returns:
            Optional[CompressionTask]: 任务对象，队列为空时返回None
        """
        try:
            if self.use_priority:
                priority_task = self.queue.get(timeout=timeout)
                task = priority_task.task
            else:
                task = self.queue.get(timeout=timeout)
            
            with self._lock:
                self._active_tasks.add(task.task_id)
            
            self.logger.debug(f"任务已出队: {task.task_id}")
            return task
            
        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"获取任务时发生错误: {e}")
            return None
    
    def task_done(self, task: CompressionTask):
        """
        标记任务完成
        
        Args:
            task: 已完成的任务
        """
        try:
            self.queue.task_done()
            
            with self._lock:
                self._active_tasks.discard(task.task_id)
                self._total_completed += 1
            
            self.logger.info(f"任务已完成: {task.task_id} ({task.status.value})")
            
        except Exception as e:
            self.logger.error(f"标记任务完成时发生错误: {e}")
    
    def get_task_by_id(self, task_id: str) -> Optional[CompressionTask]:
        """
        根据ID获取任务对象
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[CompressionTask]: 任务对象
        """
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[CompressionTask]:
        """
        获取所有任务
        
        Returns:
            List[CompressionTask]: 任务列表
        """
        with self._lock:
            return list(self._tasks.values())
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[CompressionTask]:
        """
        根据状态获取任务
        
        Args:
            status: 任务状态
            
        Returns:
            List[CompressionTask]: 匹配状态的任务列表
        """
        with self._lock:
            return [task for task in self._tasks.values() if task.status == status]
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.cancel()
                self.logger.info(f"任务已取消: {task_id}")
                return True
            return False
    
    def cancel_all_pending(self) -> int:
        """
        取消所有等待中的任务
        
        Returns:
            int: 取消的任务数量
        """
        cancelled_count = 0
        with self._lock:
            for task in self._tasks.values():
                if task.status == TaskStatus.PENDING:
                    task.cancel()
                    cancelled_count += 1
        
        self.logger.info(f"已取消 {cancelled_count} 个等待中的任务")
        return cancelled_count
    
    def clear(self):
        """清空队列"""
        with self._lock:
            # 清空队列
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except queue.Empty:
                    break
            
            # 取消所有任务
            for task in self._tasks.values():
                if not task.is_finished:
                    task.cancel()
            
            # 重置统计
            self._active_tasks.clear()
            self.logger.info("队列已清空")
    
    @property
    def size(self) -> int:
        """获取队列当前大小"""
        return self.queue.qsize()
    
    @property
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return self.queue.empty()
    
    @property
    def is_full(self) -> bool:
        """检查队列是否已满"""
        return self.queue.full()
    
    @property
    def total_tasks(self) -> int:
        """获取总任务数"""
        with self._lock:
            return len(self._tasks)
    
    @property
    def active_tasks_count(self) -> int:
        """获取活动任务数"""
        with self._lock:
            return len(self._active_tasks)
    
    @property
    def completed_tasks_count(self) -> int:
        """获取已完成任务数"""
        return self._total_completed
    
    @property
    def pending_tasks_count(self) -> int:
        """获取等待中任务数"""
        return len(self.get_tasks_by_status(TaskStatus.PENDING))
    
    @property
    def failed_tasks_count(self) -> int:
        """获取失败任务数"""
        return len(self.get_tasks_by_status(TaskStatus.FAILED))
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取队列统计信息
        
        Returns:
            Dict[str, Any]: 统计信息字典
        """
        with self._lock:
            return {
                'queue_size': self.size,
                'total_tasks': self.total_tasks,
                'active_tasks': self.active_tasks_count,
                'completed_tasks': self.completed_tasks_count,
                'pending_tasks': self.pending_tasks_count,
                'failed_tasks': self.failed_tasks_count,
                'total_added': self._total_added,
                'use_priority': self.use_priority,
                'max_size': self.max_size
            }
    
    def wait_completion(self, timeout: Optional[float] = None):
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间（秒）
        """
        try:
            if timeout:
                self.queue.join()  # 这里可能需要手动实现超时
            else:
                self.queue.join()
        except Exception as e:
            self.logger.error(f"等待任务完成时发生错误: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        stats = self.get_statistics()
        return (f"TaskQueue(size={stats['queue_size']}, "
                f"total={stats['total_tasks']}, "
                f"active={stats['active_tasks']}, "
                f"completed={stats['completed_tasks']})")


class CompressionWorker:
    """图片压缩工作器"""
    
    def __init__(self, worker_id: str, task_queue: TaskQueue):
        """
        初始化压缩工作器
        
        Args:
            worker_id: 工作器ID
            task_queue: 任务队列
        """
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.compressor = None
        self.is_running = False
        self.thread = None
        
        # 统计信息
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        
    def start(self):
        """启动工作器线程"""
        if self.is_running:
            return False
        
        self.is_running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """停止工作器"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
    
    def _worker_loop(self):
        """工作器主循环"""
        while self.is_running:
            try:
                # 获取任务（超时1秒）
                task = self.task_queue.get_task(timeout=1.0)
                if task is None:
                    continue
                
                # 处理任务
                self._process_task(task)
                
                # 标记任务完成
                self.task_queue.task_done(task)
                
            except Exception as e:
                # 记录错误但继续运行
                print(f"Worker {self.worker_id} 处理错误: {e}")
                continue
    
    def _process_task(self, task: CompressionTask):
        """
        处理单个压缩任务
        
        Args:
            task: 压缩任务
        """
        try:
            self.processed_count += 1
            
            # 标记任务开始
            task.start()
            task.update_progress(10.0, "准备压缩")
            
            # 延迟导入ImageCompressor以避免循环导入
            from image_compressor import ImageCompressor
            
            # 创建压缩器（如果还没有）
            if self.compressor is None:
                self.compressor = ImageCompressor(target_size_kb=task.target_size_kb)
            else:
                self.compressor.target_size_kb = task.target_size_kb
            
            # 更新进度
            task.update_progress(20.0, "开始压缩")
            
            # 执行压缩
            start_time = time.time()
            
            # 根据压缩方法选择处理方式
            if task.compression_method == "webp":
                result = self.compressor.compress_with_webp(
                    task.input_path, 
                    task.output_path
                )
            elif task.compression_method == "advanced_jpeg":
                result = self.compressor.compress_with_advanced_jpeg(
                    task.input_path, 
                    task.output_path
                )
            elif task.compression_method == "best":
                result = self.compressor.compress_with_best_method(
                    task.input_path, 
                    task.output_path
                )
            else:  # standard
                result = self.compressor.compress_single_image(
                    task.input_path, 
                    task.output_path
                )
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 更新进度
            task.update_progress(90.0, "压缩完成，保存结果")
            
            # 检查压缩结果
            if result and result.get('success', False):
                # 准备结果数据
                final_result = {
                    'original_size_bytes': result.get('original_size_bytes', 0),
                    'final_size_bytes': result.get('final_size_bytes', 0),
                    'compression_ratio': result.get('compression_ratio', 1.0),
                    'processing_time_seconds': processing_time
                }
                
                # 标记任务完成
                task.complete(final_result)
                self.success_count += 1
                
                print(f"Worker {self.worker_id}: 成功处理 {task.input_path} "
                      f"(压缩比: {final_result['compression_ratio']:.2f}x)")
                
            else:
                # 压缩失败
                error_msg = result.get('error', '压缩失败') if result else '未知错误'
                task.fail(error_msg)
                self.error_count += 1
                
                print(f"Worker {self.worker_id}: 处理失败 {task.input_path} - {error_msg}")
            
        except Exception as e:
            # 处理异常
            task.fail(str(e))
            self.error_count += 1
            print(f"Worker {self.worker_id}: 异常错误 {task.input_path} - {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取工作器统计信息"""
        return {
            'worker_id': self.worker_id,
            'is_running': self.is_running,
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': self.success_count / max(1, self.processed_count)
        }


def process_single_task_sync(task: CompressionTask) -> bool:
    """
    同步处理单个任务（用于测试或单任务处理）
    
    Args:
        task: 压缩任务
        
    Returns:
        bool: 是否处理成功
    """
    try:
        # 创建临时工作器
        temp_worker = CompressionWorker("temp", None)
        temp_worker._process_task(task)
        
        return task.is_successful
        
    except Exception as e:
        task.fail(str(e))
        return False


class BatchProcessor:
    """批量图片处理调度器"""
    
    def __init__(self, max_workers: int = 2, max_queue_size: int = 100, 
                 use_priority: bool = False):
        """
        初始化批量处理器
        
        Args:
            max_workers: 最大工作器数量
            max_queue_size: 队列最大大小
            use_priority: 是否使用优先级队列
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.use_priority = use_priority
        
        # 创建任务队列
        self.task_queue = TaskQueue(
            max_size=max_queue_size,
            use_priority=use_priority
        )
        
        # 工作器管理
        self.workers = []
        self.is_running = False
        
        # 处理统计
        self.start_time = None
        self.total_processed = 0
        self.total_success = 0
        self.total_errors = 0
        
        # 回调函数
        self.on_task_complete = None
        self.on_task_error = None
        self.on_progress_update = None
        
        # 监控和日志
        self.monitor = ProcessingMonitor(save_to_file=True)
        self.logger = ProcessingLogger()
    
    def add_tasks(self, image_files: List[str], output_dir: str,
                  target_size_kb: int = 100, replace_original: bool = False,
                  compression_method: str = "standard",
                  priority: TaskPriority = TaskPriority.NORMAL) -> int:
        """
        添加批量处理任务
        
        Args:
            image_files: 图片文件路径列表
            output_dir: 输出目录
            target_size_kb: 目标文件大小
            replace_original: 是否替换原图
            compression_method: 压缩方法
            priority: 任务优先级
            
        Returns:
            int: 成功添加的任务数量
        """
        # 创建任务列表
        tasks = create_compression_tasks(
            image_files=image_files,
            output_dir=output_dir,
            target_size_kb=target_size_kb,
            replace_original=replace_original,
            compression_method=compression_method
        )
        
        # 添加到队列
        return self.task_queue.add_tasks(tasks, priority)
    
    def start_processing(self) -> bool:
        """
        开始处理任务
        
        Returns:
            bool: 是否成功启动
        """
        if self.is_running:
            return False
        
        self.is_running = True
        self.start_time = time.time()
        
        # 开始监控
        self.monitor.start_monitoring()
        self.monitor.current_stats['total_tasks'] = self.task_queue.total_tasks
        
        self.logger.info(f"开始批量处理，队列中有 {self.task_queue.total_tasks} 个任务")
        
        # 创建并启动工作器
        for i in range(self.max_workers):
            worker = CompressionWorker(f"worker-{i+1}", self.task_queue)
            
            # 设置回调（如果需要）
            if hasattr(worker, 'set_callbacks'):
                worker.set_callbacks(
                    on_complete=self._on_worker_task_complete,
                    on_error=self._on_worker_task_error,
                    on_progress=self._on_worker_progress_update
                )
            
            if worker.start():
                self.workers.append(worker)
            else:
                self.logger.warning(f"工作器 {worker.worker_id} 启动失败")
        
        self.monitor.current_stats['active_workers'] = len(self.workers)
        self.logger.info(f"批量处理器已启动，{len(self.workers)} 个工作器运行中")
        return len(self.workers) > 0
    
    def stop_processing(self, timeout: float = 10.0):
        """
        停止处理任务
        
        Args:
            timeout: 等待超时时间
        """
        if not self.is_running:
            return
        
        self.logger.info("正在停止批量处理器...")
        self.is_running = False
        
        # 停止所有工作器
        for worker in self.workers:
            worker.stop()
        
        # 等待工作器完成
        for worker in self.workers:
            if worker.thread and worker.thread.is_alive():
                worker.thread.join(timeout=timeout/len(self.workers))
        
        self.workers.clear()
        
        # 停止监控
        self.monitor.stop_monitoring()
        self.monitor.print_summary()
        self.logger.info("批量处理器已停止")
    
    def wait_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否在超时前完成
        """
        if not self.is_running:
            return True
        
        try:
            # 等待队列中的所有任务完成
            if timeout:
                start_wait = time.time()
                while not self.task_queue.is_empty and (time.time() - start_wait) < timeout:
                    time.sleep(0.1)
                    if self.on_progress_update:
                        self._report_progress()
                return self.task_queue.is_empty
            else:
                # 无超时等待
                while not self.task_queue.is_empty:
                    time.sleep(0.1)
                    if self.on_progress_update:
                        self._report_progress()
                return True
                
        except KeyboardInterrupt:
            self.logger.info("用户中断处理")
            self.stop_processing()
            return False
    
    def cancel_all_pending(self) -> int:
        """
        取消所有等待中的任务
        
        Returns:
            int: 取消的任务数量
        """
        return self.task_queue.cancel_all_pending()
    
    def get_progress_info(self) -> Dict[str, Any]:
        """
        获取处理进度信息
        
        Returns:
            Dict[str, Any]: 进度信息
        """
        queue_stats = self.task_queue.get_statistics()
        worker_stats = [worker.get_statistics() for worker in self.workers]
        
        # 计算总体统计
        total_processed = sum(w['processed_count'] for w in worker_stats)
        total_success = sum(w['success_count'] for w in worker_stats)
        total_errors = sum(w['error_count'] for w in worker_stats)
        
        # 计算处理速度
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        processing_rate = total_processed / max(1, elapsed_time) * 60  # 每分钟处理数
        
        return {
            'is_running': self.is_running,
            'elapsed_time_seconds': elapsed_time,
            'queue_stats': queue_stats,
            'worker_count': len(self.workers),
            'worker_stats': worker_stats,
            'total_processed': total_processed,
            'total_success': total_success,
            'total_errors': total_errors,
            'success_rate': total_success / max(1, total_processed),
            'processing_rate_per_minute': processing_rate,
            'estimated_remaining_time': self._estimate_remaining_time()
        }
    
    def _estimate_remaining_time(self) -> Optional[float]:
        """估算剩余处理时间"""
        if not self.is_running or not self.start_time:
            return None
        
        queue_stats = self.task_queue.get_statistics()
        remaining_tasks = queue_stats['pending_tasks']
        
        if remaining_tasks == 0:
            return 0.0
        
        # 计算平均处理速度
        elapsed_time = time.time() - self.start_time
        worker_stats = [worker.get_statistics() for worker in self.workers]
        total_processed = sum(w['processed_count'] for w in worker_stats)
        
        if total_processed == 0:
            return None
        
        avg_time_per_task = elapsed_time / total_processed
        return remaining_tasks * avg_time_per_task / len(self.workers)
    
    def _report_progress(self):
        """报告处理进度"""
        if self.on_progress_update:
            progress_info = self.get_progress_info()
            self.on_progress_update(progress_info)
    
    def _on_worker_task_complete(self, worker_id: str, task: CompressionTask):
        """工作器任务完成回调"""
        self.total_processed += 1
        self.total_success += 1
        
        if self.on_task_complete:
            self.on_task_complete(task)
    
    def _on_worker_task_error(self, worker_id: str, task: CompressionTask, error: str):
        """工作器任务错误回调"""
        self.total_processed += 1
        self.total_errors += 1
        
        if self.on_task_error:
            self.on_task_error(task, error)
    
    def _on_worker_progress_update(self, worker_id: str, task: CompressionTask):
        """工作器进度更新回调"""
        if self.on_progress_update:
            self._report_progress()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop_processing()


def process_images_batch(image_files: List[str], output_dir: str,
                        target_size_kb: int = 100, max_workers: int = 2,
                        compression_method: str = "standard",
                        replace_original: bool = False,
                        use_priority: bool = False,
                        progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    批量处理图片的便捷函数
    
    Args:
        image_files: 图片文件路径列表
        output_dir: 输出目录
        target_size_kb: 目标文件大小
        max_workers: 最大工作器数量
        compression_method: 压缩方法
        replace_original: 是否替换原图
        use_priority: 是否使用优先级队列
        progress_callback: 进度回调函数
        
    Returns:
        Dict[str, Any]: 处理结果统计
    """
    with BatchProcessor(
        max_workers=max_workers,
        use_priority=use_priority
    ) as processor:
        
        # 设置进度回调
        if progress_callback:
            processor.on_progress_update = progress_callback
        
        # 添加任务
        added_count = processor.add_tasks(
            image_files=image_files,
            output_dir=output_dir,
            target_size_kb=target_size_kb,
            replace_original=replace_original,
            compression_method=compression_method
        )
        
        if added_count == 0:
            return {'error': '没有任务被添加到队列'}
        
        # 开始处理
        if not processor.start_processing():
            return {'error': '无法启动处理器'}
        
        # 等待完成
        success = processor.wait_completion()
        
        # 获取最终统计
        final_stats = processor.get_progress_info()
        final_stats['completed_successfully'] = success
        
        return final_stats


def main():
    """测试函数"""
    print("测试 CompressionTask 类和 TaskQueue")
    print("=" * 60)
    
    # 创建测试任务
    task = CompressionTask(
        input_path="test_image.jpg",
        output_path="test_output.jpg",
        target_size_kb=100,
        compression_method="standard"
    )
    
    print(f"初始状态: {task}")
    print(f"任务ID: {task.task_id}")
    print(f"是否完成: {task.is_finished}")
    print(f"是否成功: {task.is_successful}")
    
    # 模拟任务处理
    print("\n开始处理任务...")
    task.start()
    print(f"处理中: {task}")
    
    # 模拟进度更新
    for i in range(0, 101, 25):
        task.update_progress(i, f"处理进度 {i}%")
        print(f"进度更新: {task}")
        time.sleep(0.1)
    
    # 模拟任务完成
    result = {
        'original_size_bytes': 500000,
        'final_size_bytes': 100000,
        'compression_ratio': 5.0,
        'processing_time_seconds': 2.5
    }
    task.complete(result)
    print(f"任务完成: {task}")
    print(f"处理时长: {task.duration_seconds:.2f}秒")
    
    # 测试任务字典转换
    print(f"\n任务字典: {task.to_dict()}")
    
    # 测试批量创建任务
    print(f"\n测试批量创建任务...")
    test_files = ["img1.jpg", "img2.png", "img3.gif"]
    tasks = create_compression_tasks(
        test_files, 
        "output", 
        target_size_kb=100, 
        compression_method="standard"
    )
    
    print(f"创建了 {len(tasks)} 个任务:")
    for task in tasks:
        print(f"  {task}")
    
    # 测试队列功能
    print(f"\n" + "=" * 60)
    print("测试 TaskQueue 功能")
    print("=" * 60)
    
    # 创建普通队列
    print("\n1. 测试普通队列")
    normal_queue = TaskQueue(max_size=10, use_priority=False)
    print(f"队列创建: {normal_queue}")
    
    # 添加任务
    success_count = normal_queue.add_tasks(tasks)
    print(f"批量添加任务: {success_count}/{len(tasks)} 成功")
    print(f"队列状态: {normal_queue}")
    print(f"统计信息: {normal_queue.get_statistics()}")
    
    # 测试获取任务
    print(f"\n2. 测试任务获取")
    task1 = normal_queue.get_task(timeout=1.0)
    if task1:
        print(f"获取任务: {task1}")
        task1.start()
        print(f"任务状态: {task1}")
        
        # 模拟任务完成
        result = {'original_size_bytes': 300000, 'final_size_bytes': 80000, 'compression_ratio': 3.75}
        task1.complete(result)
        normal_queue.task_done(task1)
        print(f"任务完成: {task1}")
    
    print(f"队列状态: {normal_queue}")
    
    # 测试优先级队列
    print(f"\n3. 测试优先级队列")
    priority_queue = TaskQueue(max_size=10, use_priority=True)
    
    # 创建不同优先级的任务
    high_task = CompressionTask("high_priority.jpg", "output/high.jpg")
    normal_task = CompressionTask("normal_priority.jpg", "output/normal.jpg")
    low_task = CompressionTask("low_priority.jpg", "output/low.jpg")
    
    # 按相反顺序添加（低->普通->高）
    priority_queue.add_task(low_task, TaskPriority.LOW)
    priority_queue.add_task(normal_task, TaskPriority.NORMAL)
    priority_queue.add_task(high_task, TaskPriority.HIGH)
    
    print(f"优先级队列: {priority_queue}")
    
    # 按优先级获取任务
    print("按优先级获取任务:")
    for i in range(3):
        task = priority_queue.get_task(timeout=1.0)
        if task:
            print(f"  获取到: {task} (预期高优先级先出)")
            priority_queue.task_done(task)
    
    # 测试任务状态查询
    print(f"\n4. 测试任务状态查询")
    print(f"所有任务数: {normal_queue.total_tasks}")
    print(f"等待中任务: {normal_queue.pending_tasks_count}")
    print(f"已完成任务: {normal_queue.completed_tasks_count}")
    
    pending_tasks = normal_queue.get_tasks_by_status(TaskStatus.PENDING)
    print(f"等待中任务详情: {[str(t) for t in pending_tasks]}")
    
    # 测试任务取消
    if pending_tasks:
        cancelled = normal_queue.cancel_task(pending_tasks[0].task_id)
        print(f"取消任务: {'成功' if cancelled else '失败'}")
        print(f"队列状态: {normal_queue}")
    
    print(f"\n测试完成！")
    
    # 测试批量处理器
    print(f"\n" + "=" * 60)
    print("测试 BatchProcessor 批量处理器")
    print("=" * 60)
    
    # 创建测试文件列表（模拟）
    test_image_files = [
        "sample1.jpg",
        "sample2.png", 
        "sample3.gif",
        "sample4.webp"
    ]
    
    print(f"模拟批量处理 {len(test_image_files)} 个图片文件:")
    for file in test_image_files:
        print(f"  - {file}")
    
    # 创建批量处理器
    print(f"\n创建批量处理器（2个工作器）...")
    processor = BatchProcessor(max_workers=2, max_queue_size=50, use_priority=False)
    
    # 添加任务（模拟）
    print(f"添加批量任务...")
    # 注意：这里只是模拟添加，实际不会处理因为文件不存在
    
    # 显示处理器信息
    print(f"✅ 批量处理器创建成功")
    print(f"  最大工作器数: {processor.max_workers}")
    print(f"  队列大小限制: {processor.max_queue_size}")
    print(f"  使用优先级队列: {processor.use_priority}")
    print(f"  当前运行状态: {processor.is_running}")
    
    # 测试便捷函数接口
    print(f"\n测试便捷函数接口...")
    print(f"process_images_batch() 函数可用于快速批量处理")
    print(f"支持参数: 工作器数量、压缩方法、优先级队列、进度回调等")
    
    print(f"\n✅ 批量处理器测试完成！")


if __name__ == "__main__":
    main() 