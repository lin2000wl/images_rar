#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件扫描器单元测试
测试file_scanner模块的各项功能
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import shutil

from file_scanner import ImageScanner


class TestImageScanner(unittest.TestCase):
    """ImageScanner类的单元测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.scanner = ImageScanner(min_size_kb=100)
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后的清理工作"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_test_file(self, filename: str, size_bytes: int = 0) -> Path:
        """创建测试文件"""
        file_path = Path(self.temp_dir) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建指定大小的文件
        with open(file_path, 'wb') as f:
            f.write(b'0' * size_bytes)
        
        return file_path
    
    def test_init(self):
        """测试初始化"""
        scanner = ImageScanner(min_size_kb=50)
        self.assertEqual(scanner.min_size_bytes, 50 * 1024)
        
        # 测试默认值
        default_scanner = ImageScanner()
        self.assertEqual(default_scanner.min_size_bytes, 100 * 1024)
    
    def test_supported_formats(self):
        """测试支持的格式"""
        expected_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        self.assertEqual(ImageScanner.get_supported_formats(), expected_formats)
    
    def test_is_supported_image(self):
        """测试图片格式检查"""
        # 测试支持的格式
        supported_files = [
            'test.jpg', 'test.jpeg', 'test.png', 'test.gif', 
            'test.bmp', 'test.webp', 'TEST.JPG', 'Test.PNG'
        ]
        
        for filename in supported_files:
            file_path = Path(filename)
            self.assertTrue(
                self.scanner.is_supported_image(file_path),
                f"{filename} should be supported"
            )
        
        # 测试不支持的格式
        unsupported_files = [
            'test.txt', 'test.doc', 'test.pdf', 'test.mp4', 
            'test.zip', 'test', 'test.'
        ]
        
        for filename in unsupported_files:
            file_path = Path(filename)
            self.assertFalse(
                self.scanner.is_supported_image(file_path),
                f"{filename} should not be supported"
            )
    
    def test_check_file_size(self):
        """测试文件大小检查"""
        # 创建大于阈值的文件 (150KB)
        large_file = self.create_test_file('large.jpg', 150 * 1024)
        self.assertTrue(self.scanner.check_file_size(large_file))
        
        # 创建小于阈值的文件 (50KB)
        small_file = self.create_test_file('small.jpg', 50 * 1024)
        self.assertFalse(self.scanner.check_file_size(small_file))
        
        # 创建等于阈值的文件 (100KB)
        equal_file = self.create_test_file('equal.jpg', 100 * 1024)
        self.assertFalse(self.scanner.check_file_size(equal_file))  # 应该是大于，不是大于等于
    
    def test_check_file_size_nonexistent_file(self):
        """测试检查不存在文件的大小"""
        nonexistent_file = Path(self.temp_dir) / 'nonexistent.jpg'
        result = self.scanner.check_file_size(nonexistent_file)
        self.assertFalse(result)  # 不存在的文件应该返回False
    
    def test_scan_directory_basic(self):
        """测试基本目录扫描"""
        # 创建测试文件结构
        self.create_test_file('file1.txt', 1024)
        self.create_test_file('subdir/file2.jpg', 2048)
        self.create_test_file('subdir/nested/file3.png', 3072)
        
        files = list(self.scanner.scan_directory(self.temp_dir))
        
        # 应该找到3个文件
        self.assertEqual(len(files), 3)
        
        # 检查文件路径
        filenames = [f.name for f in files]
        self.assertIn('file1.txt', filenames)
        self.assertIn('file2.jpg', filenames)
        self.assertIn('file3.png', filenames)
    
    def test_scan_directory_empty(self):
        """测试空目录扫描"""
        empty_dir = Path(self.temp_dir) / 'empty'
        empty_dir.mkdir()
        
        files = list(self.scanner.scan_directory(str(empty_dir)))
        self.assertEqual(len(files), 0)
    
    def test_scan_directory_nonexistent(self):
        """测试扫描不存在的目录"""
        nonexistent_dir = self.temp_dir + '_nonexistent'
        
        with self.assertRaises(FileNotFoundError):
            list(self.scanner.scan_directory(nonexistent_dir))
    
    def test_scan_directory_not_directory(self):
        """测试扫描非目录路径"""
        file_path = self.create_test_file('notdir.txt', 1024)
        
        with self.assertRaises(ValueError):
            list(self.scanner.scan_directory(str(file_path)))
    
    def test_scan_images(self):
        """测试图片扫描功能"""
        # 创建测试文件
        self.create_test_file('large.jpg', 150 * 1024)  # 符合条件
        self.create_test_file('small.jpg', 50 * 1024)   # 太小
        self.create_test_file('large.txt', 150 * 1024)  # 非图片
        self.create_test_file('small.png', 50 * 1024)   # 太小
        self.create_test_file('subdir/large.gif', 200 * 1024)  # 符合条件
        
        images = self.scanner.scan_images(self.temp_dir)
        
        # 应该只找到2个符合条件的图片
        self.assertEqual(len(images), 2)
        
        image_names = [img.name for img in images]
        self.assertIn('large.jpg', image_names)
        self.assertIn('large.gif', image_names)
        self.assertNotIn('small.jpg', image_names)
        self.assertNotIn('large.txt', image_names)
        self.assertNotIn('small.png', image_names)
    
    def test_get_scan_summary(self):
        """测试扫描摘要功能"""
        # 创建测试文件
        self.create_test_file('test1.jpg', 150 * 1024)
        self.create_test_file('test2.png', 120 * 1024)
        self.create_test_file('test3.gif', 110 * 1024)
        self.create_test_file('small.jpg', 50 * 1024)  # 太小，不计入
        
        total, valid, formats = self.scanner.get_scan_summary(self.temp_dir)
        
        self.assertEqual(total, 3)  # 符合条件的图片数
        self.assertEqual(valid, 3)  # 符合条件的图片数
        self.assertEqual(len(formats), 3)  # 3种格式
        
        # 检查格式统计
        format_str = ', '.join(formats)
        self.assertIn('.jpg: 1', format_str)
        self.assertIn('.png: 1', format_str)
        self.assertIn('.gif: 1', format_str)
    
    def test_set_size_threshold(self):
        """测试设置大小阈值"""
        self.scanner.set_size_threshold(200)
        self.assertEqual(self.scanner.min_size_bytes, 200 * 1024)
        
        # 测试无效阈值
        with self.assertRaises(ValueError):
            self.scanner.set_size_threshold(0)
        
        with self.assertRaises(ValueError):
            self.scanner.set_size_threshold(-10)
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 空目录
        empty_dir = Path(self.temp_dir) / 'empty'
        empty_dir.mkdir()
        
        images = self.scanner.scan_images(str(empty_dir))
        self.assertEqual(len(images), 0)
        
        # 只有非图片文件
        text_only_dir = Path(self.temp_dir) / 'text_only'
        text_only_dir.mkdir()
        (text_only_dir / 'file1.txt').write_text('content')
        (text_only_dir / 'file2.doc').write_text('content')
        
        images = self.scanner.scan_images(str(text_only_dir))
        self.assertEqual(len(images), 0)
        
        # 只有小图片文件
        small_images_dir = Path(self.temp_dir) / 'small_images'
        small_images_dir.mkdir()
        self.create_test_file('small_images/tiny1.jpg', 1024)  # 1KB
        self.create_test_file('small_images/tiny2.png', 2048)  # 2KB
        
        images = self.scanner.scan_images(str(small_images_dir))
        self.assertEqual(len(images), 0)
    
    def test_permission_error_handling(self):
        """测试权限错误处理"""
        # 测试文件不存在的情况（这会触发OSError处理逻辑）
        nonexistent_file = Path(self.temp_dir) / 'nonexistent.jpg'
        result = self.scanner.check_file_size(nonexistent_file)
        self.assertFalse(result)  # OSError时应该返回False
        
        # 这个测试验证了异常处理机制确实在工作


class TestImageScannerIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.scanner = ImageScanner(min_size_kb=100)
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_complex_structure(self):
        """创建复杂的测试目录结构"""
        base = Path(self.temp_dir)
        
        # 创建多层嵌套结构
        dirs = [
            'level1',
            'level1/level2a',
            'level1/level2b',
            'level1/level2a/level3',
            'other'
        ]
        
        for dir_path in dirs:
            (base / dir_path).mkdir(parents=True, exist_ok=True)
        
        # 创建各种文件
        files = [
            ('image1.jpg', 150 * 1024, True),      # 符合条件
            ('image2.png', 50 * 1024, False),     # 太小
            ('document.txt', 200 * 1024, False),  # 非图片
            ('level1/image3.gif', 120 * 1024, True),  # 符合条件
            ('level1/level2a/image4.bmp', 180 * 1024, True),  # 符合条件
            ('level1/level2a/level3/image5.webp', 90 * 1024, False),  # 太小
            ('level1/level2b/image6.jpeg', 250 * 1024, True),  # 符合条件
            ('other/mixed.jpg', 30 * 1024, False),  # 太小
        ]
        
        expected_valid = 0
        for filename, size, should_be_valid in files:
            file_path = base / filename
            with open(file_path, 'wb') as f:
                f.write(b'0' * size)
            if should_be_valid:
                expected_valid += 1
        
        return expected_valid
    
    def test_complex_directory_scan(self):
        """测试复杂目录结构扫描"""
        expected_count = self.create_complex_structure()
        
        images = self.scanner.scan_images(self.temp_dir)
        
        # 验证结果数量
        self.assertEqual(len(images), expected_count)
        
        # 验证所有找到的文件都符合条件
        for image_path in images:
            # 检查格式
            self.assertTrue(self.scanner.is_supported_image(image_path))
            # 检查大小
            self.assertTrue(self.scanner.check_file_size(image_path))


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestImageScanner))
    suite.addTests(loader.loadTestsFromTestCase(TestImageScannerIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == '__main__':
    print("运行文件扫描器单元测试...")
    success = run_tests()
    
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败！")
        exit(1) 