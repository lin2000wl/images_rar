#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片压缩工具主程序
使用PyQt5构建GUI界面
"""

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                           QMenuBar, QStatusBar, QAction, QMessageBox, QFileDialog,
                           QRadioButton, QButtonGroup, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont
from file_scanner import ImageScanner


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        # 初始化实例变量
        self.selected_folder = None
        self.image_scanner = ImageScanner(min_size_kb=100)
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
        """开始压缩按钮点击事件（占位逻辑）"""
        self.statusBar().showMessage('压缩功能待实现...')
        QMessageBox.information(self, '信息', '图片压缩功能将在后续任务中实现')
        
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