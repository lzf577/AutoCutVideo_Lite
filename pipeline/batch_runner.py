import os
import shutil
import time
from typing import List, Optional, Callable
try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    class QThread:
        def __init__(self): pass
        def start(self): self.run()
    class _SignalMock:
        def __init__(self, *types): pass
        def emit(self, *args):
            # 控制台友好打印日志
            if args and isinstance(args[0], str) and ("▶️" in args[0] or "✅" in args[0] or "❌" in args[0] or "%" in args[0]):
                print(args[0])
    def pyqtSignal(*types):
        return _SignalMock(*types)

try:
    from pipeline.scanner import ProjectTask
    from pipeline.audio_transcriber import extract_audio, transcribe_audio_to_srt, polish_subtitles_with_llm
    from pipeline.gemini_web_polisher import polish_subtitles_with_gemini_web
    from pipeline.subtitle_corrector import auto_correct_srt
    from pipeline.pdf_extractor import extract_images_from_pdf
    from pipeline.pdf_aligner import align_pdf_slides_with_subtitles
    from pipeline.broll_manager import slice_broll_material, get_media_duration
    from pipeline.compositor import compose_final_video
except ImportError:
    from .scanner import ProjectTask
    from .audio_transcriber import extract_audio, transcribe_audio_to_srt, polish_subtitles_with_llm
    from .gemini_web_polisher import polish_subtitles_with_gemini_web
    from .subtitle_corrector import auto_correct_srt
    from .pdf_extractor import extract_images_from_pdf
    from .pdf_aligner import align_pdf_slides_with_subtitles
    from .broll_manager import slice_broll_material, get_media_duration
    from .compositor import compose_final_video

