import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QFileDialog, QSpinBox,
    QDoubleSpinBox, QCheckBox, QComboBox, QGroupBox, QFormLayout,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from theme import DARK_QSS

class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.setWindowTitle("⚙️ 全局参数与配置")
        self.resize(780, 620)
        self.setMinimumSize(720, 560)
        self.setStyleSheet(DARK_QSS)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        tabs = QTabWidget()

        def create_form_layout(parent_widget):
            form = QFormLayout(parent_widget)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setHorizontalSpacing(18)
            form.setVerticalSpacing(16)
            form.setContentsMargins(20, 24, 20, 20)
            return form

        # ==========================================
        # Tab 1: 素材与版式
        # ==========================================
        tab_media = QWidget()
        tab_media.setStyleSheet("background-color: #1E222A;")
        form_media = create_form_layout(tab_media)

        # 全局 Logo
        self.edit_logo = QLineEdit(self.config.get("global_logo_path", ""))
        self.edit_logo.setFixedHeight(34)
        self.edit_logo.setPlaceholderText("可选择图片Logo(.png/.jpg)或视频动态Logo(.mp4)...")
        btn_logo = QPushButton("浏览...")
        btn_logo.setFixedHeight(34)
        btn_logo.clicked.connect(self._select_logo)
        h_logo = QHBoxLayout()
        h_logo.addWidget(self.edit_logo)
        h_logo.addWidget(btn_logo)
        form_media.addRow("全局默认 Logo 水印:", h_logo)

        # Logo 缩放
        self.spin_logo_scale = QSpinBox()
        self.spin_logo_scale.setFixedHeight(34)
        self.spin_logo_scale.setRange(1, 100)
        self.spin_logo_scale.setValue(int(self.config.get("logo_scale_percent", 12)))
        self.spin_logo_scale.setSuffix(" % (相对视频宽度)")
        form_media.addRow("Logo 缩放大小:", self.spin_logo_scale)

        # Logo 贴边边距
        h_logo_margin = QHBoxLayout()
        self.spin_logo_mr = QSpinBox()
        self.spin_logo_mr.setFixedHeight(34)
        self.spin_logo_mr.setRange(0, 500)
        self.spin_logo_mr.setValue(int(self.config.get("logo_margin_right", 0)))
        self.spin_logo_mr.setSuffix(" px (右边距)")

        self.spin_logo_mb = QSpinBox()
        self.spin_logo_mb.setFixedHeight(34)
        self.spin_logo_mb.setRange(0, 500)
        self.spin_logo_mb.setValue(int(self.config.get("logo_margin_bottom", 0)))
        self.spin_logo_mb.setSuffix(" px (下边距)")

        h_logo_margin.addWidget(self.spin_logo_mr)
        h_logo_margin.addWidget(self.spin_logo_mb)
        form_media.addRow("Logo 贴边边距:", h_logo_margin)

        # 全局虚晃素材
        self.edit_broll = QLineEdit(self.config.get("global_broll_path", ""))
        self.edit_broll.setFixedHeight(34)
        self.edit_broll.setPlaceholderText("选择默认虚晃视频文件或素材文件夹...")
        btn_broll = QPushButton("浏览素材...")
        btn_broll.setFixedHeight(34)
        btn_broll.clicked.connect(self._select_broll)
        h_broll = QHBoxLayout()
        h_broll.addWidget(self.edit_broll)
        h_broll.addWidget(btn_broll)
        form_media.addRow("全局虚晃素材库 (B-Roll):", h_broll)

        # 虚晃空镜启用与时长
        self.chk_broll = QCheckBox("启用虚晃镜头自动穿插")
        self.chk_broll.setFixedHeight(28)
        self.chk_broll.setChecked(self.config.get("broll_enable", True))
        form_media.addRow("虚晃功能开关:", self.chk_broll)

        h_broll_dur = QHBoxLayout()
        self.spin_broll_min = QDoubleSpinBox()
        self.spin_broll_min.setFixedHeight(34)
        self.spin_broll_min.setRange(2.0, 30.0)
        self.spin_broll_min.setValue(float(self.config.get("broll_chunk_min", 8.0)))
        self.spin_broll_min.setSuffix(" 秒")
        
        self.spin_broll_max = QDoubleSpinBox()
        self.spin_broll_max.setFixedHeight(34)
        self.spin_broll_max.setRange(2.0, 30.0)
        self.spin_broll_max.setValue(float(self.config.get("broll_chunk_max", 12.0)))
        self.spin_broll_max.setSuffix(" 秒")

        h_broll_dur.addWidget(QLabel("最小:"))
        h_broll_dur.addWidget(self.spin_broll_min)
        h_broll_dur.addWidget(QLabel("最大:"))
        h_broll_dur.addWidget(self.spin_broll_max)
        form_media.addRow("单个镜头切片区间:", h_broll_dur)

        # 双音轨独立音量
        h_vol = QHBoxLayout()
        self.spin_main_vol = QSpinBox()
        self.spin_main_vol.setFixedHeight(34)
        self.spin_main_vol.setRange(0, 200)
        self.spin_main_vol.setValue(int(self.config.get("main_audio_volume", 100)))
        self.spin_main_vol.setSuffix(" % (解说人声)")
        
        self.spin_broll_vol = QSpinBox()
        self.spin_broll_vol.setFixedHeight(34)
        self.spin_broll_vol.setRange(0, 200)
        self.spin_broll_vol.setValue(int(self.config.get("broll_audio_volume", 20)))
        self.spin_broll_vol.setSuffix(" % (切片环境音)")

        h_vol.addWidget(self.spin_main_vol)
        h_vol.addWidget(self.spin_broll_vol)
        form_media.addRow("🔊 双音轨独立音量:", h_vol)

        # 视频去头去尾剪裁
        h_trim = QHBoxLayout()
        self.spin_trim_s = QDoubleSpinBox()
        self.spin_trim_s.setFixedHeight(34)
        self.spin_trim_s.setRange(0.0, 300.0)
        self.spin_trim_s.setSingleStep(0.5)
        self.spin_trim_s.setValue(float(self.config.get("trim_start", 0.0)))
        self.spin_trim_s.setSuffix(" 秒 (去头)")

        self.spin_trim_e = QDoubleSpinBox()
        self.spin_trim_e.setFixedHeight(34)
        self.spin_trim_e.setRange(0.0, 300.0)
        self.spin_trim_e.setSingleStep(0.5)
        self.spin_trim_e.setValue(float(self.config.get("trim_end", 3.0)))
        self.spin_trim_e.setSuffix(" 秒 (去尾)")

        h_trim.addWidget(self.spin_trim_s)
        h_trim.addWidget(self.spin_trim_e)
        form_media.addRow("视频去头去尾剪裁 (TRIM):", h_trim)

        tabs.addTab(tab_media, "🎨 素材与版式")

        # ==========================================
        # Tab 2: 字幕样式与排版
        # ==========================================
        tab_sub = QWidget()
        tab_sub.setStyleSheet("background-color: #1E222A;")
        vbox_sub = QVBoxLayout(tab_sub)
        vbox_sub.setContentsMargins(16, 16, 16, 16)
        vbox_sub.setSpacing(14)

        from config import SUBTITLE_PRESETS
        self.subtitle_presets = SUBTITLE_PRESETS

        form_sub = QFormLayout()
        form_sub.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form_sub.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_sub.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_sub.setHorizontalSpacing(18)
        form_sub.setVerticalSpacing(12)

        # 1. 预设模板选择器
        self.combo_sub_preset = QComboBox()
        self.combo_sub_preset.setFixedHeight(34)
        self.combo_sub_preset.addItem("✨ 自定义微调 (Custom)", "custom")
        for p_key, p_val in self.subtitle_presets.items():
            self.combo_sub_preset.addItem(p_val.get("name", p_key), p_key)
        
        sub_style = self.config.get("subtitle_style", {})
        saved_preset_key = self.config.get("subtitle_preset", "")
        for i in range(1, self.combo_sub_preset.count()):
            if saved_preset_key and self.combo_sub_preset.itemData(i) == saved_preset_key:
                self.combo_sub_preset.setCurrentIndex(i)
                break
        self.combo_sub_preset.currentIndexChanged.connect(self._on_sub_preset_changed)
        form_sub.addRow("🎨 字幕预设风格:", self.combo_sub_preset)

        # 2. 字体名称
        self.edit_font_name = QLineEdit(sub_style.get("font_name", "SimHei"))
        self.edit_font_name.setFixedHeight(34)
        self.edit_font_name.textChanged.connect(self._update_sub_preview)
        form_sub.addRow("字体名称 (Font):", self.edit_font_name)

        # 3. 字体大小与垂直边距
        h_sub_geom = QHBoxLayout()
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setFixedHeight(34)
        self.spin_font_size.setRange(10, 100)
        self.spin_font_size.setValue(int(sub_style.get("font_size", 24)))
        self.spin_font_size.setSuffix(" pt")
        self.spin_font_size.valueChanged.connect(self._update_sub_preview)

        self.spin_margin_v = QSpinBox()
        self.spin_margin_v.setFixedHeight(34)
        self.spin_margin_v.setRange(0, 500)
        self.spin_margin_v.setValue(int(sub_style.get("margin_v", 45)))
        self.spin_margin_v.setSuffix(" px")

        h_sub_geom.addWidget(QLabel("字号:"))
        h_sub_geom.addWidget(self.spin_font_size)
        h_sub_geom.addWidget(QLabel("底边距:"))
        h_sub_geom.addWidget(self.spin_margin_v)
        form_sub.addRow("排版尺寸与边距:", h_sub_geom)

        # 4. 文字颜色与描边
        h_sub_color = QHBoxLayout()
        self.edit_pri_color = QLineEdit(sub_style.get("primary_color", "&H0000FFFF"))
        self.edit_pri_color.setFixedHeight(34)
        self.edit_pri_color.textChanged.connect(self._update_sub_preview)

        self.edit_out_color = QLineEdit(sub_style.get("outline_color", "&H00000000"))
        self.edit_out_color.setFixedHeight(34)

        self.spin_outline = QSpinBox()
        self.spin_outline.setFixedHeight(34)
        self.spin_outline.setRange(0, 10)
        self.spin_outline.setValue(int(sub_style.get("outline_width", 2)))
        self.spin_outline.setSuffix(" px")

        h_sub_color.addWidget(QLabel("主色:"))
        h_sub_color.addWidget(self.edit_pri_color)
        h_sub_color.addWidget(QLabel("描边色:"))
        h_sub_color.addWidget(self.edit_out_color)
        h_sub_color.addWidget(QLabel("描边宽:"))
        h_sub_color.addWidget(self.spin_outline)
        form_sub.addRow("色彩与描边 (ASS格式):", h_sub_color)

        vbox_sub.addLayout(form_sub)

        # 5. 实时效果预览卡片
        lbl_prev_title = QLabel("<b>👁️ 字幕实时渲染预览:</b>")
        lbl_prev_title.setStyleSheet("color: #38BDF8; margin-top: 4px;")
        vbox_sub.addWidget(lbl_prev_title)

        self.lbl_preview = QLabel("这里是体育解说短视频经典字幕样式效果演示")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setFixedHeight(50)
        vbox_sub.addWidget(self.lbl_preview)
        self._update_sub_preview()

        tabs.addTab(tab_sub, "🔤 字幕排版")

        # ==========================================
        # Tab 3: 语音识别与硬件加速
        # ==========================================
        tab_hw = QWidget()
        tab_hw.setStyleSheet("background-color: #1E222A;")
        form_hw = create_form_layout(tab_hw)

        self.combo_whisper = QComboBox()
        self.combo_whisper.setFixedHeight(36)
        self.combo_whisper.addItems([
            "medium (高精度/支持自动下载)",
            "small (高精度/已内置)",
            "base (极速推荐/已内置)",
            "large-v3 (顶级精度/支持自动下载)",
            "tiny (超轻量)"
        ])
        saved_wh = str(self.config.get("whisper_model", "small")).lower()
        for i in range(self.combo_whisper.count()):
            item_t = self.combo_whisper.itemText(i).lower()
            if saved_wh and (saved_wh in item_t or item_t.startswith(saved_wh)):
                self.combo_whisper.setCurrentIndex(i)
                break
        
        # Whisper 模型状态提示
        self.lbl_whisper_status = QLabel()
        self.lbl_whisper_status.setStyleSheet("color: #94A3B8; font-size: 12px;")
        
        def _update_whisper_tip():
            cur_txt = self.combo_whisper.currentText().lower()
            clean_name = "small"
            for k in ["large-v3", "medium", "small", "base", "tiny"]:
                if k in cur_txt:
                    clean_name = k
                    break
            base_dir = os.path.dirname(os.path.abspath(__file__))
            m_path = os.path.join(base_dir, "models", clean_name)
            is_ready = os.path.isdir(m_path) and (
                os.path.exists(os.path.join(m_path, "model.bin")) or os.path.exists(os.path.join(m_path, "model.safetensors"))
            )
            if is_ready:
                self.lbl_whisper_status.setText(f"<font color='#10B981'><b>🟢 本地已就绪:</b></font> 离线模型已存在于 models/{clean_name}")
            else:
                self.lbl_whisper_status.setText(f"<font color='#38BDF8'><b>🌐 自动下载:</b></font> 运行或点击时将通过镜像源自动高速下载 models/{clean_name}")

        self.combo_whisper.currentIndexChanged.connect(_update_whisper_tip)
        _update_whisper_tip()

        whisper_box = QVBoxLayout()
        whisper_box.setSpacing(4)
        whisper_box.addWidget(self.combo_whisper)
        whisper_box.addWidget(self.lbl_whisper_status)
        form_hw.addRow("Whisper 语音模型:", whisper_box)

        self.combo_device = QComboBox()
        self.combo_device.setFixedHeight(36)
        self.combo_device.addItems(["auto", "cuda", "cpu"])
        self.combo_device.setCurrentText(self.config.get("whisper_device", "auto"))
        form_hw.addRow("Whisper 运行设备:", self.combo_device)

        self.combo_encoder = QComboBox()
        self.combo_encoder.setFixedHeight(36)
        self.combo_encoder.addItems([
            "auto (智能自适应GPU加速)",
            "h264_nvenc (NVIDIA 显卡加速)",
            "h264_qsv (Intel QuickSync 硬件加速)",
            "h264_amf (AMD 显卡加速)",
            "libx264 (纯 CPU 极速多线程)"
        ])
        saved_enc = self.config.get("video_encoder", "auto")
        for i in range(self.combo_encoder.count()):
            if saved_enc in self.combo_encoder.itemText(i):
                self.combo_encoder.setCurrentIndex(i)
                break
        form_hw.addRow("视频压制 GPU 加速:", self.combo_encoder)

        # 片头封面时长
        self.spin_cover_dur = QDoubleSpinBox()
        self.spin_cover_dur.setFixedHeight(36)
        self.spin_cover_dur.setRange(0.0, 10.0)
        self.spin_cover_dur.setSingleStep(0.5)
        self.spin_cover_dur.setValue(float(self.config.get("cover_duration", 1.0)))
        self.spin_cover_dur.setSuffix(" 秒")
        form_hw.addRow("片头封面停留时长:", self.spin_cover_dur)

        tabs.addTab(tab_hw, "🎙️ 语音与硬件")

        # ==========================================
        # Tab 4: 字幕智能错别字校对引擎
        # ==========================================
        tab_sub_ai = QWidget()
        tab_sub_ai.setStyleSheet("background-color: #1E222A;")
        form_sub_ai = create_form_layout(tab_sub_ai)

        self.chk_sub_polish = QCheckBox("启用大模型字幕错别字智能校对")
        self.chk_sub_polish.setChecked(self.config.get("enable_llm_polish", True))
        self.chk_sub_polish.setFixedHeight(30)
        form_sub_ai.addRow("校对总开关:", self.chk_sub_polish)

        self.combo_sub_engine = QComboBox()
        self.combo_sub_engine.setFixedHeight(36)
        self.combo_sub_engine.addItem("🌐 Gemini 网页版静默校对 (免API Key / 终身免费 / 推荐)", "gemini_web")
        self.combo_sub_engine.addItem("🔑 Gemini 官方 API 接口 (使用下方专属 Key)", "gemini_api")
        sub_eng = self.config.get("sub_llm_engine", self.config.get("llm_engine", "gemini_web"))
        idx_sub = self.combo_sub_engine.findData(sub_eng)
        self.combo_sub_engine.setCurrentIndex(max(0, idx_sub))
        form_sub_ai.addRow("字幕校对驱动:", self.combo_sub_engine)

        self.edit_sub_key = QLineEdit(self.config.get("sub_llm_key", self.config.get("llm_api_key", "")))
        self.edit_sub_key.setFixedHeight(36)
        self.edit_sub_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_sub_key.setPlaceholderText("字幕专用 Key (支持多组Key逗号分隔)...")
        form_sub_ai.addRow("字幕 API Key:", self.edit_sub_key)

        self.edit_sub_url = QLineEdit(self.config.get("sub_llm_url", self.config.get("llm_base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")))
        self.edit_sub_url.setFixedHeight(36)
        form_sub_ai.addRow("字幕 API Base URL:", self.edit_sub_url)

        self.combo_sub_model = QComboBox()
        self.combo_sub_model.setFixedHeight(36)
        self.combo_sub_model.addItems([
            "🔄 自动多Key/7大模型智能轮询 (Auto Round-Robin / 推荐)",
            "gemini-2.5-flash (推荐/最新极速)",
            "gemini-2.5-flash-lite (轻量极速)",
            "gemini-3.6-flash (次世代 3.6 增强版)",
            "gemini-3.5-flash (次世代 3.5 旗舰版)",
            "gemini-3.1-flash-lite (次世代 3.1 极速)",
            "gemini-3-flash (次世代 3.0 基础版)",
            "gemini-robotics-er-1.6-preview (高精度预览版)"
        ])
        saved_sub_model = self.config.get("sub_llm_model", self.config.get("llm_model", "gemini-2.5-flash"))
        for i in range(self.combo_sub_model.count()):
            if saved_sub_model in self.combo_sub_model.itemText(i):
                self.combo_sub_model.setCurrentIndex(i)
                break
        form_sub_ai.addRow("字幕 API 模型:", self.combo_sub_model)

        tabs.addTab(tab_sub_ai, "✍️ 字幕智能校对")

        # ==========================================
        # Tab 5: PDF 幻灯片智能对齐插图引擎
        # ==========================================
        tab_pdf_ai = QWidget()
        tab_pdf_ai.setStyleSheet("background-color: #1E222A;")
        form_pdf_ai = create_form_layout(tab_pdf_ai)

        self.chk_pdf_align = QCheckBox("启用 PDF 语义智能插图对齐 (按右上角编号与解说词毫秒定位)")
        self.chk_pdf_align.setChecked(self.config.get("enable_pdf_align", True))
        self.chk_pdf_align.setFixedHeight(30)
        form_pdf_ai.addRow("插图对齐开关:", self.chk_pdf_align)

        self.combo_pdf_engine = QComboBox()
        self.combo_pdf_engine.setFixedHeight(36)
        self.combo_pdf_engine.addItem("🔑 Gemini 官方 API 自动轮询对齐 (推荐/多Key与7模型自动接力)", "gemini_api")
        self.combo_pdf_engine.addItem("🌐 Gemini 网页版对齐 (免 Key 交互)", "gemini_web")
        self.combo_pdf_engine.addItem("⚡ 本地 RapidOCR 关键词对齐 (纯离线 / 0 API 消耗)", "rapid_ocr")
        pdf_eng = self.config.get("pdf_align_engine", "gemini_api")
        idx_pdf = self.combo_pdf_engine.findData(pdf_eng)
        self.combo_pdf_engine.setCurrentIndex(max(0, idx_pdf))
        form_pdf_ai.addRow("插图对齐驱动:", self.combo_pdf_engine)

        self.edit_pdf_key = QLineEdit(self.config.get("pdf_align_key", self.config.get("llm_api_key", "")))
        self.edit_pdf_key.setFixedHeight(36)
        self.edit_pdf_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pdf_key.setPlaceholderText("插图专用 Key (支持多组Key逗号分隔)...")
        form_pdf_ai.addRow("插图 API Key:", self.edit_pdf_key)

        self.edit_pdf_url = QLineEdit(self.config.get("pdf_align_url", "https://generativelanguage.googleapis.com/v1beta/openai/"))
        self.edit_pdf_url.setFixedHeight(36)
        form_pdf_ai.addRow("插图 API Base URL:", self.edit_pdf_url)

        self.combo_pdf_model = QComboBox()
        self.combo_pdf_model.setFixedHeight(36)
        self.combo_pdf_model.addItems([
            "🔄 自动多Key/7大模型智能轮询 (Auto Round-Robin / 推荐)",
            "gemini-2.5-flash (推荐/精准语义匹配)",
            "gemini-2.5-flash-lite (轻量极速)",
            "gemini-3.6-flash (次世代 3.6 增强版)",
            "gemini-3.5-flash (次世代 3.5 旗舰版)",
            "gemini-3.1-flash-lite (次世代 3.1 极速)",
            "gemini-3-flash (次世代 3.0 基础版)",
            "gemini-robotics-er-1.6-preview (高精度预览版)"
        ])
        saved_pdf_model = self.config.get("pdf_align_model", "gemini-2.5-flash")
        for i in range(self.combo_pdf_model.count()):
            if saved_pdf_model in self.combo_pdf_model.itemText(i):
                self.combo_pdf_model.setCurrentIndex(i)
                break
        form_pdf_ai.addRow("插图 API 模型:", self.combo_pdf_model)

        # 幻灯片单页时长
        self.spin_slide_dur = QDoubleSpinBox()
        self.spin_slide_dur.setFixedHeight(36)
        self.spin_slide_dur.setRange(2.0, 60.0)
        self.spin_slide_dur.setSingleStep(1.0)
        self.spin_slide_dur.setValue(float(self.config.get("pdf_slide_duration", 10.0)))
        self.spin_slide_dur.setSuffix(" 秒")
        form_pdf_ai.addRow("幻灯片自适应基准时长:", self.spin_slide_dur)

        tabs.addTab(tab_pdf_ai, "🖼️ PDF 插图引擎")

        layout.addWidget(tabs)

        # 底部操作按钮栏
        h_bottom = QHBoxLayout()
        h_bottom.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedHeight(36)
        btn_cancel.clicked.connect(self.reject)
        h_bottom.addWidget(btn_cancel)

        btn_save = QPushButton("💾 保存配置")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedHeight(36)
        btn_save.clicked.connect(self._on_save)
        h_bottom.addWidget(btn_save)

        layout.addLayout(h_bottom)

    def _on_sub_preset_changed(self):
        p_key = self.combo_sub_preset.currentData()
        if p_key and p_key in self.subtitle_presets:
            preset = self.subtitle_presets[p_key]
            self.edit_font_name.setText(preset.get("font_name", "SimHei"))
            self.spin_font_size.setValue(preset.get("font_size", 24))
            self.edit_pri_color.setText(preset.get("primary_color", "&H0000FFFF"))
            self.edit_out_color.setText(preset.get("outline_color", "&H00000000"))
            self.spin_outline.setValue(preset.get("outline_width", 2))
            self.spin_margin_v.setValue(preset.get("margin_v", 45))
        self._update_sub_preview()

    def _update_sub_preview(self):
        if not hasattr(self, 'lbl_preview'):
            return
        
        def ass_to_hex(ass_str: str, default: str) -> str:
            clean = ass_str.replace("&H", "").replace("&h", "").strip()
            if len(clean) >= 6:
                bgr = clean[-6:]
                bb, gg, rr = bgr[0:2], bgr[2:4], bgr[4:6]
                return f"#{rr}{gg}{bb}"
            return default

        pri_hex = ass_to_hex(self.edit_pri_color.text(), "#FFFF00")
        f_size = max(13, int(self.spin_font_size.value() * 0.85))
        f_name = self.edit_font_name.text().strip() or "SimHei"
        
        self.lbl_preview.setStyleSheet(
            f"font-family: '{f_name}', sans-serif; font-size: {f_size}px; font-weight: bold; color: {pri_hex}; "
            f"background-color: #0B0E14; border: 1px dashed #30363D; border-radius: 6px; padding: 12px;"
        )

    def _select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择默认 Logo 图标/视频", "", "Media Files (*.png *.jpg *.jpeg *.mp4 *.mov *.webm)")
        if file_path:
            self.edit_logo.setText(file_path)

    def _select_broll(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择虚晃视频素材目录")
        if dir_path:
            self.edit_broll.setText(dir_path)
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "或者选择单个虚晃素材视频", "", "Videos (*.mp4 *.mov *.mkv)")
        if file_path:
            self.edit_broll.setText(file_path)

    def _on_save(self):
        self.config["global_logo_path"] = self.edit_logo.text().strip()
        self.config["logo_scale_percent"] = self.spin_logo_scale.value()
        self.config["logo_margin_right"] = self.spin_logo_mr.value()
        self.config["logo_margin_bottom"] = self.spin_logo_mb.value()
        self.config["global_broll_path"] = self.edit_broll.text().strip()
        self.config["broll_enable"] = self.chk_broll.isChecked()
        self.config["broll_chunk_min"] = self.spin_broll_min.value()
        self.config["broll_chunk_max"] = self.spin_broll_max.value()
        self.config["main_audio_volume"] = self.spin_main_vol.value()
        self.config["broll_audio_volume"] = self.spin_broll_vol.value()
        self.config["pdf_slide_duration"] = self.spin_slide_dur.value()
        self.config["cover_duration"] = self.spin_cover_dur.value()
        self.config["trim_start"] = self.spin_trim_s.value()
        self.config["trim_end"] = self.spin_trim_e.value()

        self.config["subtitle_preset"] = self.combo_sub_preset.currentData()
        self.config["subtitle_style"]["name"] = self.combo_sub_preset.currentText()
        self.config["subtitle_style"]["font_name"] = self.edit_font_name.text().strip()
        self.config["subtitle_style"]["font_size"] = self.spin_font_size.value()
        self.config["subtitle_style"]["primary_color"] = self.edit_pri_color.text().strip()
        self.config["subtitle_style"]["outline_color"] = self.edit_out_color.text().strip()
        self.config["subtitle_style"]["outline_width"] = self.spin_outline.value()
        self.config["subtitle_style"]["margin_v"] = self.spin_margin_v.value()

        # 1. 保存字幕校对引擎配置
        self.config["enable_llm_polish"] = self.chk_sub_polish.isChecked()
        sub_eng_choice = self.combo_sub_engine.currentData() or ("gemini_api" if self.combo_sub_engine.currentIndex() == 1 else "gemini_web")
        self.config["sub_llm_engine"] = sub_eng_choice
        self.config["llm_engine"] = sub_eng_choice
        
        self.config["sub_llm_key"] = self.edit_sub_key.text().strip()
        self.config["llm_api_key"] = self.edit_sub_key.text().strip()
        self.config["sub_llm_url"] = self.edit_sub_url.text().strip()
        self.config["llm_base_url"] = self.edit_sub_url.text().strip()

        sub_m = self.combo_sub_model.currentText()
        if "(" in sub_m: sub_m = sub_m.split("(")[0].strip()
        self.config["sub_llm_model"] = sub_m
        self.config["llm_model"] = sub_m

        # 2. 保存 PDF 插图对齐引擎配置
        self.config["enable_pdf_align"] = self.chk_pdf_align.isChecked()
        pdf_eng_choice = self.combo_pdf_engine.currentData() or ("gemini_api" if self.combo_pdf_engine.currentIndex() == 0 else "gemini_web" if self.combo_pdf_engine.currentIndex() == 1 else "rapid_ocr")
        self.config["pdf_align_engine"] = pdf_eng_choice

        self.config["pdf_align_key"] = self.edit_pdf_key.text().strip()
        self.config["pdf_align_url"] = self.edit_pdf_url.text().strip()

        pdf_m = self.combo_pdf_model.currentText()
        if "(" in pdf_m: pdf_m = pdf_m.split("(")[0].strip()
        self.config["pdf_align_model"] = pdf_m

        # 3. 语音与压制
        wh_txt = self.combo_whisper.currentText()
        if "(" in wh_txt: wh_txt = wh_txt.split("(")[0].strip()
        self.config["whisper_model"] = wh_txt
        self.config["whisper_device"] = self.combo_device.currentText()
        
        enc_txt = self.combo_encoder.currentText()
        if "nvenc" in enc_txt:
            self.config["video_encoder"] = "h264_nvenc"
        elif "qsv" in enc_txt:
            self.config["video_encoder"] = "h264_qsv"
        elif "amf" in enc_txt:
            self.config["video_encoder"] = "h264_amf"
        elif "libx264" in enc_txt:
            self.config["video_encoder"] = "libx264"
        else:
            self.config["video_encoder"] = "auto"

        from config import save_config
        save_config(self.config)

        self.accept()

    def get_updated_config(self) -> dict:
        return self.config
