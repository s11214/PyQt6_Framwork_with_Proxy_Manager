import PyInstaller.__main__
import os
import shutil
from datetime import datetime

def clean_dist():
    """清理之前的构建文件"""
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')

def build():
    """构建应用程序"""
    # 清理旧文件
    clean_dist()
    
    # 获取版本号（使用日期作为版本号）
    version = datetime.now().strftime("%Y.%m.%d")
    
    # PyInstaller 参数
    params = [
        'main.py',                          # 主程序文件
        '--name=TestAlive',                 # 程序名称
        '--icon=icon.ico',                  # 使用图标
        '--windowed',                       # 使用 GUI 模式
        '--noconfirm',                      # 覆盖现有文件夹
        '--clean',                          # 清理临时文件
        '--onefile',                        # 打包成单个文件
        '--hidden-import=PyQt6',            # 确保 PyQt6 被包含
        '--hidden-import=PyQt6.QtWidgets',  # Qt组件
        '--hidden-import=PyQt6.QtCore',     
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=sqlite3',          # 确保 sqlite3 被包含
        '--add-data=icon.ico;.',         # 将图标文件添加到打包中
    ]
    
    # 调用 PyInstaller
    PyInstaller.__main__.run(params)
    
    # 构建完成后的清理工作
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    print(f"\nBuild completed! Version: {version}")
    print("The executable can be found in the 'dist' folder.")

if __name__ == '__main__':
    build() 