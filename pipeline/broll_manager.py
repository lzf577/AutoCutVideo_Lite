import os
import re
import random
import subprocess
import json
from typing import List, Optional, Callable
try:
    from config import get_ffmpeg_exe, get_ffprobe_exe
except ImportError:
    from ..config import get_ffmpeg_exe, get_ffprobe_exe

def get_media_duration(file_path: str) -> float:
    """
    极速高鲁棒性媒体时长探测 (双引擎机制: ffprobe -> ffmpeg 回退)
    使用纯字节流与 UTF-8 安全解码，彻底解决 Windows GBK 环境下 UnicodeDecodeError 导致时长读取为 0 的问题。
    """
    if not file_path or not os.path.exists(file_path):
        return 0.0
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    # 1. 首选: ffprobe 提取 duration 元数据
    try:
        ffprobe = get_ffprobe_exe()
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        out_str = res.stdout.decode("utf-8", errors="ignore").strip()
        if res.returncode == 0 and out_str:
            dur = float(out_str)
            if dur > 0:
                return dur
    except Exception:
        pass

    # 2. 兜底回退: 使用 ffmpeg -i 探测 Duration 字段 (100% 可靠)
    try:
        ffmpeg = get_ffmpeg_exe()
        cmd = [ffmpeg, "-i", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        err_str = res.stderr.decode("utf-8", errors="ignore")
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', err_str)
        if m:
            dur = float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
            if dur > 0:
                return dur
    except Exception:
        pass

    return 0.0

def slice_broll_material(
    broll_source: str,
    output_dir: str,
    needed_total_duration: float,
    min_chunk: float = 4.0,
    max_chunk: float = 8.0,
    progress_cb: Optional[Callable[[str], None]] = None
) -> List[str]:
    """
    将虚晃素材（单个视频文件或包含多个视频的文件夹）切割成短镜头片段池。
    """
    if not os.path.exists(broll_source):
        return []

    os.makedirs(output_dir, exist_ok=True)
    video_files = []
    
    if os.path.isdir(broll_source):
        for f in os.listdir(broll_source):
            full = os.path.join(broll_source, f)
            if os.path.isfile(full) and os.path.splitext(f.lower())[1] in {".mp4", ".mov", ".mkv", ".flv"}:
                video_files.append(full)
    else:
        video_files.append(broll_source)

    if not video_files:
        return []

    if progress_cb:
        progress_cb(f"正在准备切分虚晃素材镜头 (目标总时长约 {needed_total_duration:.1f}s)...")

    ffmpeg = get_ffmpeg_exe()
    creation_flags = 0
    if os.name == 'nt':
        creation_flags = subprocess.CREATE_NO_WINDOW

    slices: List[str] = []
    current_acc_duration = 0.0
    slice_idx = 1

    # 遍历素材视频进行切片
    for v_file in video_files:
        if current_acc_duration >= needed_total_duration and len(slices) >= 3:
            break
            
        dur = get_media_duration(v_file)
        if dur <= 1.0:
            dur = 120.0  # 兜底假设素材至少2分钟

        has_aud = False
        try:
            # 探测素材视频是否包含音频流
            ffprobe = get_ffprobe_exe()
            probe_cmd = [ffprobe, "-v", "error", "-show_streams", "-select_streams", "a", "-of", "json", v_file]
            p_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            if p_res.returncode == 0 and p_res.stdout:
                probe_data = json.loads(p_res.stdout.decode("utf-8", errors="ignore"))
                has_aud = len(probe_data.get('streams', [])) > 0
        except Exception:
            pass

        curr_time = 0.0
        while curr_time < dur and current_acc_duration < needed_total_duration:
            chunk_len = random.uniform(min_chunk, max_chunk)
            if curr_time + chunk_len > dur:
                chunk_len = dur - curr_time
            if chunk_len < 2.0:
                break

            out_slice = os.path.join(output_dir, f"broll_seg_{slice_idx:03d}.mp4")
            # 极速切片：若有音频流则保留并转码为高质量 AAC，无音频则 -an
            if has_aud:
                cmd = [
                    ffmpeg, "-y",
                    "-ss", f"{curr_time:.2f}",
                    "-t", f"{chunk_len:.2f}",
                    "-i", v_file,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-ar", "48000",
                    "-ac", "2",
                    "-avoid_negative_ts", "make_zero",
                    out_slice
                ]
            else:
                cmd = [
                    ffmpeg, "-y",
                    "-ss", f"{curr_time:.2f}",
                    "-t", f"{chunk_len:.2f}",
                    "-i", v_file,
                    "-an",
                    "-c:v", "copy",
                    "-avoid_negative_ts", "make_zero",
                    out_slice
                ]
            
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            if res.returncode == 0 and os.path.exists(out_slice) and os.path.getsize(out_slice) > 1024:
                slices.append(out_slice)
                current_acc_duration += chunk_len
                if progress_cb:
                    broll_pct = min(100, int((current_acc_duration / max(1.0, needed_total_duration)) * 100))
                    progress_cb(f"🎬 [虚晃切片 {broll_pct}%] 已切出第 {slice_idx} 个空镜头片段 ({chunk_len:.1f}s)")
                slice_idx += 1

            curr_time += chunk_len

    if progress_cb:
        progress_cb(f"✅ [虚晃切片 100%] 镜头池准备完毕，共切出 {len(slices)} 个独立空镜头")

    return slices
