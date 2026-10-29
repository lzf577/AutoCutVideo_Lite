"""
AutoCutVideo Lite 现代化高对比度深色主题 QSS
"""

DARK_QSS = """
/* 全局基础 */
QWidget {
    background-color: #121418;
    color: #ECEFF4;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

/* 窗口与对话框 */
QMainWindow, QDialog, QMessageBox {
    background-color: #181B22;
    color: #ECEFF4;
}

/* 卡片容器 */
QFrame#CardFrame {
    background-color: #1E222A;
    border: 1px solid #2D3748;
    border-radius: 8px;
    padding: 12px;
}

/* 标签与文本 (高对比度纯白/浅灰，透明底色) */
QLabel {
    background-color: transparent;
    color: #F1F5F9;
    font-size: 13px;
}

/* 标签页 QTabWidget */
QTabWidget {
    background-color: transparent;
}
QTabWidget::pane {
    border: 1px solid #2D3748;
    background-color: #1E222A;
    border-radius: 6px;
    padding: 14px;
}
QTabBar::tab {
    background-color: #242933;
    color: #94A3B8;
    padding: 8px 20px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #1E222A;
    color: #38BDF8;
    border: 1px solid #2D3748;
    border-bottom: 1px solid #1E222A;
    font-weight: bold;
}
QTabBar::tab:hover {
    color: #FFFFFF;
    background-color: #2E3440;
}

/* 分组框 QGroupBox */
QGroupBox {
    font-weight: bold;
    color: #38BDF8;
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 22px;
    padding-bottom: 14px;
    padding-left: 14px;
    padding-right: 14px;
    background-color: #181B22;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: #181B22;
}

/* 输入框、下拉框、数字调节框 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #242933;
    border: 1px solid #3B4252;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 32px;
    font-size: 13px;
    color: #FFFFFF;
    selection-background-color: #0284C7;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #38BDF8;
}
QComboBox {
    padding-right: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1E222A;
    color: #FFFFFF;
    selection-background-color: #0284C7;
    border: 1px solid #3B4252;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 8px;
}

/* 复选框 QCheckBox */
QCheckBox {
    color: #F1F5F9;
    spacing: 8px;
    background-color: transparent;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #4C566A;
    border-radius: 4px;
    background-color: #242933;
}
QCheckBox::indicator:checked {
    background-color: #0284C7;
    border-color: #38BDF8;
}

/* 按钮通用 */
QPushButton {
    background-color: #2E3440;
    color: #ECEFF4;
    border: 1px solid #434C5E;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3B4252;
    border-color: #4C566A;
}
QPushButton:pressed {
    background-color: #434C5E;
}
QPushButton#PrimaryBtn {
    background-color: #0284C7;
    color: #FFFFFF;
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 8px 20px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #0369A1;
}
QPushButton#StopBtn {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
    font-weight: bold;
    padding: 8px 16px;
}
QPushButton#StopBtn:hover {
    background-color: #B91C1C;
}

/* 对话框操作按钮 (Save / Cancel) */
QDialogButtonBox QPushButton {
    background-color: #2E3440;
    color: #ECEFF4;
    border: 1px solid #434C5E;
    border-radius: 6px;
    padding: 6px 18px;
    min-width: 70px;
    font-weight: 500;
}
QDialogButtonBox QPushButton:hover {
    background-color: #0284C7;
    color: #FFFFFF;
    border-color: #38BDF8;
}

/* 消息提示框 QMessageBox */
QMessageBox {
    background-color: #181B22;
    min-width: 420px;
}
QMessageBox QLabel {
    background-color: transparent;
    color: #F8FAFC;
    font-size: 13px;
    line-height: 1.5;
    padding: 6px 0;
}
QMessageBox QPushButton {
    background-color: #0284C7;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 24px;
    min-width: 80px;
    font-weight: bold;
}
QMessageBox QPushButton:hover {
    background-color: #0369A1;
}

/* 任务列表表格 */
QTableWidget {
    background-color: #1E222A;
    border: 1px solid #2D3748;
    border-radius: 6px;
    gridline-color: #2D3748;
    selection-background-color: #2A3B5C;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background-color: #242933;
    color: #94A3B8;
    padding: 6px;
    border: none;
    border-right: 1px solid #2D3748;
    border-bottom: 1px solid #2D3748;
    font-weight: bold;
}

/* 实时终端日志框 */
QTextEdit {
    background-color: #0F1115;
    border: 1px solid #2D3748;
    border-radius: 6px;
    color: #38BDF8;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}

/* 进度条 */
QProgressBar {
    background-color: #242933;
    border: 1px solid #3B4252;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #0284C7;
    border-radius: 5px;
}
"""
