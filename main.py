import os
import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar,
    QMessageBox, QSplitter, QFrame, QSizePolicy, QDialog, QMenu,
    QCheckBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

from config import load_config, save_config, get_ffmpeg_exe
from pipeline.scanner import scan_batch_directory, scan_and_append_directories, ProjectTask
from pipeline.batch_runner import BatchRunnerThread
from settings_dialog import SettingsDialog

from theme import DARK_QSS

class BatchResultDialog(QDialog):
    def __init__(self, success_count: int, failed_count: int, output_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎉 批处理执行完毕")
        self.setMinimumSize(480, 260)
        self.setStyleSheet(DARK_QSS)
        self.output_dir = output_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        # 标题行
        lbl_title = QLabel("<b><h3>批处理任务已全部执行完成！</h3></b>")
        lbl_title.setStyleSheet("color: #38BDF8;")
        layout.addWidget(lbl_title)

        # 统计卡片
        stats_frame = QFrame()
        stats_frame.setObjectName("CardFrame")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(14, 12, 14, 12)
        stats_layout.setSpacing(8)

        lbl_s = QLabel(f"<b>✅ 成功生成:</b> &nbsp;<font color='#10B981' size='+1'><b>{success_count}</b></font> 个")
        lbl_f = QLabel(f"<b>❌ 执行失败:</b> &nbsp;<font color='#EF4444' size='+1'><b>{failed_count}</b></font> 个")
        lbl_out = QLabel(f"<b>📁 成片输出目录:</b><br><font color='#94A3B8'>{self.output_dir}</font>")
        lbl_out.setWordWrap(True)

        stats_layout.addWidget(lbl_s)
        stats_layout.addWidget(lbl_f)
        stats_layout.addWidget(lbl_out)
        layout.addWidget(stats_frame)

        # 底部操作按钮
        h_btn = QHBoxLayout()
        h_btn.addStretch()

        btn_open = QPushButton("📂 打开成片输出目录")
        btn_open.setFixedHeight(36)
        btn_open.clicked.connect(self._open_folder)
        h_btn.addWidget(btn_open)

        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("PrimaryBtn")
        btn_ok.setFixedHeight(36)
        btn_ok.setFixedWidth(90)
        btn_ok.clicked.connect(self.accept)
        h_btn.addWidget(btn_ok)

        layout.addLayout(h_btn)

    def _open_folder(self):
        os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(self.output_dir)
        else:
            subprocess.Popen(["xdg-open", self.output_dir])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoCutVideo 极简批量版 (Lite v1.04)")
        self.resize(1560, 920)
        self.setMinimumSize(1200, 750)
        self.setAcceptDrops(True)

        # 启动自适应屏幕中央居中显示
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            cx = max(0, (geo.width() - 1520) // 2)
            cy = max(0, (geo.height() - 920) // 2 - 15)
            self.setGeometry(cx, cy, 1520, 920)

        self.config = load_config()
        self.tasks = []
        self.runner_thread = None
        self.init_ui()

        # 检查是否记住上次的目录
        last_dir = self.config.get("last_batch_dir", "")
        if last_dir and os.path.isdir(last_dir):
            self.edit_dir.setText(last_dir)
            self._scan_directory(last_dir)

    def init_ui(self):
        self.setStyleSheet(DARK_QSS)
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. 顶部栏：批处理目录选择与快捷操作
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.setSpacing(10)

        top_layout.addWidget(QLabel("<b>📁 批处理根目录:</b>"))
        self.edit_dir = QLineEdit()
        self.edit_dir.setPlaceholderText("选择或直接拖入包含各项目子文件夹的总目录...")
        self.edit_dir.returnPressed.connect(self._on_dir_entered)
        top_layout.addWidget(self.edit_dir, stretch=1)

        btn_add_dir = QPushButton("➕ 添加项目")
        btn_add_dir.setToolTip("选择单个或多个项目文件夹追加到当前任务清单")
        btn_add_dir.clicked.connect(self._browse_add_directory)
        top_layout.addWidget(btn_add_dir)

        btn_browse = QPushButton("📂 扫描总目录")
        btn_browse.setToolTip("选择包含多个子项目的总目录并加载任务")
        btn_browse.clicked.connect(self._browse_directory)
        top_layout.addWidget(btn_browse)

        btn_rescan = QPushButton("🔄 重新扫描")
        btn_rescan.clicked.connect(self._rescan)
        top_layout.addWidget(btn_rescan)

        btn_open_out = QPushButton("📤 打开成片输出目录")
        btn_open_out.clicked.connect(self._open_output_dir)
        top_layout.addWidget(btn_open_out)

        btn_settings = QPushButton("⚙️ 设置")
        btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(btn_settings)

        main_layout.addWidget(top_card)

        # 2. 统计状态看板
        self.lbl_stats = QLabel("📊 待扫描项目...")
        self.lbl_stats.setStyleSheet("color: #94A3B8; font-size: 13px; font-weight: 500;")
        main_layout.addWidget(self.lbl_stats)

        # 3. 中部核心区：任务列表 + 实时日志 (左右分栏)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：任务表格
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)

        h_table_header = QHBoxLayout()
        h_table_header.addWidget(QLabel("<b>📋 任务项目清单:</b>"))
        h_table_header.addStretch()

        self.btn_del_task = QPushButton("🗑️ 移除选中 (Del)")
        self.btn_del_task.setFixedHeight(30)
        self.btn_del_task.setToolTip("移除选中的任务项（快捷键：Delete 键）")
        self.btn_del_task.clicked.connect(self._delete_selected_tasks)
        h_table_header.addWidget(self.btn_del_task)

        self.btn_clear_tasks = QPushButton("🧹 清空列表")
        self.btn_clear_tasks.setFixedHeight(30)
        self.btn_clear_tasks.setToolTip("清空所有任务项")
        self.btn_clear_tasks.clicked.connect(self._clear_all_tasks)
        h_table_header.addWidget(self.btn_clear_tasks)

        table_layout.addLayout(h_table_header)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "序号", "文件夹", "主视频", "幻灯片", "封面", "切片", "Logo", "状态", "成片"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        # 右侧：实时日志面板
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(6)

        h_log_header = QHBoxLayout()
        h_log_header.addWidget(QLabel("<b>📜 实时流水线日志:</b>"))
        h_log_header.addStretch()
        btn_clear_log = QPushButton("🧹 清空日志")
        btn_clear_log.setFixedHeight(30)
        btn_clear_log.clicked.connect(lambda: self.txt_log.clear())
        h_log_header.addWidget(btn_clear_log)
        log_layout.addLayout(h_log_header)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        log_layout.addWidget(self.txt_log)
        splitter.addWidget(log_container)

        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([920, 600])
        main_layout.addWidget(splitter, stretch=1)

        # 4. 底部状态与全局控制条
        bottom_card = QFrame()
        bottom_card.setObjectName("CardFrame")
        bottom_layout = QHBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(26)
        bottom_layout.addWidget(self.progress_bar, stretch=1)

        self.chk_llm_polish = QCheckBox("🤖 AI字幕智能纠错")
        self.chk_llm_polish.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: 500;")
        self.chk_llm_polish.setChecked(self.config.get("enable_llm_polish", True))
        self.chk_llm_polish.setToolTip("开启：调用 Google Gemini 自动纠错同音字；\n关闭：100%纯离线极速模式（跳过联网校对，每片秒速出片）。")
        self.chk_llm_polish.toggled.connect(self._on_llm_polish_toggled)
        bottom_layout.addWidget(self.chk_llm_polish)

        self.btn_start = QPushButton("▶️ 一键开始批量处理")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self._start_batch_processing)
        bottom_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹️ 停止")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_batch_processing)
        bottom_layout.addWidget(self.btn_stop)

        main_layout.addWidget(bottom_card)

    def _browse_add_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择要追加的项目文件夹")
        if dir_path:
            self._scan_directory(dir_path, append_mode=True)

    def _browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择批处理项目总目录")
        if dir_path:
            self.edit_dir.setText(dir_path)
            self._scan_directory(dir_path, append_mode=False)

    def _on_dir_entered(self):
        dir_path = self.edit_dir.text().strip()
        if os.path.isdir(dir_path):
            self._scan_directory(dir_path, append_mode=False)

    def _rescan(self):
        dir_path = self.edit_dir.text().strip()
        if os.path.isdir(dir_path):
            self._scan_directory(dir_path, append_mode=False)

    def _scan_directory(self, dir_path: str, append_mode: bool = False):
        self.config["last_batch_dir"] = dir_path
        save_config(self.config)

        self.txt_log.append(f"🔍 正在解析目录: {dir_path} ...")
        if append_mode:
            self.tasks, added_count = scan_and_append_directories(self.tasks, [dir_path])
            self._render_table_rows()
            self.txt_log.append(f"📥 成功追加 {added_count} 个任务！当前清单共有 {len(self.tasks)} 个任务。")
        else:
            self.tasks, added_count = scan_and_append_directories([], [dir_path])
            self._render_table_rows()
            self.txt_log.append(f"✅ 扫描完毕，发现有效任务 {added_count} 个")

    def _delete_selected_tasks(self):
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        if not selected_rows:
            return

        del_names = []
        for row in selected_rows:
            if 0 <= row < len(self.tasks):
                del_names.append(self.tasks[row].name)
                self.tasks.pop(row)

        # 重新编排序号
        for idx, t in enumerate(self.tasks):
            t.id = idx + 1

        self._render_table_rows()
        self.txt_log.append(f"🗑️ 已从任务清单移除 {len(selected_rows)} 个项目: {', '.join(del_names)}")

    def _clear_all_tasks(self):
        if not self.tasks:
            return
        count = len(self.tasks)
        self.tasks.clear()
        self._render_table_rows()
        self.txt_log.append(f"🧹 已清空任务清单 (共移除 {count} 个项目)")

    def _render_table_rows(self):
        self.table.setRowCount(0)
        valid_count = 0

        for row, task in enumerate(self.tasks):
            self.table.insertRow(row)

            # 0: 序号
            item_id = QTableWidgetItem(str(task.id))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, item_id)

            # 1: 文件夹
            item_name = QTableWidgetItem(task.name)
            item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_name)

            # 2: 主视频
            v_name = os.path.basename(task.video_path) if task.video_path else "❌ 缺失"
            item_v = QTableWidgetItem(v_name)
            item_v.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not task.video_path:
                item_v.setForeground(QColor("#EF4444"))
            self.table.setItem(row, 2, item_v)

            # 3: 幻灯片
            pdf_name = os.path.basename(task.pdf_path) if task.pdf_path else "—"
            item_pdf = QTableWidgetItem(pdf_name)
            item_pdf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not task.pdf_path:
                item_pdf.setForeground(QColor("#64748B"))
            self.table.setItem(row, 3, item_pdf)

            # 4: 封面 (独立列)
            if task.cover_path and os.path.exists(task.cover_path):
                cov_name = os.path.basename(task.cover_path)
                item_cov = QTableWidgetItem(f"✅ {cov_name}")
                item_cov.setForeground(QColor("#38BDF8"))
            else:
                item_cov = QTableWidgetItem("—")
                item_cov.setForeground(QColor("#64748B"))
            item_cov.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, item_cov)

            # 5: 切片 (独立列)
            if task.broll_path and os.path.exists(task.broll_path):
                if os.path.isdir(task.broll_path):
                    item_br = QTableWidgetItem("✅ 虚晃库")
                else:
                    item_br = QTableWidgetItem(f"✅ {os.path.basename(task.broll_path)}")
                item_br.setForeground(QColor("#A78BFA"))
            else:
                item_br = QTableWidgetItem("—")
                item_br.setForeground(QColor("#64748B"))
            item_br.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, item_br)

            # 6: Logo (独立列)
            if task.logo_path and os.path.exists(task.logo_path):
                item_logo = QTableWidgetItem(f"✅ {os.path.basename(task.logo_path)}")
                item_logo.setForeground(QColor("#FBBF24"))
            else:
                item_logo = QTableWidgetItem("全局默认")
                item_logo.setForeground(QColor("#64748B"))
            item_logo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, item_logo)

            # 7: 状态
            item_st = QTableWidgetItem(task.status)
            item_st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if task.status == "已完成":
                item_st.setForeground(QColor("#10B981"))
            elif task.status == "处理中":
                item_st.setForeground(QColor("#38BDF8"))
            elif task.status in {"失败", "无效项目"}:
                item_st.setForeground(QColor("#EF4444"))
            self.table.setItem(row, 7, item_st)

            # 8: 成片
            out_str = "等待生成"
            if task.output_video_path and os.path.exists(task.output_video_path):
                out_str = "✅ 已导出"
            item_out = QTableWidgetItem(out_str)
            item_out.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if out_str.startswith("✅"):
                item_out.setForeground(QColor("#10B981"))
            self.table.setItem(row, 8, item_out)

            if task.is_valid():
                valid_count += 1

        self.lbl_stats.setText(f"📊 当前清单：共 {len(self.tasks)} 个项目，其中有效待处理 {valid_count} 个。")

    def _show_table_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(DARK_QSS)
        act_del = menu.addAction("🗑️ 移除选中项目 (Delete)")
        act_open = menu.addAction("📂 打开项目所在文件夹")
        menu.addSeparator()
        act_clear = menu.addAction("🧹 清空所有任务")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_del:
            self._delete_selected_tasks()
        elif action == act_clear:
            self._clear_all_tasks()
        elif action == act_open:
            cur_row = self.table.currentRow()
            if 0 <= cur_row < len(self.tasks):
                f_path = self.tasks[cur_row].folder_path
                if os.path.exists(f_path):
                    if sys.platform == "win32":
                        os.startfile(f_path)
                    else:
                        subprocess.Popen(["xdg-open", f_path])

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.table.hasFocus():
                self._delete_selected_tasks()
                return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [u.toLocalFile() for u in urls if u.toLocalFile() and os.path.exists(u.toLocalFile())]
            if paths:
                self.tasks, added_count = scan_and_append_directories(self.tasks, paths)
                self._render_table_rows()
                if not self.edit_dir.text().strip() and paths:
                    self.edit_dir.setText(paths[0] if os.path.isdir(paths[0]) else os.path.dirname(paths[0]))
                self.txt_log.append(f"📥 成功拖入追加 {added_count} 个任务！当前清单共有 {len(self.tasks)} 个任务待处理。")
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _get_output_dir(self) -> str:
        custom_out = self.config.get("custom_output_dir", "").strip()
        if custom_out:
            return custom_out
        root = self.edit_dir.text().strip()
        if root and os.path.isdir(root):
            return os.path.join(root, "output")
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

    def _open_output_dir(self):
        out_dir = self._get_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(out_dir)
        else:
            subprocess.Popen(["xdg-open", out_dir])

    def _on_llm_polish_toggled(self, checked: bool):
        self.config["enable_llm_polish"] = checked
        save_config(self.config)
        status_str = "已开启 (调用大模型纠错)" if checked else "已关闭 (纯离线极速模式，跳过联网校对)"
        self.txt_log.append(f"🤖 AI字幕纠错: {status_str}")

    def _open_settings(self):
        self.config = load_config()
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self.config = dlg.get_updated_config()
            save_config(self.config)
            self.chk_llm_polish.setChecked(self.config.get("enable_llm_polish", True))
            from config import CONFIG_FILE
            self.txt_log.append(f"⚙️ 配置已成功保存生效并持久化至本地: {CONFIG_FILE}")

    def _start_batch_processing(self):
        if not self.tasks:
            QMessageBox.warning(self, "提示", "当前没有扫描到任何项目任务，请先选择批处理根目录！")
            return

        valid_tasks = [t for t in self.tasks if t.is_valid()]
        if not valid_tasks:
            QMessageBox.warning(self, "提示", "没有包含有效主视频的项目！")
            return

        # 确保最新勾选状态传入配置
        self.config["enable_llm_polish"] = self.chk_llm_polish.isChecked()

        out_dir = self._get_output_dir()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)

        self.runner_thread = BatchRunnerThread(self.tasks, self.config, out_dir)
        self.runner_thread.log_signal.connect(self._on_log)
        self.runner_thread.task_started_signal.connect(self._on_task_started)
        self.runner_thread.task_progress_signal.connect(self._on_task_progress)
        self.runner_thread.task_finished_signal.connect(self._on_task_finished)
        self.runner_thread.all_finished_signal.connect(self._on_all_finished)
        self.runner_thread.start()

    def _stop_batch_processing(self):
        if self.runner_thread and self.runner_thread.isRunning():
            self.btn_stop.setEnabled(False)
            self.txt_log.append("⚠️ 正在请求停止批处理...")
            self.runner_thread.stop()

    def _on_log(self, msg: str):
        self.txt_log.append(msg)

    def _on_task_started(self, task_id: int, task_name: str):
        row = task_id - 1
        if 0 <= row < self.table.rowCount():
            item = self.table.item(row, 7)
            if item:
                item.setText("⏳ 处理中...")
                item.setForeground(QColor("#38BDF8"))

    def _on_task_progress(self, task_id: int, percent: int, msg: str):
        row = task_id - 1
        if 0 <= row < self.table.rowCount():
            item = self.table.item(row, 7)
            if item:
                item.setText(f"⏳ {percent}% - {msg}")
                item.setForeground(QColor("#38BDF8"))

        total_tasks = max(1, len(self.tasks))
        global_pct = min(99, int(((task_id - 1) * 100 + percent) / total_tasks))
        self.progress_bar.setValue(global_pct)
        self.progress_bar.setFormat(f"总体进度: {global_pct}% | 任务 [{task_id}/{total_tasks}]: {percent}% - {msg}")

    def _on_task_finished(self, task_id: int, success: bool, msg: str):
        row = task_id - 1
        if 0 <= row < self.table.rowCount():
            item_st = self.table.item(row, 7)
            item_out = self.table.item(row, 8)
            if success:
                if item_st:
                    item_st.setText("✅ 已完成")
                    item_st.setForeground(QColor("#10B981"))
                if item_out:
                    item_out.setText("✅ 已导出")
                    item_out.setForeground(QColor("#10B981"))
            else:
                if item_st:
                    item_st.setText("❌ 失败")
                    item_st.setForeground(QColor("#EF4444"))

    def _on_all_finished(self, success_count: int, failed_count: int):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(f"总体进度: 100% | 批处理完成 (成功 {success_count} 个, 失败 {failed_count} 个)")

    def closeEvent(self, event):
        """窗口关闭时安全终止后台批处理工作线程并释放句柄"""
        try:
            if self.runner_thread and self.runner_thread.isRunning():
                self.runner_thread.stop()
                self.runner_thread.wait(1000)
        except Exception:
            pass
        event.accept()

if __name__ == "__main__":
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    window = MainWindow()
    window.show()
    ret = app.exec()
    
    # 显式清理对象与垃圾回收
    try:
        del window
        import gc
        gc.collect()
    except Exception:
        pass
        
    os._exit(ret)
