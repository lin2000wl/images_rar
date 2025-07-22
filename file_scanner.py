#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件系统操作模块
实现递归扫描文件夹及筛选图片文件的功能
"""

import logging
from pathlib import Path
from typing import List, Set, Generator, Tuple, Optional
import time


class ImageScanner:
    """图片文件扫描器类"""
    
    # 支持的图片格式（小写）
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    # 文件大小阈值（字节）
    SIZE_THRESHOLD = 100 * 1024  # 100KB
    
    def __init__(self, min_size_kb: int = 100):
        """
        初始化图片扫描器
        
        Args:
            min_size_kb: 最小文件大小（KB），默认100KB
        """
        self.min_size_bytes = min_size_kb * 1024
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def scan_directory(self, directory_path: str) -> Generator[Path, None, None]:
        """
        递归扫描指定目录，返回所有文件路径
        
        Args:
            directory_path: 要扫描的目录路径
            
        Yields:
            Path: 文件路径对象
            
        Raises:
            FileNotFoundError: 目录不存在
            PermissionError: 没有访问权限
        """
        try:
            directory = Path(directory_path)
            
            # 检查目录是否存在
            if not directory.exists():
                raise FileNotFoundError(f"目录不存在: {directory_path}")
            
            if not directory.is_dir():
                raise ValueError(f"路径不是目录: {directory_path}")
            
            self.logger.info(f"开始扫描目录: {directory_path}")
            
            # 递归遍历目录
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    yield file_path
                    
        except PermissionError as e:
            self.logger.error(f"权限不足，无法访问目录: {directory_path}")
            raise PermissionError(f"无法访问目录: {directory_path}") from e
        except Exception as e:
            self.logger.error(f"扫描目录时发生错误: {e}")
            raise
    
    def is_supported_image(self, file_path: Path) -> bool:
        """
        检查文件是否为支持的图片格式
        
        Args:
            file_path: 文件路径对象
            
        Returns:
            bool: 是否为支持的图片格式
        """
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def check_file_size(self, file_path: Path) -> bool:
        """
        检查文件大小是否满足条件
        
        Args:
            file_path: 文件路径对象
            
        Returns:
            bool: 文件大小是否大于阈值
            
        Raises:
            OSError: 无法获取文件信息
        """
        try:
            return file_path.stat().st_size > self.min_size_bytes
        except OSError as e:
            self.logger.warning(f"无法获取文件大小: {file_path}, 错误: {e}")
            return False
    
    def scan_images(self, directory_path: str) -> List[Path]:
        """
        扫描目录中符合条件的图片文件
        
        Args:
            directory_path: 要扫描的目录路径
            
        Returns:
            List[Path]: 符合条件的图片文件路径列表
        """
        start_time = time.time()
        image_files = []
        total_files = 0
        
        try:
            self.logger.info(f"开始扫描图片文件: {directory_path}")
            
            for file_path in self.scan_directory(directory_path):
                total_files += 1
                
                # 检查是否为支持的图片格式
                if self.is_supported_image(file_path):
                    # 检查文件大小
                    if self.check_file_size(file_path):
                        image_files.append(file_path)
                        self.logger.debug(f"找到符合条件的图片: {file_path}")
            
            elapsed_time = time.time() - start_time
            self.logger.info(
                f"扫描完成 - 总文件数: {total_files}, "
                f"符合条件的图片: {len(image_files)}, "
                f"耗时: {elapsed_time:.2f}秒"
            )
            
            return image_files
            
        except Exception as e:
            self.logger.error(f"扫描图片文件时发生错误: {e}")
            raise
    
    def get_scan_summary(self, directory_path: str) -> Tuple[int, int, List[str]]:
        """
        获取目录扫描摘要信息
        
        Args:
            directory_path: 要扫描的目录路径
            
        Returns:
            Tuple[int, int, List[str]]: (总文件数, 符合条件的图片数, 图片格式统计)
        """
        try:
            image_files = self.scan_images(directory_path)
            total_images = len(image_files)
            
            # 统计图片格式
            format_count = {}
            for img_path in image_files:
                ext = img_path.suffix.lower()
                format_count[ext] = format_count.get(ext, 0) + 1
            
            format_summary = [f"{ext}: {count}" for ext, count in format_count.items()]
            
            return total_images, total_images, format_summary
            
        except Exception as e:
            self.logger.error(f"获取扫描摘要时发生错误: {e}")
            return 0, 0, []
    
    @classmethod
    def get_supported_formats(cls) -> Set[str]:
        """
        获取支持的图片格式列表
        
        Returns:
            Set[str]: 支持的文件扩展名集合
        """
        return cls.SUPPORTED_FORMATS.copy()
    
    def set_size_threshold(self, size_kb: int) -> None:
        """
        设置文件大小阈值
        
        Args:
            size_kb: 大小阈值（KB）
        """
        if size_kb <= 0:
            raise ValueError("文件大小阈值必须大于0")
        
        self.min_size_bytes = size_kb * 1024
        self.logger.info(f"文件大小阈值已设置为: {size_kb}KB")


def main():
    """测试函数"""
    # 创建扫描器实例
    scanner = ImageScanner(min_size_kb=100)
    
    # 测试扫描当前目录
    try:
        current_dir = "."
        print(f"扫描目录: {current_dir}")
        
        image_files = scanner.scan_images(current_dir)
        
        print(f"\n找到 {len(image_files)} 个符合条件的图片文件:")
        for img_file in image_files:
            file_size = img_file.stat().st_size / 1024  # 转换为KB
            print(f"  {img_file} ({file_size:.1f}KB)")
        
        # 显示摘要信息
        total, valid, formats = scanner.get_scan_summary(current_dir)
        print(f"\n扫描摘要:")
        print(f"  符合条件的图片: {valid}")
        print(f"  格式分布: {', '.join(formats) if formats else '无'}")
        
    except Exception as e:
        print(f"测试时发生错误: {e}")


if __name__ == "__main__":
    main() 