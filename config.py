import os
import json
import sys


def get_app_dir() -> str:
    """获取程序实际所在工作目录（支持 PyInstaller 单文件打包与源码运行）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_app_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

SUBTITLE_PRESETS = {
    "sports_yellow": {
        "name": "🟡 体育解说·经典明黄（高辨识度/推荐）",
        "font_name": "SimHei",
        "font_size": 24,
        "primary_color": "&H0000FFFF",  # 鲜亮明黄
        "outline_color": "&H00000000",  # 纯黑描边
        "outline_width": 2,
        "margin_v": 45,
        "bold": 1
    },
    "knowledge_white": {
        "name": "⚪ 知识科普·极简纯白（沉稳典雅）",
        "font_name": "SimHei",
        "font_size": 22,
        "primary_color": "&H00FFFFFF",  # 纯白
        "outline_color": "&H00000000",  # 纯黑描边
        "outline_width": 2,
        "margin_v": 50,
        "bold": 1
    },
    "short_video_orange": {
        "name": "🟠 爆款短视频·活力金橙（吸睛冲击）",
        "font_name": "SimHei",
        "font_size": 26,
        "primary_color": "&H0000A5FF",  # 活力金橙
        "outline_color": "&H00000000",  # 深黑描边
        "outline_width": 3,
        "margin_v": 40,
        "bold": 1
    },
    "cyber_cyan": {
        "name": "🔵 科技数码·极客荧光青（未来前沿）",
        "font_name": "SimHei",
        "font_size": 23,
        "primary_color": "&H00FFFF00",  # 荧光青蓝 (BGR: &H00FFFF00)
        "outline_color": "&H00201010",  # 深深色边
        "outline_width": 2,
        "margin_v": 45,
        "bold": 1
    },
    "cinema_mint": {
        "name": "🟢 影视解说·清爽薄荷绿（悬疑故事）",
        "font_name": "SimHei",
        "font_size": 24,
        "primary_color": "&H0060FF60",  # 薄荷浅绿
        "outline_color": "&H00000000",  # 纯黑边
        "outline_width": 2,
        "margin_v": 45,
        "bold": 1
    },
    "movie_silver": {
        "name": "🎬 院线大片·电影银白（艺术留白）",
        "font_name": "SimHei",
        "font_size": 21,
        "primary_color": "&H00E8E8E8",  # 银灰白
        "outline_color": "&H00000000",  # 细微黑边
        "outline_width": 1,
        "margin_v": 70,
        "bold": 0
    },
    "capsule_black": {
        "name": "🖤 纪实专栏·高对比粗黑描边（强穿透）",
        "font_name": "SimHei",
        "font_size": 24,
        "primary_color": "&H00FFFFFF",  # 纯白
        "outline_color": "&H00151515",  # 粗黑底框
        "outline_width": 4,
        "margin_v": 45,
        "bold": 1
    }
}

DEFAULT_SUBTITLE_STYLE = SUBTITLE_PRESETS["sports_yellow"].copy()

DEFAULT_CONFIG = {
    # 路径与目录
    "last_batch_dir": "",
    "custom_output_dir": "",
    "global_logo_path": "",
    "global_broll_path": "",
    "global_cover_template": "",
    
    # Logo 水印配置 (默认 0 紧贴完全右下角对齐)
    "logo_margin_right": 0,
    "logo_margin_bottom": 0,
    "logo_scale_percent": 12,  # 相对视频宽度的百分比
    "logo_opacity": 0.9,
    
    # 虚晃空镜 (B-Roll) 配置
    "broll_enable": True,
    "broll_chunk_min": 8.0,
    "broll_chunk_max": 15.0,
    "broll_interval_min": 12.0,
    
    # 双音轨智能混音与音量百分比 (0~200%)
    "main_audio_volume": 100,    # 主视频/解说声音量百分比 (默认100%)
    "broll_audio_volume": 20,    # 虚晃切片素材自带音量百分比 (默认20%背景氛围音，0为纯静音)
    
    # PDF 幻灯片图片插入配置
    "pdf_slide_duration": 10.0,  # 默认每页幻灯片展示时长（秒）
    "pdf_dpi": 150,
    
    # 剪裁与去头尾配置 (秒)
    "trim_start": 0.0,
    "trim_end": 3.0,
    
    # 封面配置
    "cover_duration": 1.0,     # 片头封面停留秒数
    
    # Whisper 语音识别配置
    "whisper_model": "base",   # base (极速推荐), small, tiny, medium, large-v3
    "whisper_device": "auto",  # auto, cuda, cpu
    "whisper_language": "zh",
    
    # 1. 字幕智能纠错引擎配置 (Subtitle Polish Engine)
    "enable_llm_polish": True,
    "sub_llm_engine": "gemini_web", # gemini_web (网页版免Key), gemini_api (官方API)
    "sub_llm_key": "",
    "sub_llm_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "sub_llm_model": "🔄 自动多Key/7大模型智能轮询",
    # 兼容老字段别名
    "llm_engine": "gemini_web",
    "llm_api_key": "",
    "llm_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "llm_model": "🔄 自动多Key/7大模型智能轮询",

    # 2. PDF 幻灯片智能对齐插图引擎配置 (PDF Slide Alignment Engine)
    "enable_pdf_align": True,
    "pdf_align_engine": "gemini_api", # gemini_api (API语义对齐), gemini_web (网页版对齐), rapid_ocr (离线关键词对齐)
    "pdf_align_key": "",
    "pdf_align_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "pdf_align_model": "🔄 自动多Key/7大模型智能轮询",
    
    # 编码器与字幕预设
    "video_encoder": "auto",
    "video_crf": 23,
    "video_preset": "veryfast",
    "subtitle_preset": "sports_yellow",
    "subtitle_style": DEFAULT_SUBTITLE_STYLE
}

def get_ffmpeg_exe() -> str:
    """获取可用的 ffmpeg 可执行文件路径 (支持 Linux 原生硬件加速优先与跨平台自愈)"""
    import shutil
    # 1. Linux 环境下优先使用系统原生 ffmpeg (确保支持 QSV / VA-API 硬件编解码)
    if sys.platform.startswith('linux'):
        w = shutil.which("ffmpeg")
        if w and os.path.exists(w):
            return w

    # 2. 优先尝试 imageio_ffmpeg (Windows 静态通用兜底)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(exe):
            return exe
    except ImportError:
        pass
    except Exception:
        pass

    # 3. 尝试 PyInstaller 打包临时解压目录
    if getattr(sys, 'frozen', False):
        base_app_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        for root, dirs, files in os.walk(base_app_dir):
            for f in files:
                if f.lower().startswith("ffmpeg") and f.lower().endswith(".exe"):
                    return os.path.join(root, f)

    # 4. 尝试当前程序所在目录及子目录
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for root, dirs, files in os.walk(app_dir):
        for f in files:
            if f.lower() == "ffmpeg.exe":
                return os.path.join(root, f)

    # 5. 尝试系统 PATH
    w = shutil.which("ffmpeg")
    if w and os.path.exists(w):
        return w
    return "ffmpeg"

def get_ffprobe_exe() -> str:
    """获取可用的 ffprobe 可执行文件路径"""
    import shutil
    w = shutil.which("ffprobe")
    if w and os.path.exists(w):
        return w
    ffmpeg = get_ffmpeg_exe()
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    if os.path.exists(ffprobe):
        return ffprobe
    return "ffprobe"

def load_config() -> dict:
    """加载配置：默认配置 -> 读取 config.json 用户保存的配置（最高优先级）"""
    config = DEFAULT_CONFIG.copy()

    # 读取用户保存的 config.json (最高优先级)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
                if "subtitle_style" in saved:
                    style = DEFAULT_SUBTITLE_STYLE.copy()
                    if isinstance(config.get("subtitle_style"), dict):
                        style.update(config["subtitle_style"])
                    style.update(saved["subtitle_style"])
                    config["subtitle_style"] = style
        except Exception as e:
            print(f"[Config] 加载配置文件失败: {e}")

    return config

def save_config(config: dict):
    """保存配置到本地 json 文件，确保用户修改绝对持久化"""
    target_files = [CONFIG_FILE]
    
    # 兼容: 如果在 dist/ 目录下运行，同时也同步一份到上级目录 (项目主目录)
    parent_cfg = os.path.join(os.path.dirname(BASE_DIR), "config.json")
    if os.path.exists(os.path.dirname(parent_cfg)) and parent_cfg not in target_files:
        target_files.append(parent_cfg)

    for cfg_p in target_files:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(cfg_p)), exist_ok=True)
            with open(cfg_p, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Config] 保存配置文件 {cfg_p} 失败: {e}")
