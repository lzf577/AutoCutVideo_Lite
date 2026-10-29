import os
import sys
import re
import subprocess
import shutil
from typing import List, Dict, Optional, Callable

try:
    from config import get_ffmpeg_exe, get_ffprobe_exe
except ImportError:
    from ..config import get_ffmpeg_exe, get_ffprobe_exe
try:
    from pipeline.broll_manager import get_media_duration
except ImportError:
    from .broll_manager import get_media_duration

def check_media_has_audio(file_path: str) -> bool:
    """检查媒体文件是否包含音频流 (支持 ffprobe 与 ffmpeg 双引擎探测)"""
    if not file_path or not os.path.exists(file_path):
        return False
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    # 1. 优先尝试 ffprobe
    try:
        import json
        ffprobe = get_ffprobe_exe()
        cmd = [ffprobe, '-v', 'error', '-show_streams', '-select_streams', 'a', '-of', 'json', file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        out_str = res.stdout.decode("utf-8", errors="ignore").strip()
        if res.returncode == 0 and out_str:
            data = json.loads(out_str)
            return len(data.get('streams', [])) > 0
    except Exception:
        pass
    # 2. 兜底尝试 ffmpeg -i
    try:
        ffmpeg = get_ffmpeg_exe()
        cmd = [ffmpeg, '-i', file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        err_str = res.stderr.decode("utf-8", errors="ignore")
        return 'Audio:' in err_str
    except Exception:
        pass
    return False

def get_hardware_accelerated_encoder(user_choice: str = "auto", config: dict = None) -> tuple[str, list]:
    """
    智能推断与选取最佳 GPU 硬件加速编码器：
    1. NVIDIA GPU: h264_nvenc
    2. Intel QuickSync: h264_qsv
    3. AMD AMF: h264_amf
    4. CPU 模式: libx264 (采用 veryfast + crf 23 平衡高质量与极致体积，节省约70%磁盘空间)
    """
    if config is None:
        config = {}
    crf = str(config.get("video_crf", 23))
    preset = str(config.get("video_preset", "veryfast"))

    ffmpeg = get_ffmpeg_exe()
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    def _test_enc(enc: str) -> bool:
        try:
            cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=duration=0.1:size=64x64:rate=25", "-c:v", enc, "-f", "null", "-"]
            return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags).returncode == 0
        except Exception:
            return False

    choice = str(user_choice).lower().strip()
    if "nvenc" in choice and _test_enc("h264_nvenc"):
        return "NVIDIA NVENC (GPU加速)", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "24"]
    if "qsv" in choice and _test_enc("h264_qsv"):
        return "Intel QuickSync QSV (GPU加速)", ["-c:v", "h264_qsv", "-preset", "fast", "-global_quality", "24"]
    if "amf" in choice and _test_enc("h264_amf"):
        return "AMD AMF (GPU加速)", ["-c:v", "h264_amf", "-quality", "balanced"]
    if "264" in choice or "cpu" in choice:
        return f"CPU (libx264 均衡压缩 preset={preset}, crf={crf})", ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-threads", "4"]

    # 自动探测 (Auto Mode: NVIDIA -> Intel QSV -> AMD AMF -> CPU)
    if _test_enc("h264_nvenc"):
        return "NVIDIA NVENC (GPU加速)", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "24"]
    if _test_enc("h264_qsv"):
        return "Intel QuickSync QSV (GPU加速)", ["-c:v", "h264_qsv", "-preset", "fast", "-global_quality", "24"]
    if _test_enc("h264_amf"):
        return "AMD AMF (GPU加速)", ["-c:v", "h264_amf", "-quality", "balanced"]

    return f"CPU (libx264 均衡压缩 preset={preset}, crf={crf})", ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-threads", "4"]