class BatchRunnerThread(QThread):
    """
    后台批量流水线执行调度器 (QThread)
    支持自动多任务流转 (流程1 -> 流程2 ...)、实时日志、进度反馈与安全终止。
    """
    # 信号定义
    log_signal = pyqtSignal(str)                       # 日志消息
    task_started_signal = pyqtSignal(int, str)         # 任务开始 (task_id, task_name)
    task_progress_signal = pyqtSignal(int, int, str)   # 任务进度 (task_id, percent, message)
    task_finished_signal = pyqtSignal(int, bool, str)  # 任务完成 (task_id, success, message)
    all_finished_signal = pyqtSignal(int, int)         # 批处理全部完成 (total_success, total_failed)

    def __init__(self, tasks: List[ProjectTask], config: dict, output_dir: str):
        super().__init__()
        self.tasks = tasks
        self.config = config
        self.output_dir = output_dir
        self._is_running = True

    def stop(self):
        """请求终止批处理"""
        self._is_running = False

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        total_success = 0
        total_failed = 0

        self.log_signal.emit(f"🚀 批处理开始，共检测到 {len(self.tasks)} 个任务待处理...")

        for task in self.tasks:
            if not self._is_running:
                self.log_signal.emit("⏹️ 批处理已被用户手动停止")
                break

            if not task.is_valid():
                task.status = "跳过"
                task.message = "缺少有效的主视频"
                self.task_finished_signal.emit(task.id, False, "缺少主视频，已跳过")
                continue

            self.task_started_signal.emit(task.id, task.name)
            self.log_signal.emit(f"\n==========================================")
            self.log_signal.emit(f"▶️ 开始执行流程任务 [{task.id}/{len(self.tasks)}]: {task.name}")
            self.log_signal.emit(f"==========================================")

            success = self._process_single_task(task)

            if success:
                total_success += 1
                task.status = "已完成"
                task.progress = 100
                task.message = "成片生成完毕"
                self.task_finished_signal.emit(task.id, True, "生成成功")
                self.log_signal.emit(f"✅ 任务 [{task.name}] 处理完成！\n")
            else:
                total_failed += 1
                task.status = "失败"
                task.message = task.error_msg or "处理失败"
                self.task_finished_signal.emit(task.id, False, task.message)
                self.log_signal.emit(f"❌ 任务 [{task.name}] 执行失败: {task.message}\n")

        self.all_finished_signal.emit(total_success, total_failed)
        self.log_signal.emit(f"🎉 批处理执行结束：成功 {total_success} 个，失败 {total_failed} 个。输出目录: {self.output_dir}")

    def _process_single_task(self, task: ProjectTask) -> bool:
        """执行单个任务的标准流水线（支持全流程断点续传与中间件缓存复用）"""
        # 1. 独立临时工作区 (保留已有缓存，支持断点继续)
        temp_dir = os.path.join(task.folder_path, "tmp_autocut")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # 校验主视频来源指纹，若主视频发生变更则自动清理旧音频与字幕缓存
            meta_src = os.path.join(temp_dir, ".video_source")
            curr_src = f"{os.path.abspath(task.video_path)}:{os.path.getsize(task.video_path)}"
            if os.path.exists(meta_src):
                with open(meta_src, "r", encoding="utf-8") as f:
                    old_src = f.read().strip()
                is_changed = True
                if old_src == curr_src:
                    is_changed = False
                elif ":" in old_src and ":" in curr_src:
                    old_p, old_s = old_src.rsplit(":", 1)
                    curr_p, curr_s = curr_src.rsplit(":", 1)
                    old_base = os.path.basename(old_p.replace("\\", "/"))
                    curr_base = os.path.basename(curr_p.replace("\\", "/"))
                    if old_base == curr_base and old_s == curr_s:
                        is_changed = False

                if is_changed:
                    self.log_signal.emit(f"🔄 检测到主视频已智能锁定为 [{os.path.basename(task.video_path)}]，自动重置旧音频缓存...")
                    for old_f in ["extracted_audio.mp3", "transcript.srt", "transcript_polished.srt"]:
                        p = os.path.join(temp_dir, old_f)
                        if os.path.exists(p):
                            try: os.remove(p)
                            except Exception: pass
            with open(meta_src, "w", encoding="utf-8") as f:
                f.write(curr_src)

            # 校验演示 PDF 来源指纹，若 PDF 发生变更则自动清理旧幻灯片切片与时间轴对齐缓存
            meta_pdf = os.path.join(temp_dir, ".pdf_source")
            if task.pdf_path and os.path.exists(task.pdf_path):
                curr_pdf = f"{os.path.abspath(task.pdf_path)}:{os.path.getsize(task.pdf_path)}"
                is_pdf_changed = True
                if os.path.exists(meta_pdf):
                    with open(meta_pdf, "r", encoding="utf-8") as f:
                        old_pdf = f.read().strip()
                    if old_pdf == curr_pdf:
                        is_pdf_changed = False
                    elif ":" in old_pdf and ":" in curr_pdf:
                        old_p, old_s = old_pdf.rsplit(":", 1)
                        curr_p, curr_s = curr_pdf.rsplit(":", 1)
                        if os.path.basename(old_p) == os.path.basename(curr_p) and old_s == curr_s:
                            is_pdf_changed = False
                if is_pdf_changed:
                    self.log_signal.emit(f"🔄 检测到演示幻灯片 PDF 已更新或变更 [{os.path.basename(task.pdf_path)}]，自动重置旧幻灯片与对齐缓存...")
                    slides_dir = os.path.join(temp_dir, "slides")
                    if os.path.exists(slides_dir):
                        shutil.rmtree(slides_dir, ignore_errors=True)
                    align_json = os.path.join(temp_dir, "slides_alignment.json")
                    if os.path.exists(align_json):
                        try: os.remove(align_json)
                        except Exception: pass
                with open(meta_pdf, "w", encoding="utf-8") as f:
                    f.write(curr_pdf)

            # 步骤 1: 提取或装载母带音频 (10%)
            if not self._is_running: return False
            self.task_progress_signal.emit(task.id, 10, "正在提取或装载母带音频...")
            temp_audio = os.path.join(temp_dir, "extracted_audio.mp3")
            if task.audio_path and os.path.exists(task.audio_path):
                self.log_signal.emit(f"⚡ [10%] 优先装载高清解说母带音频 [{os.path.basename(task.audio_path)}] (EdgeTTS原生直通)...")
                ffmpeg = get_ffmpeg_exe()
                cmd = [ffmpeg, "-y", "-i", task.audio_path, "-vn", "-c:a", "libmp3lame", "-q:a", "2", "-ar", "48000", "-ac", "2", temp_audio]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024:
                self.log_signal.emit("⚡ [10%] 命中缓存: 发现已提取的音频 (extracted_audio.mp3)，跳过提取")
            else:
                t_start = float(self.config.get("trim_start", 0.0))
                t_end = float(self.config.get("trim_end", 0.0))
                if not extract_audio(task.video_path, temp_audio, trim_start=t_start, trim_end=t_end, progress_cb=self.log_signal.emit):
                    task.error_msg = "提取原视频音频失败"
                    return False

            # 步骤 2: Whisper 语音转字幕 (25%)
            if not self._is_running: return False
            self.task_progress_signal.emit(task.id, 25, "语音转写生成字幕中...")
            srt_path = os.path.join(temp_dir, "transcript.srt")
            if os.path.exists(srt_path) and os.path.getsize(srt_path) > 30:
                self.log_signal.emit("⚡ [25%] 命中缓存: 发现已有字幕文件 (transcript.srt)，跳过 Whisper 重复识别")
            else:
                whisper_model = self.config.get("whisper_model", "small")
                whisper_device = self.config.get("whisper_device", "auto")
                whisper_lang = self.config.get("whisper_language", "zh")

                srt_path, subs = transcribe_audio_to_srt(
                    temp_audio,
                    srt_path,
                    model_name=whisper_model,
                    device=whisper_device,
                    language=whisper_lang,
                    progress_cb=self.log_signal.emit
                )

            # 可选: LLM 字幕错别字校对 (45%)
            if self.config.get("enable_llm_polish", True):
                if not self._is_running: return False
                self.task_progress_signal.emit(task.id, 45, "字幕错别字智能校对中...")
                polished_srt = os.path.join(temp_dir, "transcript_polished.srt")
                if os.path.exists(polished_srt) and os.path.getsize(polished_srt) > 30:
                    self.log_signal.emit("⚡ [45%] 命中缓存: 发现已有大模型校对字幕 (transcript_polished.srt)，跳过校对")
                    srt_path = polished_srt
                else:
                    sub_eng = self.config.get("sub_llm_engine", self.config.get("llm_engine", "gemini_web"))
                    sub_key = self.config.get("sub_llm_key", self.config.get("llm_api_key", "")).strip()
                    
                    if sub_eng == "gemini_web" or not sub_key:
                        # 使用 Gemini 网页版静默校对 (免Key / 0费用)
                        srt_path = polish_subtitles_with_gemini_web(
                            srt_path,
                            polished_srt,
                            headless=True,
                            progress_cb=self.log_signal.emit
                        )
                    else:
                        # 使用官方 API 接口
                        sub_model = self.config.get("sub_llm_model", self.config.get("llm_model", "gemini-2.5-flash"))
                        if "(" in sub_model: sub_model = sub_model.split("(")[0].strip()
                        srt_path = polish_subtitles_with_llm(
                            srt_path,
                            polished_srt,
                            api_key=sub_key,
                            base_url=self.config.get("sub_llm_url", "https://generativelanguage.googleapis.com/v1beta/openai/"),
                            model_name=sub_model,
                            progress_cb=self.log_signal.emit
                        )

            # 步骤 2.5: 长期持久化字幕自动纠错与剧本真值咬合 (50%)
            if not self._is_running: return False
            self.task_progress_signal.emit(task.id, 50, "执行剧本真值咬合与专业术语纠错中...")
            try:
                auto_correct_srt(srt_path, progress_cb=self.log_signal.emit)
            except Exception as e_corr:
                self.log_signal.emit(f"⚠️ [持久化校对告警] 自动校准跳过 ({e_corr})，继续使用现有字幕")

            # 步骤 3: 提取/装载幻灯片图片与智能语义插图对齐 (55% -> 65%)
            slide_images = []
            
            # 1. 优先直读分集目录下的 slides/ 文件夹 (完全脱离 PDF，零额外开销)
            direct_slides_dir = os.path.join(task.folder_path, "slides")
            if os.path.isdir(direct_slides_dir):
                direct_slides = [
                    os.path.join(direct_slides_dir, f)
                    for f in sorted(os.listdir(direct_slides_dir))
                    if f.lower().endswith(('.png', '.jpg', '.jpeg'))
                ]
                if direct_slides:
                    slide_images = direct_slides
                    self.log_signal.emit(f"⚡ [55%] 发现直接生成的竖版原画课件 ({len(slide_images)} 张)，免 PDF 提取直接装载！")

            # 2. 若无直接原画，则回退兼容 task.pdf_path
            if not slide_images and task.pdf_path and os.path.exists(task.pdf_path):
                if not self._is_running: return False
                self.task_progress_signal.emit(task.id, 55, "解析 PDF 幻灯片图片中...")
                pdf_out_dir = os.path.join(temp_dir, "slides")
                if os.path.exists(pdf_out_dir):
                    existing_slides = [
                        os.path.join(pdf_out_dir, f)
                        for f in sorted(os.listdir(pdf_out_dir))
                        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
                    ]
                    if existing_slides:
                        slide_images = existing_slides
                        self.log_signal.emit(f"⚡ [55%] 命中缓存: 发现已有幻灯片图片 ({len(slide_images)} 张)，跳过 PDF 提取")
                
                if not slide_images:
                    dpi = int(self.config.get("pdf_dpi", 150))
                    slide_images = extract_images_from_pdf(
                        task.pdf_path,
                        pdf_out_dir,
                        dpi=dpi,
                        progress_cb=self.log_signal.emit
                    )

            # 3. 幻灯片智能语义时间轴对齐
            if slide_images and self.config.get("enable_pdf_align", True):
                if not self._is_running: return False
                self.task_progress_signal.emit(task.id, 62, "幻灯片语义时间轴对齐中...")
                pdf_model = self.config.get("pdf_align_model", "gemini-2.5-flash")
                if "(" in pdf_model: pdf_model = pdf_model.split("(")[0].strip()
                
                slide_dur = float(self.config.get("pdf_slide_duration", 10.0))
                aligned = align_pdf_slides_with_subtitles(
                    image_paths=slide_images,
                    srt_path=srt_path,
                    pdf_path=task.pdf_path or "",
                    engine=self.config.get("pdf_align_engine", "gemini_api"),
                    api_key=self.config.get("pdf_align_key", self.config.get("llm_api_key", "")),
                    base_url=self.config.get("pdf_align_url", "https://generativelanguage.googleapis.com/v1beta/openai/"),
                    model_name=pdf_model,
                    slide_duration=slide_dur,
                    progress_cb=self.log_signal.emit
                )
                if aligned:
                    slide_images = aligned

            # 步骤 4: 准备虚晃空镜素材切片 (68%)
            broll_slices = []
            broll_source = task.broll_path or self.config.get("global_broll_path", "")
            if broll_source and os.path.exists(broll_source) and self.config.get("broll_enable", True):
                if not self._is_running: return False
                self.task_progress_signal.emit(task.id, 68, "切分虚晃素材镜头...")
                broll_dir = os.path.join(temp_dir, "broll_cuts")
                if os.path.exists(broll_dir):
                    existing_brolls = [
                        os.path.join(broll_dir, f)
                        for f in sorted(os.listdir(broll_dir))
                        if f.lower().endswith(('.mp4', '.mov', '.mkv'))
                    ]
                    if existing_brolls:
                        broll_slices = existing_brolls
                        self.log_signal.emit(f"⚡ [68%] 命中缓存: 发现已有虚晃镜头切片 ({len(broll_slices)} 个)，跳过切片")

                if not broll_slices:
                    total_dur = get_media_duration(task.video_path)
                    if total_dur <= 0.5 and srt_path and os.path.exists(srt_path):
                        try:
                            import re
                            with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                srt_txt = f.read()
                            ts_m = re.findall(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', srt_txt)
                            if ts_m:
                                l_ts = ts_m[-1]
                                total_dur = float(l_ts[0]) * 3600 + float(l_ts[1]) * 60 + float(l_ts[2]) + float(l_ts[3]) / 1000.0
                        except Exception:
                            pass
                    if total_dur <= 0.5:
                        total_dur = 300.0
                    broll_slices = slice_broll_material(
                        broll_source,
                        broll_dir,
                        needed_total_duration=max(60.0, total_dur * 0.4),
                        min_chunk=float(self.config.get("broll_chunk_min", 4.0)),
                        max_chunk=float(self.config.get("broll_chunk_max", 8.0)),
                        progress_cb=self.log_signal.emit
                    )

            # 步骤 5: 确定 Logo 与 封面 (75%)
            enable_logo = self.config.get("enable_logo", False)
            logo_path = (task.logo_path or self.config.get("global_logo_path", "")) if enable_logo else None
            if not enable_logo:
                self.log_signal.emit("⚪ [Logo策略] 已禁用角标 Logo (纯净原画无遮挡模式)")
            cover_path = task.cover_path or self.config.get("global_cover_template", "")

            # 步骤 6: FFmpeg 极速多层压制成片 (80% -> 100%)
            if not self._is_running: return False
            self.task_progress_signal.emit(task.id, 80, "极速压制合成最终成片...")
            final_output_name = f"{task.name}_成片.mp4"
            
            # 智能输出目录选择：自定义输出目录 -> 全局批处理output -> 任务自身output
            if self.config.get("custom_output_dir", "").strip():
                task_out_dir = self.config.get("custom_output_dir").strip()
            elif self.output_dir and os.path.isdir(self.output_dir):
                task_out_dir = self.output_dir
            else:
                task_out_dir = os.path.join(task.folder_path, "output")

            os.makedirs(task_out_dir, exist_ok=True)
            final_output_path = os.path.join(task_out_dir, final_output_name)
            task.output_video_path = final_output_path

            render_ok = compose_final_video(
                base_video_path=task.video_path,
                audio_track_path=temp_audio,
                srt_path=srt_path,
                output_path=final_output_path,
                slide_images=slide_images,
                broll_slices=broll_slices,
                logo_path=logo_path,
                cover_path=cover_path,
                config=self.config,
                temp_dir=os.path.join(temp_dir, "render"),
                progress_cb=self.log_signal.emit
            )

            if not render_ok:
                task.error_msg = "FFmpeg 合成压制失败"
                return False

            # 清理渲染临时目录 (保留字幕和图片切片缓存)
            render_temp = os.path.join(temp_dir, "render")
            try:
                if os.path.exists(render_temp):
                    shutil.rmtree(render_temp, ignore_errors=True)
            except Exception:
                pass

            return True

        except Exception as e:
            task.error_msg = str(e)
            self.log_signal.emit(f"💥 发生未捕获异常: {e}")
            return False
