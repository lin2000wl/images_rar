#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片压缩工具主程序
使用PyQt5构建GUI界面
"""

import sys
import os
import shutil
import tempfile
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                           QMenuBar, QStatusBar, QAction, QMessageBox, QFileDialog,
                           QRadioButton, QButtonGroup, QGroupBox, QProgressDialog,
                           QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QIcon, QFont
from file_scanner import ImageScanner
from image_compressor import ImageCompressor


class CompressionWorker(QThread):
    """压缩工作线程"""
    
    # 信号定义
    progress_updated = Signal(int, str)  # 进度百分比，当前文件名
    compression_finished = Signal(dict)  # 压缩完成，结果字典
    error_occurred = Signal(str)  # 发生错误
    
    def __init__(self, image_files, output_mode, compressor):
        super().__init__()
        self.image_files = image_files
        self.output_mode = output_mode  # "replace" or "create_new"
        self.compressor = compressor
        self.results = {
            'total_files': len(image_files),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'details': []
        }
        
    def run(self):
        """执行压缩任务"""
        try:
            total_files = len(self.image_files)
            
            for index, image_path in enumerate(self.image_files):
                if self.isInterruptionRequested():
                    break
                    
                # 更新进度
                progress = int((index / total_files) * 100)
                file_name = Path(image_path).name
                self.progress_updated.emit(progress, file_name)
                
                try:
                    if self.output_mode == "replace":
                        success = self._compress_replace_original(image_path)
                    else:  # create_new
                        success = self._compress_create_new(image_path)
                    
                    if success:
                        self.results['successful'] += 1
                    else:
                        self.results['failed'] += 1
                        
                except Exception as e:
                    self.results['failed'] += 1
                    error_msg = f"{file_name}: {str(e)}"
                    self.results['errors'].append(error_msg)
            
            # 完成进度
            self.progress_updated.emit(100, "压缩完成")
            self.compression_finished.emit(self.results)
            
        except Exception as e:
            self.error_occurred.emit(f"压缩过程中发生严重错误: {str(e)}")
    
    def _compress_replace_original(self, image_path):
        """替换原图模式的压缩"""
        try:
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_name = f"compressed_{Path(image_path).stem}_{os.getpid()}.jpg"
            temp_path = os.path.join(temp_dir, temp_name)
            
            # 压缩到临时文件
            result = self.compressor.compress_single_image(image_path, temp_path)
            
            # 创建备份（以防万一）
            backup_path = image_path + ".backup"
            shutil.copy2(image_path, backup_path)
            
            try:
                # 替换原文件
                shutil.move(temp_path, image_path)
                
                # 删除备份
                os.remove(backup_path)
                
                # 记录详情
                self.results['details'].append({
                    'file': image_path,
                    'mode': 'replace',
                    'original_size': result['original_size_bytes'],
                    'final_size': result['final_size_bytes'],
                    'compression_ratio': result['compression_ratio']
                })
                
                return True
                
            except Exception as e:
                # 恢复备份
                if os.path.exists(backup_path):
                    shutil.move(backup_path, image_path)
                raise e
                
        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise e
    
    def _compress_create_new(self, image_path):
        """生成新文件模式的压缩"""
        try:
            # 生成新文件名
            path_obj = Path(image_path)
            new_name = f"{path_obj.stem}_compressed{path_obj.suffix}"
            new_path = path_obj.parent / new_name
            
            # 如果新文件已存在，添加数字后缀
            counter = 1
            while new_path.exists():
                new_name = f"{path_obj.stem}_compressed_{counter}{path_obj.suffix}"
                new_path = path_obj.parent / new_name
                counter += 1
            
            # 压缩到新文件
            result = self.compressor.compress_single_image(image_path, str(new_path))
            
            # 记录详情
            self.results['details'].append({
                'file': image_path,
                'new_file': str(new_path),
                'mode': 'create_new',
                'original_size': result['original_size_bytes'],
                'final_size': result['final_size_bytes'],
                'compression_ratio': result['compression_ratio']
            })
            
            return True
            
        except Exception as e:
            raise e


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        # 初始化实例变量
        self.selected_folder = None
        self.image_scanner = ImageScanner(min_size_kb=100)
        self.image_compressor = ImageCompressor(target_size_kb=100)
        self.image_files = []
        
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        # 设置窗口基本属性
        self.setWindowTitle("图片压缩工具 v1.0")
        self.setGeometry(300, 300, 800, 600)
        self.setMinimumSize(600, 400)
        
        # 设置窗口图标（如果有的话）
        # self.setWindowIcon(QIcon('icon.ico'))
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 添加标题
        title_label = QLabel("图片批量压缩工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("QLabel { color: #2c3e50; margin: 10px 0; }")
        main_layout.addWidget(title_label)
        
        # 添加描述
        desc_label = QLabel("选择包含图片的文件夹，一键批量压缩至100KB以内")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("QLabel { color: #7f8c8d; margin-bottom: 20px; }")
        main_layout.addWidget(desc_label)
        
        # 创建按钮区域
        button_widget = QWidget()
        button_layout = QGridLayout(button_widget)
        button_layout.setSpacing(15)
        
        # 选择文件夹按钮
        self.select_folder_btn = QPushButton("选择文件夹")
        self.select_folder_btn.setMinimumHeight(50)
        self.select_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        button_layout.addWidget(self.select_folder_btn, 0, 0)
        
        # 开始压缩按钮
        self.compress_btn = QPushButton("开始压缩")
        self.compress_btn.setMinimumHeight(50)
        self.compress_btn.setEnabled(False)  # 初始状态禁用
        self.compress_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover:enabled {
                background-color: #229954;
            }
            QPushButton:pressed:enabled {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        button_layout.addWidget(self.compress_btn, 0, 1)
        
        main_layout.addWidget(button_widget)
        
        # 添加输出选项单选按钮组
        self.create_output_options()
        main_layout.addWidget(self.output_options_group)
        
        # 添加进度显示区域
        self.create_progress_area()
        main_layout.addWidget(self.progress_widget)
        
        # 添加状态显示区域
        self.status_label = QLabel("请选择包含图片的文件夹")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 15px;
                color: #2c3e50;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.status_label)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        # 连接信号和槽
        self.connect_signals()
        
        # 初始化菜单栏和状态栏
        self.init_menu_bar()
        self.init_status_bar()
        
    def create_progress_area(self):
        """创建进度显示区域"""
        # 创建进度显示容器
        self.progress_widget = QWidget()
        self.progress_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                margin: 5px 0px;
            }
        """)
        
        # 创建布局
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(15, 10, 15, 10)
        progress_layout.setSpacing(8)
        
        # 进度文本标签
        self.progress_text_label = QLabel("就绪")
        self.progress_text_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #495057;
                background: none;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        self.progress_text_label.setAlignment(Qt.AlignCenter)
        
        # 进度条
        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setMinimum(0)
        self.main_progress_bar.setMaximum(100)
        self.main_progress_bar.setValue(0)
        self.main_progress_bar.setTextVisible(True)
        self.main_progress_bar.setFormat("%p%")
        
        # 设置进度条样式
        self.main_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background-color: #ffffff;
                text-align: center;
                font-size: 12px;
                font-weight: bold;
                color: #495057;
                height: 25px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #28a745, stop:1 #20c997);
                border-radius: 6px;
                margin: 2px;
            }
            QProgressBar[error="true"] {
                border-color: #dc3545;
            }
            QProgressBar[error="true"]::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #dc3545, stop:1 #c82333);
            }
        """)
        
        # 添加到布局
        progress_layout.addWidget(self.progress_text_label)
        progress_layout.addWidget(self.main_progress_bar)
        
        self.progress_widget.setLayout(progress_layout)
        
        # 初始状态下隐藏进度区域
        self.progress_widget.setVisible(False)
        
    def create_output_options(self):
        """创建输出选项单选按钮组"""
        # 创建分组框
        self.output_options_group = QGroupBox("输出选项")
        self.output_options_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
            }
        """)
        
        # 创建布局
        options_layout = QVBoxLayout(self.output_options_group)
        options_layout.setSpacing(10)
        options_layout.setContentsMargins(20, 20, 20, 15)
        
        # 创建按钮组（确保只能选择一个）
        self.output_button_group = QButtonGroup()
        
        # 创建"替换原图"单选按钮（默认选中）
        self.replace_original_radio = QRadioButton("替换原图（覆盖原始文件）")
        self.replace_original_radio.setChecked(True)  # 默认选中
        self.replace_original_radio.setStyleSheet("""
            QRadioButton {
                font-size: 12px;
                color: #2c3e50;
                padding: 5px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator::unchecked {
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
            }
            QRadioButton::indicator::checked {
                border: 2px solid #3498db;
                border-radius: 8px;
                background-color: #3498db;
            }
        """)
        
        # 创建"生成新文件"单选按钮
        self.create_new_radio = QRadioButton("生成新文件（保留原始文件，创建压缩版本）")
        self.create_new_radio.setStyleSheet("""
            QRadioButton {
                font-size: 12px;
                color: #2c3e50;
                padding: 5px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator::unchecked {
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
            }
            QRadioButton::indicator::checked {
                border: 2px solid #27ae60;
                border-radius: 8px;
                background-color: #27ae60;
            }
        """)
        
        # 将单选按钮添加到按钮组
        self.output_button_group.addButton(self.replace_original_radio, 0)
        self.output_button_group.addButton(self.create_new_radio, 1)
        
        # 将单选按钮添加到布局
        options_layout.addWidget(self.replace_original_radio)
        options_layout.addWidget(self.create_new_radio)
        
        # 连接信号（可选：用于响应选择变化）
        self.output_button_group.buttonToggled.connect(self.on_output_option_changed)
        
    def on_output_option_changed(self, button, checked):
        """输出选项改变时的回调函数"""
        if checked:
            if button == self.replace_original_radio:
                self.statusBar().showMessage('已选择：替换原图模式')
            elif button == self.create_new_radio:
                self.statusBar().showMessage('已选择：生成新文件模式')
                
    def get_output_mode(self):
        """获取当前选择的输出模式"""
        if self.replace_original_radio.isChecked():
            return "replace"
        elif self.create_new_radio.isChecked():
            return "create_new"
        else:
            return "replace"  # 默认值
        
    def init_menu_bar(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')
        
        # 选择文件夹动作
        select_action = QAction('选择文件夹(&O)', self)
        select_action.setShortcut('Ctrl+O')
        select_action.setStatusTip('选择包含图片的文件夹')
        select_action.triggered.connect(self.select_folder_clicked)
        file_menu.addAction(select_action)
        
        # 重置状态动作
        reset_action = QAction('重置状态(&R)', self)
        reset_action.setShortcut('Ctrl+R')
        reset_action.setStatusTip('重置应用程序状态')
        reset_action.triggered.connect(self.reset_gui_state)
        file_menu.addAction(reset_action)
        
        file_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction('退出(&Q)', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('退出应用程序')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')
        
        # 关于动作
        about_action = QAction('关于(&A)', self)
        about_action.setStatusTip('关于图片压缩工具')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def init_status_bar(self):
        """初始化状态栏"""
        self.statusBar().showMessage('就绪')
        
    def connect_signals(self):
        """连接信号和槽"""
        self.select_folder_btn.clicked.connect(self.select_folder_clicked)
        self.compress_btn.clicked.connect(self.compress_clicked)
        
    def select_folder_clicked(self):
        """选择文件夹按钮点击事件"""
        try:
            # 设置默认路径为用户文档目录
            default_path = str(Path.home() / "Documents")
            
            # 如果之前有选择过文件夹，使用上次的路径
            if self.selected_folder:
                default_path = self.selected_folder
            
            # 打开文件夹选择对话框
            selected_directory = QFileDialog.getExistingDirectory(
                self,  # 父窗口
                "选择包含图片的文件夹",  # 对话框标题
                default_path,  # 默认路径
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks  # 选项
            )
            
            # 检查用户是否选择了文件夹
            if selected_directory:
                self.selected_folder = selected_directory
                self.statusBar().showMessage('正在扫描文件夹...')
                self.status_label.setText("正在扫描文件夹，请稍候...")
                
                # 强制刷新GUI
                QApplication.processEvents()
                
                # 扫描文件夹中的图片
                try:
                    self.image_files = self.image_scanner.scan_images(selected_directory)
                    image_count = len(self.image_files)
                    
                    # 更新GUI显示
                    folder_name = Path(selected_directory).name
                    self.status_label.setText(f"已选择文件夹：{folder_name} - 发现 {image_count} 张符合条件的图片")
                    
                    # 根据是否找到图片来启用/禁用压缩按钮
                    if image_count > 0:
                        self.compress_btn.setEnabled(True)
                        self.statusBar().showMessage(f'找到 {image_count} 张图片，可以开始压缩')
                        
                        # 显示详细的扫描结果
                        self.show_scan_results(selected_directory, image_count)
                    else:
                        self.compress_btn.setEnabled(False)
                        self.statusBar().showMessage('该文件夹中没有找到符合条件的图片')
                        QMessageBox.information(
                            self, 
                            '扫描结果', 
                            '该文件夹中没有找到符合条件的图片文件。\n\n'
                            '支持的格式：JPG、PNG、GIF、BMP、WEBP\n'
                            '文件大小：大于100KB\n\n'
                            '提示：请选择包含较大图片文件的文件夹。'
                        )
                
                except PermissionError:
                    self.reset_gui_state()
                    self.statusBar().showMessage('无法访问选择的文件夹')
                    QMessageBox.warning(
                        self,
                        '权限错误',
                        f'无法访问选择的文件夹：\n{selected_directory}\n\n'
                        '请选择有访问权限的文件夹。\n\n'
                        '建议：\n'
                        '• 选择您的文档、图片或桌面文件夹\n'
                        '• 避免选择系统文件夹或受保护的目录'
                    )
                
                except Exception as e:
                    self.reset_gui_state()
                    self.statusBar().showMessage('扫描文件夹时发生错误')
                    QMessageBox.critical(
                        self,
                        '扫描错误',
                        f'扫描文件夹时发生错误：\n{str(e)}\n\n'
                        '请尝试：\n'
                        '• 选择其他文件夹\n'
                        '• 确保文件夹路径有效\n'
                        '• 检查文件夹是否包含可访问的文件'
                    )
            
            else:
                # 用户取消了选择
                self.statusBar().showMessage('已取消文件夹选择')
                
        except Exception as e:
            self.statusBar().showMessage('打开文件夹选择对话框时发生错误')
            QMessageBox.critical(
                self,
                '错误',
                f'打开文件夹选择对话框时发生错误：\n{str(e)}'
            )
        
    def show_scan_results(self, folder_path: str, image_count: int):
        """显示扫描结果详情"""
        try:
            # 获取扫描摘要信息
            total_images, valid_images, format_summary = self.image_scanner.get_scan_summary(folder_path)
            
            # 构建结果消息
            folder_name = Path(folder_path).name
            result_msg = f"文件夹：{folder_name}\n"
            result_msg += f"发现 {image_count} 张符合条件的图片\n\n"
            
            if format_summary:
                result_msg += "格式分布：\n"
                for format_info in format_summary:
                    result_msg += f"  • {format_info}\n"
            
            result_msg += f"\n所有图片均大于100KB，可以进行压缩处理。"
            
            # 显示结果对话框
            QMessageBox.information(self, '扫描完成', result_msg)
            
        except Exception as e:
            # 如果获取详细信息失败，只显示基本信息
            QMessageBox.information(
                self, 
                '扫描完成', 
                f'发现 {image_count} 张符合条件的图片，可以开始压缩。'
            )
    
    def reset_gui_state(self):
        """重置GUI到初始状态"""
        self.selected_folder = None
        self.image_files = []
        self.status_label.setText("请选择包含图片的文件夹")
        self.compress_btn.setEnabled(False)
        self.statusBar().showMessage('就绪')

    def compress_clicked(self):
        """开始压缩按钮点击事件"""
        try:
            # 检查是否有选择的图片文件
            if not self.image_files:
                QMessageBox.warning(self, '警告', '请先选择包含图片的文件夹')
                return
            
            # 获取用户选择的输出模式
            output_mode = self.get_output_mode()
            
            # 确认对话框
            mode_text = "替换原图" if output_mode == "replace" else "生成新文件"
            file_count = len(self.image_files)
            
            reply = QMessageBox.question(
                self, 
                '确认压缩',
                f'即将压缩 {file_count} 张图片\n'
                f'输出模式：{mode_text}\n'
                f'目标大小：100KB以内\n\n'
                f'确定要开始压缩吗？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 特殊警告：替换原图模式
            if output_mode == "replace":
                warning_reply = QMessageBox.warning(
                    self,
                    '重要警告',
                    '⚠️ 替换原图模式将会覆盖您的原始图片文件！\n\n'
                    '为了您的数据安全，建议：\n'
                    '• 确保您已备份重要图片\n'
                    '• 或者选择"生成新文件"模式\n\n'
                    '确定要继续替换原图吗？',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if warning_reply != QMessageBox.Yes:
                    return
            
            # 开始压缩
            self.start_compression(output_mode)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'启动压缩时发生错误：\n{str(e)}')
    
    def start_compression(self, output_mode):
        """启动压缩过程"""
        try:
            # 禁用相关按钮
            self.compress_btn.setEnabled(False)
            self.select_folder_btn.setEnabled(False)
            
            # 显示并初始化主界面进度区域
            self.progress_widget.setVisible(True)
            self.main_progress_bar.setValue(0)
            self.main_progress_bar.setProperty("error", False)
            self.main_progress_bar.setStyleSheet(self.main_progress_bar.styleSheet())  # 刷新样式
            self.progress_text_label.setText("准备压缩...")
            
            # 创建进度对话框
            self.progress_dialog = QProgressDialog("准备压缩...", "取消", 0, 100, self)
            self.progress_dialog.setWindowTitle("压缩进度")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.show()
            
            # 创建工作线程
            self.compression_worker = CompressionWorker(
                self.image_files, 
                output_mode, 
                self.image_compressor
            )
            
            # 连接信号
            self.compression_worker.progress_updated.connect(self.on_compression_progress)
            self.compression_worker.compression_finished.connect(self.on_compression_finished)
            self.compression_worker.error_occurred.connect(self.on_compression_error)
            self.progress_dialog.canceled.connect(self.on_compression_canceled)
            
            # 启动线程
            self.compression_worker.start()
            
        except Exception as e:
            self.reset_compression_ui()
            QMessageBox.critical(self, '错误', f'启动压缩线程时发生错误：\n{str(e)}')
    
    def on_compression_progress(self, progress, current_file):
        """压缩进度更新"""
        # 更新弹窗进度条
        self.progress_dialog.setValue(progress)
        self.progress_dialog.setLabelText(f"正在压缩: {current_file}")
        
        # 更新主界面进度条
        self.main_progress_bar.setValue(progress)
        
        # 更新进度文本（显示文件名和进度）
        if hasattr(self, 'compression_worker') and self.compression_worker:
            total_files = len(self.compression_worker.image_files)
            # 更精确的当前文件索引计算
            if progress >= 100:
                current_index = total_files
            else:
                current_index = max(1, int((progress / 100) * total_files) + 1)
            self.progress_text_label.setText(f"正在压缩: {current_file} ({current_index}/{total_files})")
        else:
            self.progress_text_label.setText(f"正在压缩: {current_file}")
        
        # 更新状态栏
        self.statusBar().showMessage(f'压缩进度: {progress}% - {current_file}')
    
    def on_compression_finished(self, results):
        """压缩完成处理"""
        self.progress_dialog.close()
        
        # 更新主界面进度条为完成状态
        total = results['total_files']
        successful = results['successful']
        failed = results['failed']
        
        # 设置进度条为100%
        self.main_progress_bar.setValue(100)
        
        # 根据结果设置不同的状态文本和颜色
        if failed == 0:
            # 全部成功
            self.progress_text_label.setText(f"压缩完成：成功 {successful} 张")
            self.main_progress_bar.setProperty("error", False)
        elif successful > 0:
            # 部分成功
            self.progress_text_label.setText(f"压缩完成：成功 {successful} 张，失败 {failed} 张")
            self.main_progress_bar.setProperty("error", False)
        else:
            # 全部失败
            self.progress_text_label.setText(f"压缩失败：失败 {failed} 张")
            self.main_progress_bar.setProperty("error", True)
        
        # 刷新进度条样式
        self.main_progress_bar.setStyleSheet(self.main_progress_bar.styleSheet())
        
        self.reset_compression_ui()
        
        # 显示结果
        
        # 构建结果消息
        result_msg = f"压缩完成！\n\n"
        result_msg += f"总计文件：{total} 张\n"
        result_msg += f"成功压缩：{successful} 张\n"
        result_msg += f"失败：{failed} 张\n"
        
        if results['details']:
            total_original = sum(d['original_size'] for d in results['details'])
            total_final = sum(d['final_size'] for d in results['details'])
            if total_original > 0:
                overall_ratio = total_original / total_final
                saved_space = (total_original - total_final) / (1024 * 1024)  # MB
                result_msg += f"\n总压缩比：{overall_ratio:.2f}x\n"
                result_msg += f"节省空间：{saved_space:.1f} MB"
        
        if results['errors']:
            result_msg += f"\n\n错误详情：\n"
            for error in results['errors'][:5]:  # 最多显示5个错误
                result_msg += f"• {error}\n"
            if len(results['errors']) > 5:
                result_msg += f"... 还有 {len(results['errors']) - 5} 个错误"
        
        # 根据结果选择消息框类型
        if failed == 0:
            QMessageBox.information(self, '压缩成功', result_msg)
        elif successful > 0:
            QMessageBox.warning(self, '部分成功', result_msg)
        else:
            QMessageBox.critical(self, '压缩失败', result_msg)
        
        self.statusBar().showMessage(f'压缩完成：成功 {successful}/{total}')
    
    def on_compression_error(self, error_message):
        """压缩错误处理"""
        self.progress_dialog.close()
        
        # 设置主界面进度条为错误状态
        self.progress_text_label.setText("压缩发生错误")
        self.main_progress_bar.setProperty("error", True)
        self.main_progress_bar.setStyleSheet(self.main_progress_bar.styleSheet())
        
        self.reset_compression_ui()
        QMessageBox.critical(self, '压缩错误', error_message)
        self.statusBar().showMessage('压缩失败')
    
    def on_compression_canceled(self):
        """用户取消压缩"""
        if hasattr(self, 'compression_worker') and self.compression_worker.isRunning():
            self.compression_worker.requestInterruption()
            self.compression_worker.wait(3000)  # 等待3秒
        
        # 更新主界面进度条为取消状态
        self.progress_text_label.setText("压缩已取消")
        self.main_progress_bar.setValue(0)
        self.main_progress_bar.setProperty("error", False)
        self.main_progress_bar.setStyleSheet(self.main_progress_bar.styleSheet())
        
        self.reset_compression_ui()
        self.statusBar().showMessage('压缩已取消')
    
    def reset_compression_ui(self):
        """重置压缩相关的UI状态"""
        self.compress_btn.setEnabled(True)
        self.select_folder_btn.setEnabled(True)
        
        # 5秒后隐藏进度区域（让用户能看到最终结果）
        from PyQt5.QtCore import QTimer
        if not hasattr(self, 'hide_progress_timer'):
            self.hide_progress_timer = QTimer()
            self.hide_progress_timer.setSingleShot(True)
            self.hide_progress_timer.timeout.connect(self.hide_progress_area)
        
        self.hide_progress_timer.start(5000)  # 5秒后隐藏
    
    def hide_progress_area(self):
        """隐藏进度区域并重置状态"""
        self.progress_widget.setVisible(False)
        self.progress_text_label.setText("就绪")
        self.main_progress_bar.setValue(0)
        self.main_progress_bar.setProperty("error", False)
        self.main_progress_bar.setStyleSheet(self.main_progress_bar.styleSheet())
        
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, '关于图片压缩工具', 
                         '图片压缩工具 v1.0\n\n'
                         '批量压缩图片至100KB以内\n'
                         '支持JPG、PNG、GIF、BMP、WEBP格式\n\n'
                         '开发中...')
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        reply = QMessageBox.question(self, '确认退出', 
                                   '确定要退出图片压缩工具吗？',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("图片压缩工具")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("ImageCompressor")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == '__main__':
    main() 