def build_subtitle_filter_style(style_dict: dict, is_vertical: bool = False) -> str:
    """构建 FFmpeg subtitles 滤镜的 force_style 参数 (支持竖屏短视频自适应大字与防遮挡定位)"""
    font_name = style_dict.get("font_name", "SimHei")
    default_size = 38 if is_vertical else 24
    default_margin_v = 180 if is_vertical else 40
    font_size = style_dict.get("font_size", default_size)
    if is_vertical and font_size < 30:
        font_size = 38  # 竖屏短视频确保大字清晰易读
    primary_color = style_dict.get("primary_color", "&H0000FFFF")
    outline_color = style_dict.get("outline_color", "&H00000000")
    outline_width = style_dict.get("outline_width", 3 if is_vertical else 2)
    margin_v = style_dict.get("margin_v", default_margin_v)
    if is_vertical and margin_v < 100:
        margin_v = 180  # 竖屏底部避开抖音/小红书/视频号操作栏
    bold = style_dict.get("bold", 1)
    
    return (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour={primary_color},"
        f"OutlineColour={outline_color},"
        f"Outline={outline_width},"
        f"Shadow=0,"
        f"MarginV={margin_v},"
        f"Bold={bold},"
        f"Alignment=2"
    )

def _run_ffmpeg_with_progress(
    cmd: list,
    cwd: str,
    total_duration: float,
    phase_name: str,
    creation_flags: int,
    progress_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """带真正秒级实时进度监控的 FFmpeg 执行器 (支持 \\r 回车符动态流式刷新，彻底解决长视频看似卡住的问题)"""
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creation_flags
    )

    time_pattern = re.compile(r'time=(\d{2}:\d{2}:\d{2}\.\d+)')
    last_reported_pct = -1
    err_lines = []
    buffer = ""

    while True:
        chunk = proc.stderr.read(128)
        if not chunk and proc.poll() is not None:
            break
        if chunk:
            text = chunk.decode("utf-8", errors="replace")
            buffer += text
            
            while '\r' in buffer or '\n' in buffer:
                idx_r = buffer.find('\r')
                idx_n = buffer.find('\n')
                if idx_r != -1 and idx_n != -1:
                    split_idx = min(idx_r, idx_n)
                elif idx_r != -1:
                    split_idx = idx_r
                else:
                    split_idx = idx_n
                
                line = buffer[:split_idx].strip()
                buffer = buffer[split_idx + 1:]
                
                if line:
                    err_lines.append(line)
                    m = time_pattern.search(line)
                    if m:
                        t_str = m.group(1)
                        parts = t_str.split(':')
                        curr_sec = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                        pct = min(99, int((curr_sec / max(1.0, total_duration)) * 100))
                        if pct > last_reported_pct and (pct % 3 == 0 or pct >= 95 or pct <= 5):
                            last_reported_pct = pct
                            if progress_cb:
                                total_min = int(total_duration // 60)
                                total_sec = int(total_duration % 60)
                                progress_cb(f"⚡ [{phase_name} {pct}%] 极速渲染中: {t_str.split('.')[0]} / {total_min:02d}:{total_sec:02d} (进度 {pct}%)")

    proc.wait()

    if proc.returncode != 0:
        err_str = "\n".join(err_lines[-12:])
        print(f"[FFmpeg {phase_name} Error]: {err_str}")
        if progress_cb:
            progress_cb(f"❌ {phase_name} 失败 (错误码 {proc.returncode}): {err_str.strip()[:200]}")
        return False

    return True



def compose_final_video(
    base_video_path: str,
    srt_path: str,
    output_path: str,
    audio_track_path: Optional[str] = None,
    slide_images: Optional[List[str]] = None,
    broll_slices: Optional[List[str]] = None,
    logo_path: Optional[str] = None,
    cover_path: Optional[str] = None,
    config: Optional[dict] = None,
    temp_dir: Optional[str] = None,
    progress_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """
    两阶段高鲁棒性极速合成架构 (支持竖屏 9:16、EdgeTTS母带音轨直通与高燃比赛切片紧密穿插)：
    - 阶段一（画面层）：竖屏原画课件 + 比赛高燃视频切片 + 封面 -> 生成中间视频
    - 阶段二（字幕层）：独立纯净压制 ASS/SRT 大字字幕 -> 生成最终成片
    """
    if config is None:
        config = {}

    if temp_dir is None:
        temp_dir = os.path.join(os.path.dirname(output_path), "tmp_render")
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    ffmpeg = get_ffmpeg_exe()
    creation_flags = 0
    if os.name == 'nt':
        creation_flags = subprocess.CREATE_NO_WINDOW

    # 优先从主解说音频中探测真实时长 (EdgeTTS 原生驱动)
    raw_duration = 0.0
    if audio_track_path and os.path.exists(audio_track_path):
        raw_duration = get_media_duration(audio_track_path)
    if raw_duration <= 0.5 and base_video_path and os.path.exists(base_video_path):
        raw_duration = get_media_duration(base_video_path)
    # 若无法通过主音频/视频探测时长，尝试从字幕文件解析最大时间戳作为备选兜底
    if raw_duration <= 0.5 and srt_path and os.path.exists(srt_path):
        try:
            with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            ts_matches = re.findall(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', content)
            if ts_matches:
                last_ts = ts_matches[-1]
                raw_duration = float(last_ts[0]) * 3600 + float(last_ts[1]) * 60 + float(last_ts[2]) + float(last_ts[3]) / 1000.0 + 3.0
        except Exception:
            pass

    if raw_duration <= 0.5:
        if progress_cb:
            progress_cb("❌ 音视频时长探测异常 (时长为 0)，无法合成")
        return False

    trim_start = float(config.get("trim_start", 0.0))
    trim_end = float(config.get("trim_end", 0.0))
    total_duration = max(1.0, raw_duration - trim_start - trim_end)

    if total_duration <= 0.5:
        if progress_cb:
            progress_cb("❌ 剪辑后有效时长异常，无法合成")
        return False

    if progress_cb:
        if trim_start > 0 or trim_end > 0:
            progress_cb(f"🎬 开始构建合成流水线 (母带原长: {raw_duration:.1f}s, 去头{trim_start}s/去尾{trim_end}s -> 成片时长: {total_duration:.1f}s)...")
        else:
            progress_cb(f"🎬 开始构建合成流水线 (成片总时长: {total_duration:.1f}s)...")

    # ─────────────────────────────────────────────────────────
    # 广播级三层视听合成架构 (Broadcasting 3-Layer Engine)
    # 层1 (底层)：高清横屏转竖屏比赛实况背景 (1080x1920，时长不足智能循环，赛场原声 50%)
    # 层2 (主声)：老法师量化分析母带解说音频 (100% 洪亮清晰)
    # 层3 (顶层)：赛事直播级全息动态数据课件 (淡入/滑入/升起/微旋/缩放动态转场)
    # ─────────────────────────────────────────────────────────

    bg_duration = get_media_duration(base_video_path)
    if bg_duration <= 0.5:
        bg_duration = 120.0  # 兜底假设背景素材至少 2 分钟

    has_bg_audio = check_media_has_audio(base_video_path)
    bg_vol = float(config.get("broll_audio_volume", 50)) / 100.0  # 用户指定：赛场原声 50%

    # 1. 毫秒级生成双层母带混音轨 (Layer 1 赛场原声 50% + Layer 2 解说母带 100%)
    temp_audio_name = "master_audio_track.m4a"
    temp_audio_path = os.path.join(temp_dir, temp_audio_name)

    enc_choice = config.get("video_encoder", "auto")
    enc_name, enc_args = get_hardware_accelerated_encoder(enc_choice, config=config)
    if progress_cb:
        progress_cb(f"🚀 已自动激活编码引擎: {enc_name} (广播级三层动态视听架构)")

    if progress_cb:
        progress_cb(f"🎧 [双层混音] 正在融合音频: 赛场实况原声({int(bg_vol*100)}%) + 专家解说母带(100%)...")

    if audio_track_path and os.path.exists(audio_track_path) and has_bg_audio and bg_vol > 0.01:
        # 双音轨完美立体声 amix 融合
        cmd_mix_audio = [
            ffmpeg, "-y",
            "-stream_loop", "-1",
            "-ss", f"{trim_start:.3f}",
            "-t", f"{total_duration:.3f}",
            "-i", os.path.abspath(base_video_path),
            "-ss", "0",
            "-t", f"{total_duration:.3f}",
            "-i", os.path.abspath(audio_track_path),
            "-filter_complex",
            f"[0:a]volume={bg_vol:.2f}[a_bg];[1:a]volume=1.00[a_voice];[a_bg][a_voice]amix=inputs=2:duration=first:dropout_transition=0[a_mix]",
            "-map", "[a_mix]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            temp_audio_name
        ]
    elif audio_track_path and os.path.exists(audio_track_path):
        # 仅有母带音频 (无背景音或背景音音量为0)
        cmd_mix_audio = [
            ffmpeg, "-y",
            "-i", os.path.abspath(audio_track_path),
            "-t", f"{total_duration:.3f}",
            "-vn",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            temp_audio_name
        ]
    else:
        # 回退仅提取主视频音频
        cmd_mix_audio = [
            ffmpeg, "-y",
            "-stream_loop", "-1",
            "-ss", f"{trim_start:.3f}",
            "-t", f"{total_duration:.3f}",
            "-i", os.path.abspath(base_video_path),
            "-vn",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            temp_audio_name
        ]
    subprocess.run(cmd_mix_audio, cwd=temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)

    # 2. 编排广播级插图出现时间表与动态转场动画 (Layer 3 Animation Schedule)
    # 转场风格库（模仿 ESPN/SkySports 体育直播包装系统）：
    # 0: slide_left (从屏幕左侧平滑飞入、向右滑出)
    # 1: zoom (全息微缩放弹性弹入)
    # 2: slide_bottom (底部数据牌升起、回落)
    # 3: rotate (3D 微角度旋转倾斜归位)
    # 4: fade (优雅高斯淡入淡出)
    TRANSITION_STYLES = ["slide_left", "zoom", "slide_bottom", "rotate", "fade"]

    schedule = []
    target_slide_dur = float(config.get("pdf_slide_duration", 7.0))
    if target_slide_dur <= 0:
        target_slide_dur = 7.0

    if slide_images:
        num_slides = len(slide_images)
        if isinstance(slide_images[0], dict):
            sorted_slides = sorted(slide_images, key=lambda x: float(x.get("start_time", 0.0)))
            for i, s_info in enumerate(sorted_slides):
                img_p = s_info.get("image_path") or s_info.get("path") or ""
                # 跨平台路径自适应
                if img_p and not os.path.exists(img_p):
                    base_n = os.path.basename(img_p.replace("\\", "/"))
                    candidates = [
                        os.path.join(temp_dir, "slides", base_n),
                        os.path.join(os.path.dirname(temp_dir), "slides", base_n),
                        os.path.join(os.path.dirname(base_video_path), "slides", base_n),
                        os.path.join(os.path.dirname(base_video_path), "tmp_autocut", "slides", base_n)
                    ]
                    for cp in candidates:
                        if os.path.exists(cp):
                            img_p = os.path.abspath(cp)
                            break

                st = max(0.0, float(s_info.get("start_time", 0.0)))
                next_st = float(sorted_slides[i+1].get("start_time", total_duration)) if i+1 < len(sorted_slides) else total_duration
                gap_to_next = max(0.5, next_st - st)

                if gap_to_next >= 10.0:
                    slide_dur = target_slide_dur
                elif gap_to_next >= 5.0:
                    slide_dur = max(3.0, round(gap_to_next * 0.55, 2))
                else:
                    slide_dur = max(2.0, round(gap_to_next - 0.5, 2))

                slide_et = min(total_duration - 0.2, round(st + slide_dur, 2))
                if img_p and os.path.exists(img_p) and slide_et > st + 0.5:
                    anim_style = TRANSITION_STYLES[i % len(TRANSITION_STYLES)]
                    schedule.append({
                        "type": "image",
                        "path": img_p,
                        "start": round(st, 2),
                        "end": slide_et,
                        "style": anim_style
                    })
        else:
            step = total_duration / (num_slides + 1)
            for i, s_img in enumerate(slide_images):
                s_start = max(1.0, (i + 1) * step - (target_slide_dur / 2.0))
                s_end = min(total_duration - 1.0, s_start + target_slide_dur)
                if s_end > s_start + 1.0:
                    anim_style = TRANSITION_STYLES[i % len(TRANSITION_STYLES)]
                    schedule.append({
                        "type": "image",
                        "path": s_img,
                        "start": round(s_start, 2),
                        "end": round(s_end, 2),
                        "style": anim_style
                    })

    schedule.sort(key=lambda x: x["start"])
    if progress_cb:
        progress_cb(f"📋 [直播级排期完成] 本片成功编排: {len(schedule)} 页全息动态数据课件，深度结合 1080x1920 竖屏赛事实况！")

    # 3. 构造时间轴严格互斥的分段渲染序列 (Timeline Slices)
    seg_dir = os.path.join(temp_dir, "segs")
    os.makedirs(seg_dir, exist_ok=True)

    curr_t = 0.0
    slices = []
    for item in schedule:
        item_st = max(curr_t, min(total_duration, float(item["start"])))
        item_et = max(item_st, min(total_duration, float(item["end"])))

        # (A) 插片前的纯实况视频间隙 (Pure Match Action)
        if item_st > curr_t + 0.05:
            dur = item_st - curr_t
            slices.append({
                "type": "base",
                "ss_bg": (trim_start + curr_t) % bg_duration,
                "dur": dur
            })

        # (B) 带有赛事直播包装动画的插图片段 (Dynamic Slide Overlay)
        if item_et > item_st + 0.05:
            dur = item_et - item_st
            slices.append({
                "type": "image",
                "path": item["path"],
                "style": item.get("style", "fade"),
                "ss_bg": (trim_start + item_st) % bg_duration,
                "dur": dur
            })

        curr_t = item_et

    # (C) 末尾纯实况视频间隙
    if curr_t < total_duration - 0.05:
        slices.append({
            "type": "base",
            "ss_bg": (trim_start + curr_t) % bg_duration,
            "dur": total_duration - curr_t
        })

    # 若没有任何插图，则整体作为一段基础实况
    if not slices:
        slices.append({
            "type": "base",
            "ss_bg": trim_start % bg_duration,
            "dur": total_duration
        })

    total_slices = len(slices)
    seg_files = []

    # 广播级高斯模糊填充背景滤镜 (16:9 横屏转 9:16 竖屏超感画质，采用低分辨率模糊再放大极速算法)
    v_base_filter = (
        "[0:v]split=2[v_bg_raw][v_fg_raw];"
        "[v_bg_raw]scale=270:480,boxblur=15:3,scale=1080:1920[v_bg];"
        "[v_fg_raw]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:0x00000000[v_fg];"
        "[v_bg][v_fg]overlay=0:0"
    )

    temp_visual_name = "temp_visual_track.mp4"
    temp_visual_path = os.path.join(temp_dir, temp_visual_name)

    if progress_cb:
        progress_cb(f"⚡ [极速分段渲染] 开始渲染 {total_slices} 个赛事直播多层视觉分段 (零内存堆积)...")

    for s_idx, sl in enumerate(slices):
        seg_fname = f"seg_{s_idx:04d}.mp4"
        seg_fpath = os.path.join(seg_dir, seg_fname)
        seg_files.append(seg_fpath)

        dur = sl["dur"]
        ss_bg = sl["ss_bg"]

        if sl["type"] == "base":
            # 纯实况镜头：底层横屏比赛视频转为 1080x1920 竖屏
            cmd_seg = [
                ffmpeg, "-y",
                "-stream_loop", "-1",
                "-ss", f"{ss_bg:.3f}",
                "-t", f"{dur:.3f}",
                "-i", os.path.abspath(base_video_path),
                "-filter_complex", f"{v_base_filter}[v_out]",
                "-map", "[v_out]",
                "-an",
                *enc_args,
                "-pix_fmt", "yuv420p",
                seg_fpath
            ]
        else:
            # 动态插图卡片：底层比赛实况 + 顶层直播级动画转场
            anim = sl.get("style", "fade")
            card_p = os.path.abspath(sl["path"])

            if anim == "slide_left":
                # 左侧平滑滑入，静止后向右滑出
                anim_filter = (
                    f"{v_base_filter}[v_base];"
                    f"[1:v]scale=1080:1920,fade=t=out:st={dur-0.35:.2f}:d=0.35:alpha=1[s_card];"
                    f"[v_base][s_card]overlay=x='if(lt(t,0.35), -w+w*(t/0.35), if(gt(t,{dur-0.35:.2f}), (W-w)/2+W*(t-({dur-0.35:.2f}))/0.35, (W-w)/2))':y='(H-h)/2'[v_out]"
                )
            elif anim == "slide_bottom":
                # 底部数据栏升起，静止后向下滑出
                anim_filter = (
                    f"{v_base_filter}[v_base];"
                    f"[1:v]scale=1080:1920,fade=t=out:st={dur-0.35:.2f}:d=0.35:alpha=1[s_card];"
                    f"[v_base][s_card]overlay=x='(W-w)/2':y='if(lt(t,0.35), H-(H-(H-h)/2)*(t/0.35), if(gt(t,{dur-0.35:.2f}), (H-h)/2+H*(t-({dur-0.35:.2f}))/0.35, (H-h)/2))'[v_out]"
                )
            elif anim == "rotate":
                # 动态微旋转入场 (-3°动态摆正归位 + 优雅淡出)
                anim_filter = (
                    f"{v_base_filter}[v_base];"
                    f"[1:v]scale=1080:1920,rotate='if(lt(t,0.4), -0.05*(1-t/0.4), 0)':fillcolor=none,fade=t=in:st=0:d=0.4:alpha=1,fade=t=out:st={dur-0.4:.2f}:d=0.4:alpha=1[s_card];"
                    f"[v_base][s_card]overlay=(W-w)/2:(H-h)/2[v_out]"
                )
            elif anim == "zoom":
                # 全息微缩放弹性渐入
                anim_filter = (
                    f"{v_base_filter}[v_base];"
                    f"[1:v]scale=1080:1920,fade=t=in:st=0:d=0.35:alpha=1,fade=t=out:st={dur-0.35:.2f}:d=0.35:alpha=1[s_card];"
                    f"[v_base][s_card]overlay=(W-w)/2:(H-h)/2[v_out]"
                )
            else:
                # 渐进淡入淡出 (Fade In / Out)
                anim_filter = (
                    f"{v_base_filter}[v_base];"
                    f"[1:v]scale=1080:1920,fade=t=in:st=0:d=0.4:alpha=1,fade=t=out:st={dur-0.4:.2f}:d=0.4:alpha=1[s_card];"
                    f"[v_base][s_card]overlay=(W-w)/2:(H-h)/2[v_out]"
                )

            cmd_seg = [
                ffmpeg, "-y",
                "-stream_loop", "-1",
                "-ss", f"{ss_bg:.3f}",
                "-t", f"{dur:.3f}",
                "-i", os.path.abspath(base_video_path),
                "-loop", "1",
                "-i", card_p,
                "-filter_complex", anim_filter,
                "-map", "[v_out]",
                "-an",
                *enc_args,
                "-pix_fmt", "yuv420p",
                seg_fpath
            ]

        subprocess.run(cmd_seg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)

        if progress_cb and (s_idx % 4 == 0 or s_idx == total_slices - 1):
            pct = int(((s_idx + 1) / total_slices) * 60)
            progress_cb(f"⚡ [分段合成 {pct}%] 已渲染视觉片段 [{s_idx+1}/{total_slices}]...")

    # 4. 毫秒级拼接所有视觉分段 (Concat Demuxer)
    concat_txt = os.path.join(seg_dir, "concat_list.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for sf in seg_files:
            norm_p = os.path.abspath(sf).replace("\\", "/")
            f.write(f"file '{norm_p}'\n")

    raw_visual_name = "raw_visual_concat.mp4"
    raw_visual_path = os.path.join(temp_dir, raw_visual_name)
    cmd_concat = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        raw_visual_name
    ]
    subprocess.run(cmd_concat, cwd=temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)

    # 5. 合成双层音轨与视觉流 -> 产出 temp_visual_track.mp4
    if progress_cb:
        progress_cb("⚡ [画面封装 70%] 正在进行双层母带音轨极速封装...")

    cmd_wrap = [
        ffmpeg, "-y",
        "-i", raw_visual_path,
        "-i", temp_audio_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "copy",
        "-t", f"{total_duration:.2f}",
        temp_visual_path
    ]
    wrap_ok = _run_ffmpeg_with_progress(
        cmd=cmd_wrap,
        cwd=temp_dir,
        total_duration=total_duration,
        phase_name="音画合轨",
        creation_flags=creation_flags,
        progress_cb=progress_cb
    )

    # 清理中间片段目录
    try:
        shutil.rmtree(seg_dir, ignore_errors=True)
        if os.path.exists(raw_visual_path):
            os.remove(raw_visual_path)
    except Exception:
        pass

    if not wrap_ok:
        if progress_cb:
            progress_cb("❌ 音画封装失败")
        return False
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except Exception:
            pass

        if not wrap_ok:
            if progress_cb:
                progress_cb("❌ Logo与音频极速封装失败")
            return False

    if not os.path.exists(temp_visual_path) or os.path.getsize(temp_visual_path) < 1024:
        if progress_cb:
            progress_cb("❌ 第一阶段画面合成失败，中间文件未生成")
        return False

    # ─────────────────────────────────────────────────────────
    # 阶段二：独立纯净字幕压制 (Pass 2) -> temp_main_with_subs.mp4
    # ─────────────────────────────────────────────────────────
    temp_main_name = "temp_main_with_subs.mp4"
    temp_main_path = os.path.join(temp_dir, temp_main_name)

    if srt_path and os.path.exists(srt_path):
        local_sub_name = "render_subtitles.srt"
        local_sub_path = os.path.join(temp_dir, local_sub_name)
        try:
            from pipeline.audio_transcriber import sanitize_and_export_srt
            sanitize_and_export_srt(srt_path, local_sub_path)
        except Exception:
            shutil.copy2(srt_path, local_sub_path)
        style_str = build_subtitle_filter_style(config.get("subtitle_style", {}))

        if progress_cb:
            progress_cb("⚡ [字幕压制 0%] 正在进行第二阶段高清晰度 ASS 字幕压制...")

        cmd_pass2 = [
            ffmpeg, "-y",
            "-i", temp_visual_name,
            "-vf", f"subtitles='{local_sub_name}':force_style='{style_str}'",
            *enc_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-t", f"{total_duration:.2f}",
            temp_main_name
        ]

        p2_ok = _run_ffmpeg_with_progress(
            cmd=cmd_pass2,
            cwd=temp_dir,
            total_duration=total_duration,
            phase_name="字幕压制",
            creation_flags=creation_flags,
            progress_cb=progress_cb
        )

        try:
            if os.path.exists(temp_visual_path):
                os.remove(temp_visual_path)
        except Exception:
            pass

        if not p2_ok or not os.path.exists(temp_main_path):
            return False
    else:
        temp_main_path = temp_visual_path

    # ─────────────────────────────────────────────────────────
    # 阶段三：片头封面独立插入 (Pass 3) -> 最终成片
    # ─────────────────────────────────────────────────────────
    cover_dur = float(config.get("cover_duration", 0.0))
    if cover_path and os.path.exists(cover_path) and cover_dur > 0:
        if progress_cb:
            progress_cb(f"🎬 正在前置插入 {cover_dur:.1f} 秒独立片头封面帧...")

        temp_cover_name = "temp_cover_head.mp4"
        temp_cover_path = os.path.join(temp_dir, temp_cover_name)

        cmd_cover = [
            ffmpeg, "-y",
            "-loop", "1", "-t", f"{cover_dur:.2f}", "-i", os.path.abspath(cover_path),
            "-f", "lavfi", "-t", f"{cover_dur:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,setpts=PTS-STARTPTS",
            *enc_args,
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-shortest",
            temp_cover_name
        ]
        subprocess.run(cmd_cover, cwd=temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)

        if os.path.exists(temp_cover_path) and os.path.getsize(temp_cover_path) > 1024:
            concat_list_path = os.path.join(temp_dir, "concat_list.txt")
            p_cover_norm = os.path.abspath(temp_cover_path).replace("\\", "/")
            p_main_norm = os.path.abspath(temp_main_path).replace("\\", "/")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                f.write(f"file '{p_cover_norm}'\nfile '{p_main_norm}'\n")

            cmd_concat = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                os.path.abspath(output_path)
            ]
            subprocess.run(cmd_concat, cwd=temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        else:
            # 封面生成异常则直接导出主片
            shutil.move(temp_main_path, output_path)
    else:
        # 无封面需求，直接移动
        shutil.move(temp_main_path, output_path)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        if progress_cb:
            progress_cb(f"🎉 [全部完成 100%] 极速成片导出成功！保存路径: {output_path}")
        return True

    return False
