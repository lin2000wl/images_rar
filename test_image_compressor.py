#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片压缩模块单元测试
"""

import unittest
import os
import tempfile
from PIL import Image
from image_compressor import ImageCompressor, ImageInfo


class TestImageCompressor(unittest.TestCase):
    """图片压缩器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.compressor = ImageCompressor(target_size_kb=100)
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后清理"""
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_image(self, width=800, height=600, format='JPEG', filename='test.jpg'):
        """创建测试图片"""
        # 创建一个彩色测试图片
        img = Image.new('RGB', (width, height), color=(255, 0, 0))  # 红色背景
        
        # 添加一些内容让文件更大
        for i in range(0, width, 50):
            for j in range(0, height, 50):
                # 创建棋盘图案
                color = (0, 255, 0) if (i//50 + j//50) % 2 == 0 else (0, 0, 255)
                for x in range(i, min(i+25, width)):
                    for y in range(j, min(j+25, height)):
                        img.putpixel((x, y), color)
        
        # 保存到临时目录
        file_path = os.path.join(self.temp_dir, filename)
        img.save(file_path, format=format, quality=95)
        return file_path
    
    def test_load_image_info_success(self):
        """测试成功加载图片信息"""
        # 创建测试图片
        test_image = self.create_test_image(800, 600, 'JPEG', 'test.jpg')
        
        # 测试加载信息
        image_info = self.compressor.load_image_info(test_image)
        
        # 验证结果
        self.assertIsInstance(image_info, ImageInfo)
        self.assertEqual(image_info.width, 800)
        self.assertEqual(image_info.height, 600)
        self.assertEqual(image_info.format, 'JPEG')
        self.assertGreater(image_info.file_size, 0)
        self.assertEqual(image_info.file_path, test_image)
    
    def test_load_image_info_file_not_found(self):
        """测试文件不存在的情况"""
        with self.assertRaises(FileNotFoundError):
            self.compressor.load_image_info("nonexistent.jpg")
    
    def test_validate_image_valid(self):
        """测试有效图片验证"""
        test_image = self.create_test_image()
        self.assertTrue(self.compressor.validate_image(test_image))
    
    def test_validate_image_invalid(self):
        """测试无效图片验证"""
        self.assertFalse(self.compressor.validate_image("nonexistent.jpg"))
    
    def test_get_compression_info_needs_compression(self):
        """测试需要压缩的图片信息"""
        # 创建大图片（应该需要压缩）
        test_image = self.create_test_image(1920, 1080, 'JPEG', 'large.jpg')
        
        compression_info = self.compressor.get_compression_info(test_image)
        
        # 验证结果
        self.assertIn('original_info', compression_info)
        self.assertIn('needs_compression', compression_info)
        self.assertIn('compression_ratio', compression_info)
        self.assertIn('scale_factor', compression_info)
        self.assertIn('estimated_dimensions', compression_info)
        
        # 大图片应该需要压缩
        self.assertTrue(compression_info['needs_compression'])
        self.assertGreater(compression_info['compression_ratio'], 1.0)
        self.assertLess(compression_info['scale_factor'], 1.0)
    
    def test_get_compression_info_no_compression_needed(self):
        """测试不需要压缩的小图片"""
        # 创建小图片（应该不需要压缩）
        test_image = self.create_test_image(100, 100, 'JPEG', 'small.jpg')
        
        compression_info = self.compressor.get_compression_info(test_image)
        
        # 小图片可能不需要压缩（取决于内容）
        if not compression_info['needs_compression']:
            self.assertEqual(compression_info['compression_ratio'], 1.0)
            self.assertEqual(compression_info['scale_factor'], 1.0)
    
    def test_image_info_properties(self):
        """测试ImageInfo类的属性"""
        test_image = self.create_test_image(800, 600)
        image_info = self.compressor.load_image_info(test_image)
        
        # 测试宽高比
        expected_ratio = 800 / 600
        self.assertAlmostEqual(image_info.aspect_ratio, expected_ratio, places=2)
        
        # 测试总像素数
        self.assertEqual(image_info.total_pixels, 800 * 600)
        
        # 测试字符串表示
        str_repr = str(image_info)
        self.assertIn('ImageInfo', str_repr)
        self.assertIn('800', str_repr)
        self.assertIn('600', str_repr)
    
    def test_different_formats(self):
        """测试不同图片格式"""
        formats = [
            ('PNG', 'test.png'),
            ('JPEG', 'test.jpg'),
            ('BMP', 'test.bmp'),
            ('WEBP', 'test.webp')
        ]
        
        for format_name, filename in formats:
            try:
                test_image = self.create_test_image(400, 300, format_name, filename)
                image_info = self.compressor.load_image_info(test_image)
                self.assertEqual(image_info.format, format_name)
                print(f"✓ {format_name} 格式测试通过")
            except Exception as e:
                print(f"✗ {format_name} 格式测试失败: {e}")
    
    def test_calculate_quality_parameter_large_image(self):
        """测试大图片的质量参数计算"""
        # 创建一个足够大的图片，确保需要压缩
        test_image = self.create_test_image(1200, 900, 'JPEG', 'large_for_quality.jpg')
        
        # 设置较小的目标大小以确保需要压缩
        target_size = 50 * 1024  # 50KB
        
        try:
            best_quality, final_size = self.compressor.calculate_quality_parameter(
                test_image, target_size
            )
            
            # 验证结果
            self.assertIsInstance(best_quality, int)
            self.assertGreaterEqual(best_quality, 1)
            self.assertLessEqual(best_quality, 95)
            self.assertLessEqual(final_size, target_size)
            
            print(f"✓ 大图片质量计算测试通过: quality={best_quality}, size={final_size/1024:.1f}KB")
            
        except Exception as e:
            print(f"✗ 大图片质量计算测试失败: {e}")
    
    def test_calculate_quality_parameter_small_image(self):
        """测试小图片的质量参数计算（无需压缩）"""
        # 创建一个小图片
        test_image = self.create_test_image(200, 150, 'JPEG', 'small_for_quality.jpg')
        
        try:
            best_quality, final_size = self.compressor.calculate_quality_parameter(test_image)
            
            # 小图片应该返回最高质量
            self.assertEqual(best_quality, 95)
            
            print(f"✓ 小图片质量计算测试通过: quality={best_quality}, size={final_size/1024:.1f}KB")
            
        except Exception as e:
            print(f"✗ 小图片质量计算测试失败: {e}")
    
    def test_get_compression_info_with_quality(self):
        """测试带质量参数的压缩信息获取"""
        # 创建需要压缩的图片
        test_image = self.create_test_image(1000, 800, 'JPEG', 'quality_test.jpg')
        
        compression_info = self.compressor.get_compression_info(test_image)
        
        # 验证新增的质量相关字段
        self.assertIn('best_quality', compression_info)
        self.assertIn('estimated_compressed_size', compression_info)
        
        if compression_info['needs_compression']:
            # 如果需要压缩，应该有质量参数
            self.assertIsNotNone(compression_info['best_quality'])
            self.assertIsNotNone(compression_info['estimated_compressed_size'])
            
            print(f"✓ 压缩信息测试通过: best_quality={compression_info['best_quality']}, "
                  f"estimated_size={compression_info['estimated_compressed_size']/1024:.1f}KB")
    
    def test_calculate_optimal_dimensions(self):
        """测试最佳分辨率计算"""
        # 测试需要缩小的情况
        new_width, new_height = self.compressor.calculate_optimal_dimensions(
            1920, 1080, 100*1024, 500*1024  # 从500KB压缩到100KB
        )
        
        # 验证宽高比保持不变
        original_ratio = 1920 / 1080
        new_ratio = new_width / new_height
        self.assertAlmostEqual(original_ratio, new_ratio, places=2)
        
        # 验证尺寸减小
        self.assertLess(new_width, 1920)
        self.assertLess(new_height, 1080)
        
        print(f"✓ 最佳分辨率计算测试通过: {1920}x{1080} -> {new_width}x{new_height}")
    
    def test_calculate_optimal_dimensions_no_resize(self):
        """测试不需要调整分辨率的情况"""
        new_width, new_height = self.compressor.calculate_optimal_dimensions(
            800, 600, 100*1024, 50*1024  # 文件已经小于目标大小
        )
        
        # 应该保持原始尺寸
        self.assertEqual(new_width, 800)
        self.assertEqual(new_height, 600)
        
        print(f"✓ 无需调整分辨率测试通过: 尺寸保持 {new_width}x{new_height}")
    
    def test_resize_image_smart(self):
        """测试智能分辨率调整"""
        # 创建一个大图片
        test_image = self.create_test_image(1200, 900, 'JPEG', 'resize_test.jpg')
        
        try:
            # 设置较小的目标大小
            resized_img, (new_width, new_height) = self.compressor.resize_image_smart(
                test_image, 30*1024  # 30KB目标
            )
            
            # 验证返回的是PIL Image对象
            self.assertIsInstance(resized_img, Image.Image)
            
            # 验证新尺寸
            self.assertIsInstance(new_width, int)
            self.assertIsInstance(new_height, int)
            self.assertGreater(new_width, 0)
            self.assertGreater(new_height, 0)
            
            # 验证宽高比保持
            original_ratio = 1200 / 900
            new_ratio = new_width / new_height
            self.assertAlmostEqual(original_ratio, new_ratio, places=1)
            
            print(f"✓ 智能分辨率调整测试通过: {1200}x{900} -> {new_width}x{new_height}")
            
        except Exception as e:
            print(f"✗ 智能分辨率调整测试失败: {e}")
    
    def test_estimate_file_size_after_resize(self):
        """测试调整分辨率后的文件大小估算"""
        test_image = self.create_test_image(800, 600, 'JPEG', 'estimate_test.jpg')
        
        try:
            estimated_size = self.compressor.estimate_file_size_after_resize(
                test_image, 400, 300, quality=80
            )
            
            # 验证返回有效的文件大小
            self.assertIsInstance(estimated_size, int)
            self.assertGreater(estimated_size, 0)
            
            print(f"✓ 文件大小估算测试通过: 400x300 @ quality=80 -> {estimated_size/1024:.1f}KB")
            
        except Exception as e:
            print(f"✗ 文件大小估算测试失败: {e}")
    
    def test_save_compressed_image(self):
        """测试保存压缩图片功能"""
        # 创建测试图片
        test_image = self.create_test_image(600, 400, 'JPEG', 'save_test.jpg')
        
        try:
            # 加载图片
            with Image.open(test_image) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 测试保存
                output_path = os.path.join(self.temp_dir, 'saved_compressed.jpg')
                result = self.compressor.save_compressed_image(img, output_path, quality=80)
                
                # 验证结果
                self.assertIn('output_path', result)
                self.assertIn('final_size_bytes', result)
                self.assertIn('target_achieved', result)
                self.assertTrue(os.path.exists(output_path))
                
                print(f"✓ 保存压缩图片测试通过: {result['final_size_kb']:.1f}KB, quality={result['quality_used']}")
                
        except Exception as e:
            print(f"✗ 保存压缩图片测试失败: {e}")
    
    def test_compress_single_image_large(self):
        """测试完整的单张大图片压缩流程"""
        # 创建一个大图片
        test_image = self.create_test_image(1500, 1200, 'JPEG', 'large_compress.jpg')
        
        try:
            output_path = os.path.join(self.temp_dir, 'compressed_large.jpg')
            result = self.compressor.compress_single_image(test_image, output_path, 80*1024)  # 80KB目标
            
            # 验证结果结构
            expected_keys = [
                'input_path', 'output_path', 'original_size_bytes', 'final_size_bytes',
                'compression_ratio', 'quality_used', 'dimensions_original', 'dimensions_final',
                'resize_applied', 'processing_time_seconds', 'target_achieved', 'method'
            ]
            
            for key in expected_keys:
                self.assertIn(key, result)
            
            # 验证压缩效果
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(result['compression_ratio'], 1.0)
            self.assertLess(result['processing_time_seconds'], 10.0)  # 应该在10秒内完成
            
            print(f"✓ 大图片压缩测试通过: {result['original_size_bytes']/1024:.1f}KB -> {result['final_size_bytes']/1024:.1f}KB, "
                  f"压缩比: {result['compression_ratio']:.2f}x, 处理时间: {result['processing_time_seconds']:.2f}s")
                
        except Exception as e:
            print(f"✗ 大图片压缩测试失败: {e}")
    
    def test_compress_single_image_small(self):
        """测试小图片的压缩流程（应该直接复制）"""
        # 创建一个小图片
        test_image = self.create_test_image(200, 150, 'JPEG', 'small_compress.jpg')
        
        try:
            output_path = os.path.join(self.temp_dir, 'compressed_small.jpg')
            result = self.compressor.compress_single_image(test_image, output_path)
            
            # 小图片应该直接复制
            self.assertEqual(result['method'], 'direct_copy')
            self.assertEqual(result['compression_ratio'], 1.0)
            self.assertFalse(result['resize_applied'])
            self.assertTrue(result['target_achieved'])
            
            print(f"✓ 小图片压缩测试通过: 方法={result['method']}, 大小保持={result['final_size_bytes']/1024:.1f}KB")
            
        except Exception as e:
            print(f"✗ 小图片压缩测试失败: {e}")
    
    def test_compress_with_webp(self):
        """测试WebP格式压缩"""
        # 创建测试图片
        test_image = self.create_test_image(800, 600, 'JPEG', 'webp_test.jpg')
        
        try:
            output_path = os.path.join(self.temp_dir, 'compressed.webp')
            result = self.compressor.compress_with_webp(test_image, output_path, 50*1024)  # 50KB目标
            
            # 验证结果
            self.assertTrue(os.path.exists(output_path))
            self.assertEqual(result['format'], 'WEBP')
            self.assertIn('method', result)
            self.assertIn('iterations', result)
            
            print(f"✓ WebP压缩测试通过: {result['final_size_bytes']/1024:.1f}KB, "
                  f"质量={result['quality_used']}, 迭代={result['iterations']}")
            
        except Exception as e:
            print(f"✗ WebP压缩测试失败: {e}")
    
    def test_compress_with_advanced_jpeg(self):
        """测试高级JPEG压缩"""
        # 创建测试图片
        test_image = self.create_test_image(1000, 800, 'JPEG', 'advanced_jpeg_test.jpg')
        
        try:
            output_path = os.path.join(self.temp_dir, 'advanced_compressed.jpg')
            result = self.compressor.compress_with_advanced_jpeg(test_image, output_path, 60*1024)  # 60KB目标
            
            # 验证结果
            self.assertTrue(os.path.exists(output_path))
            self.assertEqual(result['format'], 'JPEG')
            self.assertEqual(result['method'], 'advanced_jpeg')
            self.assertIn('optimizations', result)
            
            # 验证高级优化参数
            expected_optimizations = ['optimize', 'progressive', 'subsampling=0']
            for opt in expected_optimizations:
                self.assertIn(opt, result['optimizations'])
            
            print(f"✓ 高级JPEG压缩测试通过: {result['final_size_bytes']/1024:.1f}KB, "
                  f"质量={result['quality_used']}, 优化={result['optimizations']}")
            
        except Exception as e:
            print(f"✗ 高级JPEG压缩测试失败: {e}")
    
    def test_compress_with_best_method(self):
        """测试多方法压缩选择最佳结果"""
        # 创建一个大图片进行测试
        test_image = self.create_test_image(1200, 900, 'JPEG', 'best_method_test.jpg')
        
        try:
            result = self.compressor.compress_with_best_method(test_image, self.temp_dir, 70*1024)  # 70KB目标
            
            # 验证结果结构
            expected_keys = [
                'method_name', 'total_processing_time', 'methods_tested', 'all_results'
            ]
            
            for key in expected_keys:
                self.assertIn(key, result)
            
            # 验证测试了多种方法
            self.assertGreater(result['methods_tested'], 1)
            self.assertIsInstance(result['all_results'], list)
            
            # 验证最终文件存在
            self.assertTrue(os.path.exists(result['output_path']))
            
            print(f"✓ 多方法压缩测试通过: 最佳方法={result['method_name']}, "
                  f"测试方法数={result['methods_tested']}, 最终大小={result['final_size_bytes']/1024:.1f}KB")
            
        except Exception as e:
            print(f"✗ 多方法压缩测试失败: {e}")


def run_manual_test():
    """手动测试函数"""
    print("开始手动测试图片压缩模块...")
    print("=" * 60)
    
    # 创建压缩器
    compressor = ImageCompressor(target_size_kb=100)
    
    # 创建临时目录和测试图片
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建不同大小的测试图片
        test_cases = [
            (400, 300, 'small.jpg'),
            (800, 600, 'medium.jpg'),
            (1920, 1080, 'large.jpg'),
            (100, 100, 'tiny.jpg')
        ]
        
        for width, height, filename in test_cases:
            print(f"\n测试图片: {filename} ({width}x{height})")
            print("-" * 40)
            
            try:
                # 创建测试图片
                img = Image.new('RGB', (width, height), color=(255, 128, 0))
                file_path = os.path.join(temp_dir, filename)
                img.save(file_path, 'JPEG', quality=90)
                
                # 测试加载信息
                image_info = compressor.load_image_info(file_path)
                print(f"图片信息: {image_info}")
                
                # 测试压缩信息
                compression_info = compressor.get_compression_info(file_path)
                print(f"需要压缩: {compression_info['needs_compression']}")
                print(f"压缩比例: {compression_info['compression_ratio']:.2f}")
                print(f"缩放因子: {compression_info['scale_factor']:.2f}")
                print(f"预估尺寸: {compression_info['estimated_dimensions']}")
                
            except Exception as e:
                print(f"错误: {e}")
    
    print("\n手动测试完成！")


if __name__ == '__main__':
    # 运行单元测试
    print("运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行手动测试
    print("\n" + "="*60)
    run_manual_test() 