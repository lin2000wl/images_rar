#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片压缩模块
实现图片压缩至100KB内的核心功能
"""

import logging
import os
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image, ImageFile
import io


# 允许加载截断的图片
ImageFile.LOAD_TRUNCATED_IMAGES = True


class ImageInfo:
    """图片信息类"""
    
    def __init__(self, width: int, height: int, format: str, mode: str, 
                 file_size: int, file_path: str):
        self.width = width
        self.height = height
        self.format = format
        self.mode = mode
        self.file_size = file_size
        self.file_path = file_path
        
    def __str__(self) -> str:
        return (f"ImageInfo(width={self.width}, height={self.height}, "
                f"format={self.format}, mode={self.mode}, "
                f"size={self.file_size/1024:.1f}KB)")
    
    @property
    def aspect_ratio(self) -> float:
        """获取宽高比"""
        return self.width / self.height if self.height > 0 else 1.0
    
    @property
    def total_pixels(self) -> int:
        """获取总像素数"""
        return self.width * self.height


class ImageCompressor:
    """图片压缩器类"""
    
    # 支持的输入格式
    SUPPORTED_INPUT_FORMATS = {'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP'}
    
    # 默认目标文件大小（字节）
    DEFAULT_TARGET_SIZE = 100 * 1024  # 100KB
    
    def __init__(self, target_size_kb: int = 100):
        """
        初始化图片压缩器
        
        Args:
            target_size_kb: 目标文件大小（KB），默认100KB
        """
        self.target_size_bytes = target_size_kb * 1024
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(f"{__name__}.ImageCompressor")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def load_image_info(self, image_path: str) -> ImageInfo:
        """
        加载图片并获取基本信息
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            ImageInfo: 图片信息对象
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的图片格式或损坏的图片文件
            OSError: 无法读取文件
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 获取文件大小
            file_size = os.path.getsize(image_path)
            
            # 使用Pillow加载图片
            with Image.open(image_path) as img:
                # 获取图片基本信息
                width, height = img.size
                format_name = img.format
                mode = img.mode
                
                # 验证格式是否支持
                if format_name not in self.SUPPORTED_INPUT_FORMATS:
                    raise ValueError(f"不支持的图片格式: {format_name}")
                
                # 创建图片信息对象
                image_info = ImageInfo(
                    width=width,
                    height=height,
                    format=format_name,
                    mode=mode,
                    file_size=file_size,
                    file_path=image_path
                )
                
                self.logger.info(f"成功加载图片信息: {image_info}")
                return image_info
                
        except FileNotFoundError:
            self.logger.error(f"文件不存在: {image_path}")
            raise
        except ValueError as e:
            self.logger.error(f"图片格式错误: {e}")
            raise
        except Exception as e:
            self.logger.error(f"加载图片时发生错误: {e}")
            raise OSError(f"无法读取图片文件: {image_path}") from e
    
    def validate_image(self, image_path: str) -> bool:
        """
        验证图片文件是否有效且可处理
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            bool: 图片是否有效
        """
        try:
            self.load_image_info(image_path)
            return True
        except Exception as e:
            self.logger.warning(f"图片验证失败: {image_path}, 错误: {e}")
            return False
    
    def calculate_quality_parameter(self, image_path: str, target_size_bytes: Optional[int] = None, 
                                   max_iterations: int = 20) -> Tuple[int, int]:
        """
        使用二分查找算法动态计算最佳压缩质量参数
        
        Args:
            image_path: 图片文件路径
            target_size_bytes: 目标文件大小（字节），默认使用实例设置
            max_iterations: 最大迭代次数，防止死循环
            
        Returns:
            Tuple[int, int]: (最佳质量参数, 最终文件大小)
            
        Raises:
            ValueError: 图片格式不支持质量参数调整
            OSError: 无法处理图片文件
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            # 加载图片信息
            image_info = self.load_image_info(image_path)
            
            # 如果原图已经小于目标大小，返回最高质量
            if image_info.file_size <= target_size_bytes:
                self.logger.info(f"图片已小于目标大小，无需压缩: {image_info.file_size} <= {target_size_bytes}")
                return 95, image_info.file_size
            
            # 检查格式是否支持质量参数
            if image_info.format not in {'JPEG', 'WEBP'}:
                self.logger.warning(f"格式 {image_info.format} 不支持质量参数，将尝试转换为JPEG")
            
            # 使用二分查找算法
            with Image.open(image_path) as img:
                # 如果是RGBA模式，转换为RGB（JPEG不支持透明度）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                low, high = 1, 95
                best_quality = high
                best_size = float('inf')
                iterations = 0
                
                self.logger.info(f"开始二分查找最佳质量参数，目标大小: {target_size_bytes/1024:.1f}KB")
                
                while low <= high and iterations < max_iterations:
                    iterations += 1
                    mid = (low + high) // 2
                    
                    # 使用内存缓冲区测试压缩效果
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=mid)
                    current_size = buffer.tell()
                    
                    self.logger.debug(f"迭代 {iterations}: quality={mid}, size={current_size/1024:.1f}KB")
                    
                    if current_size <= target_size_bytes:
                        # 文件大小符合要求，尝试更高质量
                        best_quality = mid
                        best_size = current_size
                        low = mid + 1
                    else:
                        # 文件太大，降低质量
                        high = mid - 1
                    
                    buffer.close()
                
                self.logger.info(f"二分查找完成: 最佳质量={best_quality}, "
                               f"最终大小={best_size/1024:.1f}KB, 迭代次数={iterations}")
                
                return best_quality, best_size
                
        except Exception as e:
            self.logger.error(f"计算质量参数时发生错误: {e}")
            raise OSError(f"无法计算质量参数: {image_path}") from e
    
    def calculate_optimal_dimensions(self, original_width: int, original_height: int, 
                                   target_size_bytes: int, current_file_size: int) -> Tuple[int, int]:
        """
        计算保持宽高比的最佳分辨率
        
        Args:
            original_width: 原始宽度
            original_height: 原始高度
            target_size_bytes: 目标文件大小（字节）
            current_file_size: 当前文件大小（字节）
            
        Returns:
            Tuple[int, int]: (新宽度, 新高度)
        """
        # 如果当前文件已经小于目标大小，不需要调整分辨率
        if current_file_size <= target_size_bytes:
            return original_width, original_height
        
        # 计算压缩比例（基于文件大小的平方根关系）
        size_ratio = target_size_bytes / current_file_size
        scale_factor = min(1.0, size_ratio ** 0.5)
        
        # 计算新的尺寸，保持宽高比
        new_width = max(1, int(original_width * scale_factor))
        new_height = max(1, int(original_height * scale_factor))
        
        # 确保尺寸是偶数（某些编码器要求）
        new_width = new_width if new_width % 2 == 0 else new_width - 1
        new_height = new_height if new_height % 2 == 0 else new_height - 1
        
        # 最小尺寸限制
        min_dimension = 32
        if new_width < min_dimension or new_height < min_dimension:
            aspect_ratio = original_width / original_height
            if aspect_ratio > 1:  # 宽图
                new_width = min_dimension
                new_height = max(min_dimension, int(min_dimension / aspect_ratio))
            else:  # 高图
                new_height = min_dimension
                new_width = max(min_dimension, int(min_dimension * aspect_ratio))
        
        self.logger.info(f"分辨率调整: {original_width}x{original_height} -> {new_width}x{new_height} "
                        f"(缩放因子: {scale_factor:.3f})")
        
        return new_width, new_height
    
    def resize_image_smart(self, image_path: str, target_size_bytes: Optional[int] = None) -> Tuple[Image.Image, Tuple[int, int]]:
        """
        智能调整图片分辨率，保持宽高比
        
        Args:
            image_path: 图片文件路径
            target_size_bytes: 目标文件大小（字节），默认使用实例设置
            
        Returns:
            Tuple[Image.Image, Tuple[int, int]]: (调整后的图片对象, (新宽度, 新高度))
            
        Raises:
            OSError: 无法处理图片文件
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            # 加载图片信息
            image_info = self.load_image_info(image_path)
            
            # 计算最佳尺寸
            new_width, new_height = self.calculate_optimal_dimensions(
                image_info.width, image_info.height, 
                target_size_bytes, image_info.file_size
            )
            
            # 加载并调整图片
            with Image.open(image_path) as img:
                # 转换颜色模式（如果需要）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 如果尺寸没有变化，直接返回
                if new_width == image_info.width and new_height == image_info.height:
                    return img.copy(), (new_width, new_height)
                
                # 使用高质量重采样算法调整尺寸
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                self.logger.info(f"图片分辨率已调整: {image_info.width}x{image_info.height} -> {new_width}x{new_height}")
                
                return resized_img, (new_width, new_height)
                
        except Exception as e:
            self.logger.error(f"调整图片分辨率时发生错误: {e}")
            raise OSError(f"无法调整图片分辨率: {image_path}") from e
    
    def estimate_file_size_after_resize(self, image_path: str, new_width: int, new_height: int, 
                                      quality: int = 85) -> int:
        """
        估算调整分辨率后的文件大小
        
        Args:
            image_path: 原始图片路径
            new_width: 新宽度
            new_height: 新高度
            quality: JPEG质量参数
            
        Returns:
            int: 估算的文件大小（字节）
        """
        try:
            with Image.open(image_path) as img:
                # 转换颜色模式
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 调整尺寸
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # 估算文件大小
                buffer = io.BytesIO()
                resized_img.save(buffer, format='JPEG', quality=quality)
                estimated_size = buffer.tell()
                buffer.close()
                
                return estimated_size
                
        except Exception as e:
            self.logger.warning(f"估算文件大小时发生错误: {e}")
            return 0
    
    def save_compressed_image(self, image: Image.Image, output_path: str, 
                            quality: int, target_size_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        保存压缩后的图片并验证结果
        
        Args:
            image: PIL图片对象
            output_path: 输出文件路径
            quality: JPEG质量参数
            target_size_bytes: 目标文件大小（字节），用于验证
            
        Returns:
            Dict[str, Any]: 保存结果信息
            
        Raises:
            OSError: 无法保存文件
            ValueError: 保存后文件大小超出限制
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 保存图片
            save_start_time = time.time()
            image.save(output_path, format='JPEG', quality=quality, optimize=True)
            save_time = time.time() - save_start_time
            
            # 验证保存结果
            if not os.path.exists(output_path):
                raise OSError(f"保存失败，文件不存在: {output_path}")
            
            # 获取保存后的文件信息
            final_file_size = os.path.getsize(output_path)
            
            # 验证文件大小
            if final_file_size > target_size_bytes:
                self.logger.warning(f"保存后文件大小超出目标: {final_file_size/1024:.1f}KB > {target_size_bytes/1024:.1f}KB")
                # 注意：这里不抛出异常，因为可能是由于JPEG编码器的差异
            
            # 验证图片完整性
            try:
                with Image.open(output_path) as saved_img:
                    saved_width, saved_height = saved_img.size
                    saved_format = saved_img.format
            except Exception as e:
                raise ValueError(f"保存的图片文件损坏: {e}")
            
            # 计算压缩统计信息
            compression_ratio = 1.0  # 需要原始文件大小来计算
            
            result = {
                'output_path': output_path,
                'final_size_bytes': final_file_size,
                'final_size_kb': final_file_size / 1024,
                'quality_used': quality,
                'dimensions': (saved_width, saved_height),
                'format': saved_format,
                'save_time_seconds': save_time,
                'target_achieved': final_file_size <= target_size_bytes,
                'size_difference_kb': (final_file_size - target_size_bytes) / 1024
            }
            
            self.logger.info(f"图片保存成功: {output_path}, "
                           f"大小: {final_file_size/1024:.1f}KB, "
                           f"质量: {quality}, "
                           f"尺寸: {saved_width}x{saved_height}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"保存压缩图片时发生错误: {e}")
            raise OSError(f"无法保存压缩图片: {output_path}") from e
    
    def compress_single_image(self, input_path: str, output_path: str, 
                            target_size_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        完整的单张图片压缩流程
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            target_size_bytes: 目标文件大小（字节）
            
        Returns:
            Dict[str, Any]: 压缩结果详情
            
        Raises:
            OSError: 无法处理图片文件
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            start_time = time.time()
            
            # 1. 加载图片信息
            original_info = self.load_image_info(input_path)
            self.logger.info(f"开始压缩图片: {input_path} -> {output_path}")
            self.logger.info(f"原始信息: {original_info}")
            
            # 2. 检查是否需要压缩
            if original_info.file_size <= target_size_bytes:
                # 直接复制文件
                import shutil
                shutil.copy2(input_path, output_path)
                
                result = {
                    'input_path': input_path,
                    'output_path': output_path,
                    'original_size_bytes': original_info.file_size,
                    'final_size_bytes': original_info.file_size,
                    'compression_ratio': 1.0,
                    'quality_used': 95,  # 原始质量
                    'dimensions_original': (original_info.width, original_info.height),
                    'dimensions_final': (original_info.width, original_info.height),
                    'resize_applied': False,
                    'processing_time_seconds': time.time() - start_time,
                    'target_achieved': True,
                    'method': 'direct_copy'
                }
                
                self.logger.info("图片已符合大小要求，直接复制完成")
                return result
            
            # 3. 智能调整分辨率
            resized_img, (new_width, new_height) = self.resize_image_smart(input_path, target_size_bytes)
            resize_applied = (new_width != original_info.width or new_height != original_info.height)
            
            # 4. 计算最佳质量参数
            if resize_applied:
                # 对调整后的图片计算质量参数
                temp_buffer = io.BytesIO()
                resized_img.save(temp_buffer, format='JPEG', quality=85)
                temp_size = temp_buffer.tell()
                temp_buffer.close()
                
                if temp_size > target_size_bytes:
                    # 需要进一步压缩质量
                    best_quality = self._calculate_quality_for_resized_image(
                        resized_img, target_size_bytes
                    )
                else:
                    best_quality = 85  # 默认高质量
            else:
                # 对原始图片计算质量参数
                best_quality, _ = self.calculate_quality_parameter(input_path, target_size_bytes)
                resized_img = Image.open(input_path)
                if resized_img.mode in ('RGBA', 'P'):
                    resized_img = resized_img.convert('RGB')
            
            # 5. 保存压缩后的图片
            save_result = self.save_compressed_image(resized_img, output_path, best_quality, target_size_bytes)
            
            # 6. 计算最终统计信息
            compression_ratio = original_info.file_size / save_result['final_size_bytes']
            processing_time = time.time() - start_time
            
            result = {
                'input_path': input_path,
                'output_path': output_path,
                'original_size_bytes': original_info.file_size,
                'final_size_bytes': save_result['final_size_bytes'],
                'compression_ratio': compression_ratio,
                'quality_used': best_quality,
                'dimensions_original': (original_info.width, original_info.height),
                'dimensions_final': (new_width, new_height),
                'resize_applied': resize_applied,
                'processing_time_seconds': processing_time,
                'target_achieved': save_result['target_achieved'],
                'method': 'smart_compression'
            }
            
            self.logger.info(f"图片压缩完成: 压缩比 {compression_ratio:.2f}x, "
                           f"处理时间 {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"压缩图片时发生错误: {e}")
            raise OSError(f"无法压缩图片: {input_path}") from e
        finally:
            # 确保释放图片资源
            if 'resized_img' in locals():
                resized_img.close()
    
    def _calculate_quality_for_resized_image(self, image: Image.Image, 
                                           target_size_bytes: int, max_iterations: int = 15) -> int:
        """
        为已调整尺寸的图片计算最佳质量参数
        
        Args:
            image: PIL图片对象
            target_size_bytes: 目标文件大小
            max_iterations: 最大迭代次数
            
        Returns:
            int: 最佳质量参数
        """
        low, high = 1, 95
        best_quality = high
        iterations = 0
        
        while low <= high and iterations < max_iterations:
            iterations += 1
            mid = (low + high) // 2
            
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=mid)
            current_size = buffer.tell()
            buffer.close()
            
            if current_size <= target_size_bytes:
                best_quality = mid
                low = mid + 1
            else:
                high = mid - 1
        
        return best_quality
    
    def compress_with_webp(self, input_path: str, output_path: str, 
                          target_size_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        使用WebP格式进行高效压缩
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径（应以.webp结尾）
            target_size_bytes: 目标文件大小（字节）
            
        Returns:
            Dict[str, Any]: 压缩结果详情
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            start_time = time.time()
            
            # 加载图片信息
            original_info = self.load_image_info(input_path)
            self.logger.info(f"开始WebP压缩: {input_path} -> {output_path}")
            
            with Image.open(input_path) as img:
                # 保持透明度支持
                if img.mode in ('RGBA', 'LA') or 'transparency' in img.info:
                    # WebP支持透明度，保持原始模式
                    pass
                elif img.mode == 'P':
                    img = img.convert('RGBA')
                elif img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                # 如果原图已经很小，直接使用高质量保存
                if original_info.file_size <= target_size_bytes:
                    img.save(output_path, format='WEBP', quality=95, optimize=True)
                    final_size = os.path.getsize(output_path)
                    
                    result = {
                        'input_path': input_path,
                        'output_path': output_path,
                        'original_size_bytes': original_info.file_size,
                        'final_size_bytes': final_size,
                        'compression_ratio': original_info.file_size / final_size,
                        'quality_used': 95,
                        'format': 'WEBP',
                        'processing_time_seconds': time.time() - start_time,
                        'method': 'webp_high_quality'
                    }
                    
                    self.logger.info("WebP压缩完成（高质量）")
                    return result
                
                # 使用二分查找确定最佳质量
                low, high = 1, 95
                best_quality = high
                best_size = float('inf')
                iterations = 0
                max_iterations = 20
                
                while low <= high and iterations < max_iterations:
                    iterations += 1
                    mid = (low + high) // 2
                    
                    buffer = io.BytesIO()
                    img.save(buffer, format='WEBP', quality=mid, optimize=True)
                    current_size = buffer.tell()
                    buffer.close()
                    
                    if current_size <= target_size_bytes:
                        best_quality = mid
                        best_size = current_size
                        low = mid + 1
                    else:
                        high = mid - 1
                
                # 保存最终结果
                img.save(output_path, format='WEBP', quality=best_quality, optimize=True)
                final_size = os.path.getsize(output_path)
                
                result = {
                    'input_path': input_path,
                    'output_path': output_path,
                    'original_size_bytes': original_info.file_size,
                    'final_size_bytes': final_size,
                    'compression_ratio': original_info.file_size / final_size,
                    'quality_used': best_quality,
                    'format': 'WEBP',
                    'processing_time_seconds': time.time() - start_time,
                    'iterations': iterations,
                    'method': 'webp_optimized'
                }
                
                self.logger.info(f"WebP压缩完成: 质量={best_quality}, "
                               f"压缩比={result['compression_ratio']:.2f}x, "
                               f"迭代次数={iterations}")
                
                return result
                
        except Exception as e:
            self.logger.error(f"WebP压缩时发生错误: {e}")
            raise OSError(f"无法进行WebP压缩: {input_path}") from e
    
    def compress_with_advanced_jpeg(self, input_path: str, output_path: str,
                                   target_size_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        使用高级JPEG优化技术进行压缩
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            target_size_bytes: 目标文件大小（字节）
            
        Returns:
            Dict[str, Any]: 压缩结果详情
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            start_time = time.time()
            
            # 加载图片信息
            original_info = self.load_image_info(input_path)
            self.logger.info(f"开始高级JPEG压缩: {input_path} -> {output_path}")
            
            with Image.open(input_path) as img:
                # 转换为RGB模式（JPEG不支持透明度）
                if img.mode in ('RGBA', 'P'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 如果需要，先调整分辨率
                if original_info.file_size > target_size_bytes * 2:  # 如果文件太大，先缩小
                    new_width, new_height = self.calculate_optimal_dimensions(
                        original_info.width, original_info.height,
                        target_size_bytes, original_info.file_size
                    )
                    if new_width != original_info.width or new_height != original_info.height:
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        self.logger.info(f"预调整分辨率: {original_info.width}x{original_info.height} -> {new_width}x{new_height}")
                
                # 使用二分查找确定最佳质量
                low, high = 1, 95
                best_quality = high
                best_size = float('inf')
                iterations = 0
                max_iterations = 20
                
                while low <= high and iterations < max_iterations:
                    iterations += 1
                    mid = (low + high) // 2
                    
                    buffer = io.BytesIO()
                    # 使用高级JPEG参数
                    img.save(buffer, format='JPEG', quality=mid, optimize=True, 
                            progressive=True, subsampling=0)
                    current_size = buffer.tell()
                    buffer.close()
                    
                    if current_size <= target_size_bytes:
                        best_quality = mid
                        best_size = current_size
                        low = mid + 1
                    else:
                        high = mid - 1
                
                # 保存最终结果
                img.save(output_path, format='JPEG', quality=best_quality, optimize=True,
                        progressive=True, subsampling=0)
                final_size = os.path.getsize(output_path)
                
                result = {
                    'input_path': input_path,
                    'output_path': output_path,
                    'original_size_bytes': original_info.file_size,
                    'final_size_bytes': final_size,
                    'compression_ratio': original_info.file_size / final_size,
                    'quality_used': best_quality,
                    'format': 'JPEG',
                    'processing_time_seconds': time.time() - start_time,
                    'iterations': iterations,
                    'method': 'advanced_jpeg',
                    'optimizations': ['optimize', 'progressive', 'subsampling=0']
                }
                
                self.logger.info(f"高级JPEG压缩完成: 质量={best_quality}, "
                               f"压缩比={result['compression_ratio']:.2f}x")
                
                return result
                
        except Exception as e:
            self.logger.error(f"高级JPEG压缩时发生错误: {e}")
            raise OSError(f"无法进行高级JPEG压缩: {input_path}") from e
    
    def compress_with_best_method(self, input_path: str, output_dir: str,
                                 target_size_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        尝试多种压缩方法，选择最佳结果
        
        Args:
            input_path: 输入图片路径
            output_dir: 输出目录
            target_size_bytes: 目标文件大小（字节）
            
        Returns:
            Dict[str, Any]: 最佳压缩结果详情
        """
        if target_size_bytes is None:
            target_size_bytes = self.target_size_bytes
        
        try:
            start_time = time.time()
            original_info = self.load_image_info(input_path)
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            
            self.logger.info(f"开始多方法压缩测试: {input_path}")
            
            methods = []
            
            # 方法1: 标准压缩
            try:
                standard_output = os.path.join(output_dir, f"{base_name}_standard.jpg")
                standard_result = self.compress_single_image(input_path, standard_output, target_size_bytes)
                standard_result['method_name'] = 'standard'
                methods.append(standard_result)
                self.logger.info(f"标准方法: {standard_result['final_size_bytes']/1024:.1f}KB")
            except Exception as e:
                self.logger.warning(f"标准方法失败: {e}")
            
            # 方法2: 高级JPEG
            try:
                jpeg_output = os.path.join(output_dir, f"{base_name}_advanced.jpg")
                jpeg_result = self.compress_with_advanced_jpeg(input_path, jpeg_output, target_size_bytes)
                jpeg_result['method_name'] = 'advanced_jpeg'
                methods.append(jpeg_result)
                self.logger.info(f"高级JPEG: {jpeg_result['final_size_bytes']/1024:.1f}KB")
            except Exception as e:
                self.logger.warning(f"高级JPEG方法失败: {e}")
            
            # 方法3: WebP格式
            try:
                webp_output = os.path.join(output_dir, f"{base_name}_webp.webp")
                webp_result = self.compress_with_webp(input_path, webp_output, target_size_bytes)
                webp_result['method_name'] = 'webp'
                methods.append(webp_result)
                self.logger.info(f"WebP方法: {webp_result['final_size_bytes']/1024:.1f}KB")
            except Exception as e:
                self.logger.warning(f"WebP方法失败: {e}")
            
            if not methods:
                raise OSError("所有压缩方法都失败了")
            
            # 选择最佳方法（优先考虑文件大小，其次考虑质量）
            def score_method(result):
                size_score = 1.0 if result.get('target_achieved', False) else 0.5
                efficiency_score = min(1.0, target_size_bytes / result['final_size_bytes'])
                quality_score = result.get('quality_used', 50) / 100
                return size_score * 0.5 + efficiency_score * 0.3 + quality_score * 0.2
            
            best_method = max(methods, key=score_method)
            
            # 清理其他文件，保留最佳结果
            format_ext = best_method.get('format', 'jpg').lower()
            if format_ext == 'jpeg':
                format_ext = 'jpg'
            final_output = os.path.join(output_dir, f"{base_name}_compressed.{format_ext}")
            if best_method['output_path'] != final_output:
                import shutil
                shutil.move(best_method['output_path'], final_output)
            
            # 删除其他临时文件
            for method in methods:
                if method != best_method and os.path.exists(method['output_path']):
                    try:
                        os.remove(method['output_path'])
                    except:
                        pass
            
            # 更新最终结果
            best_method['output_path'] = final_output
            best_method['total_processing_time'] = time.time() - start_time
            best_method['methods_tested'] = len(methods)
            best_method['all_results'] = methods
            
            self.logger.info(f"最佳方法选择: {best_method['method_name']}, "
                           f"最终大小: {best_method['final_size_bytes']/1024:.1f}KB")
            
            return best_method
            
        except Exception as e:
            self.logger.error(f"多方法压缩时发生错误: {e}")
            raise OSError(f"无法进行多方法压缩: {input_path}") from e
    
    def get_compression_info(self, image_path: str) -> Dict[str, Any]:
        """
        获取图片压缩相关信息
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            Dict[str, Any]: 压缩信息字典
        """
        try:
            image_info = self.load_image_info(image_path)
            
            # 计算压缩需求
            needs_compression = image_info.file_size > self.target_size_bytes
            compression_ratio = image_info.file_size / self.target_size_bytes if needs_compression else 1.0
            
            # 估算需要的分辨率缩放
            if needs_compression:
                scale_factor = min(1.0, (self.target_size_bytes / image_info.file_size) ** 0.5)
                estimated_width = int(image_info.width * scale_factor)
                estimated_height = int(image_info.height * scale_factor)
            else:
                scale_factor = 1.0
                estimated_width = image_info.width
                estimated_height = image_info.height
            
            # 如果需要压缩，计算最佳质量参数
            best_quality = None
            estimated_compressed_size = None
            if needs_compression and image_info.format in {'JPEG', 'WEBP'}:
                try:
                    best_quality, estimated_compressed_size = self.calculate_quality_parameter(image_path)
                except Exception as e:
                    self.logger.warning(f"无法计算质量参数: {e}")
            
            return {
                'original_info': image_info,
                'needs_compression': needs_compression,
                'compression_ratio': compression_ratio,
                'scale_factor': scale_factor,
                'estimated_dimensions': (estimated_width, estimated_height),
                'target_size_bytes': self.target_size_bytes,
                'best_quality': best_quality,
                'estimated_compressed_size': estimated_compressed_size
            }
            
        except Exception as e:
            self.logger.error(f"获取压缩信息时发生错误: {e}")
            raise


def main():
    """测试函数"""
    # 创建压缩器实例
    compressor = ImageCompressor(target_size_kb=100)
    
    # 测试当前目录中的图片文件
    current_dir = Path(".")
    test_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    
    print("测试图片加载与信息获取功能...")
    print("-" * 50)
    
    found_images = False
    for ext in test_extensions:
        for img_file in current_dir.glob(f"*{ext}"):
            found_images = True
            try:
                print(f"\n测试图片: {img_file}")
                
                # 测试图片信息加载
                image_info = compressor.load_image_info(str(img_file))
                print(f"  {image_info}")
                
                # 测试压缩信息获取
                compression_info = compressor.get_compression_info(str(img_file))
                print(f"  需要压缩: {compression_info['needs_compression']}")
                print(f"  压缩比例: {compression_info['compression_ratio']:.2f}")
                print(f"  缩放因子: {compression_info['scale_factor']:.2f}")
                print(f"  预估尺寸: {compression_info['estimated_dimensions']}")
                
            except Exception as e:
                print(f"  错误: {e}")
    
    if not found_images:
        print("当前目录中未找到测试图片文件")
        print("支持的格式:", compressor.SUPPORTED_INPUT_FORMATS)


if __name__ == "__main__":
    main() 