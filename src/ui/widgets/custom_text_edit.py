from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt

class LogTextEdit(QTextEdit):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.setReadOnly(True)  # 设置为只读
        
    def paintEvent(self, event):
        """重写绘制事件，添加占位符文本"""
        super().paintEvent(event)
        
        if self.toPlainText() == "" and self.placeholder:
            painter = QPainter(self.viewport())
            painter.setOpacity(0.5)  # 设置透明度
            painter.setPen(QColor("#6C757D"))  # 设置颜色为灰色
            rect = self.rect()
            rect.setLeft(rect.left() + 9)  # 添加左边距，与正常文本对齐
            rect.setTop(rect.top() + 9)    # 添加上边距，与正常文本对齐
            painter.drawText(rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self.placeholder) 