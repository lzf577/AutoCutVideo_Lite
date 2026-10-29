#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
《AutoCutVideo_Lite》无头纯命令行压制运行器 (Headless CLI Runner for Linux/Debian 12)
- 功能：
  1. 纯控制台运行，彻底脱离 PyQt6 桌面图形依赖；
  2. 智能扫描指定目录下的全部待压制任务（第1集、第2集...）；
  3. 自动探测 Linux 底层 Intel QSV / VA-API 硬件加速编码器；
  4. 毫秒级字幕对齐、PDF 幻灯片插片、虚晃空镜拼接全自动化；
  5. 压制完成后输出成片文件清单与详细耗时统计。
"""

import os
import sys
import re
import argparse
import datetime
from pathlib import Path

# 确保能正常导入 AutoCutVideo_Lite 模块
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config import load_config, save_config, get_ffmpeg_exe, get_ffprobe_exe
from pipeline.scanner import scan_batch_directory, ProjectTask
from pipeline.batch_runner import BatchRunnerThread

def detect_best_encoder(ffmpeg_exe: str) -> str:
    """自动检测系统中可用的最佳视频编码器"""
    import subprocess
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        res = subprocess.run([ffmpeg_exe, "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
        out = res.stdout.lower()
        if "h264_qsv" in out:
            return "h264_qsv"
        if "h264_vaapi" in out:
            return "h264_vaapi"
        elif "h264_nvenc" in out:
            return "h264_nvenc"
    except Exception:
        pass
    return "libx264"

def main():
    parser = argparse.ArgumentParser(description="AutoCutVideo_Lite Headless CLI Batch Runner")
    parser.add_argument("date", nargs="?", default="", help="可选生产日期 (如 2026-09-07)")
    parser.add_argument("--date", dest="date_opt", type=str, default="", help="指定生产日期 (如 2026-09-07)")
    parser.add_argument("--episodes", "--ep", type=str, default="", help="指定要压制的分集 (如 '1-3' 或 '1,2,3' 或 '第1集')")
    parser.add_argument("--batch-dir", type=str, default="", help="待压制素材根目录 (默认自动探测最新的待压制素材/[今日日期])")
    parser.add_argument("--output-dir", type=str, default="", help="成品输出目录 (默认 成品交付/[今日日期])")
    parser.add_argument("--encoder", type=str, default="auto", help="指定视频编码器 (auto, h264_qsv, h264_vaapi, libx264)")
    parser.add_argument("--crf", type=int, default=23, help="视频 CRF 质量压缩比 (默认 23，推荐 22-26，数值越大约省空间)")
    parser.add_argument("--preset", type=str, default="veryfast", help="libx264 编码预设 (默认 veryfast)")
    parser.add_argument("--whisper-model", type=str, default="", help="指定 Whisper 模型 (base, small, medium)")
    parser.add_argument("--device", type=str, default="", help="Whisper 运行设备 (auto, cpu, cuda)")
    parser.add_argument("--trim-start", type=float, default=None, help="片头裁剪秒数 (默认读取配置)")
    parser.add_argument("--trim-end", type=float, default=None, help="片尾裁剪秒数 (默认读取配置)")
    args = parser.parse_args()

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    project_root = APP_DIR.parent
    target_date_str = (args.date_opt or args.date or "").strip() or today_str

    # 1. 确定待压制素材目录
    batch_dir = args.batch_dir
    if not batch_dir:
        target_daily = project_root / "每日生产" / target_date_str
        target_pre_press = target_daily / "04_待压制素材"
        target_pre_press.mkdir(parents=True, exist_ok=True)
        
        # 自动按每日集数同步建立 04_待压制素材 的分集子目录
        try:
            from pipeline.path_config import sync_episode_dirs
            sync_episode_dirs(target_date_str)
        except Exception:
            nb_dir = target_daily / "03_Notebook素材"
            if nb_dir.exists():
                for f in nb_dir.glob("第*集*"):
                    m = re.search(r"(第\d+集)", f.name)
                    if m:
                        (target_pre_press / m.group(1)).mkdir(parents=True, exist_ok=True)

        candidate_dirs = [
            target_pre_press,
            project_root / "每日生产" / today_str / "04_待压制素材",
            project_root / "待压制素材" / target_date_str,
            project_root / "待压制素材" / today_str,
            project_root / "待压制素材",
            Path("/root/体彩自动化/每日生产") / target_date_str / "04_待压制素材",
            Path("/root/体彩自动化/每日生产") / today_str / "04_待压制素材",
            Path("/root/体彩自动化/待压制素材") / target_date_str,
            Path("/root/体彩自动化/待压制素材") / today_str,
            Path("/data/体彩自动化/待压制素材") / target_date_str,
        ]
        for c in candidate_dirs:
            if c.exists() and any(c.iterdir()):
                batch_dir = str(c)
                break
        if not batch_dir:
            batch_dir = str(target_pre_press)
    else:
        os.makedirs(batch_dir, exist_ok=True)

    # 2. 确定成片输出目录
    output_dir = args.output_dir
    if not output_dir:
        output_dir = str(project_root / "每日生产" / target_date_str / "05_成品交付")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 65)
    print("🎬 《AutoCutVideo_Lite》无头命令行压制流水线 (Debian 12 工业版)")
    print("=" * 65)
    print(f"📁 待压制素材目录: {batch_dir}")
    print(f"💾 成品输出交付目录: {output_dir}")

    # 3. 加载配置文件并应用 Linux 覆盖项
    cfg = load_config()
    ffmpeg_exe = get_ffmpeg_exe()
    print(f"🔧 底层 FFmpeg 可执行路径: {ffmpeg_exe}")

    # 编码器自适应决策
    if args.encoder != "auto":
        cfg["video_encoder"] = args.encoder
    else:
        cfg_enc = cfg.get("video_encoder", "auto")
        if cfg_enc and cfg_enc != "auto":
            cfg["video_encoder"] = cfg_enc
        else:
            cfg["video_encoder"] = detect_best_encoder(ffmpeg_exe)
    if args.crf:
        cfg["video_crf"] = args.crf
    if args.preset:
        cfg["video_preset"] = args.preset
    print(f"🚀 激活视频编码引擎: {cfg['video_encoder']} (Preset: {cfg.get('video_preset', 'veryfast')}, CRF: {cfg.get('video_crf', 23)})")

    if args.whisper_model:
        cfg["whisper_model"] = args.whisper_model
    if args.device:
        cfg["whisper_device"] = args.device
    if args.trim_start is not None:
        cfg["trim_start"] = args.trim_start
    if args.trim_end is not None:
        cfg["trim_end"] = args.trim_end
    print(f"✂️ 去头掐尾配置: 片头截取前 {cfg.get('trim_start', 0.0)}s | 片尾掐除后 {cfg.get('trim_end', 0.0)}s")

    # 4. 扫描目录任务
    tasks = scan_batch_directory(batch_dir)
    if not tasks:
        print(f"⚠️ 提示: 在目录 [{batch_dir}] 下未扫描到待压制的视频文件。")
        print("💡 状态: 压制引擎就绪，等待 NotebookLM 生成的 MP4 与 PDF 素材放入。")
        print("=" * 65)
        sys.exit(0)

    # 支持 --episodes 过滤分集 (如 1-3, 1,2,3, 第1集)
    if args.episodes:
        allowed_nums = set()
        allowed_names = set()
        parts = re.split(r"[,;\s]+", args.episodes.strip())
        for part in parts:
            if not part:
                continue
            range_match = re.match(r"^(?:第)?(\d+)(?:集)?\s*[-~至到]\s*(?:第)?(\d+)(?:集)?$", part)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                for i in range(min(start, end), max(start, end) + 1):
                    allowed_nums.add(i)
                    allowed_names.add(f"第{i}集")
            else:
                num_match = re.search(r"\d+", part)
                if num_match:
                    n = int(num_match.group(0))
                    allowed_nums.add(n)
                    allowed_names.add(f"第{n}集")
                allowed_names.add(part)

        filtered_tasks = []
        for t in tasks:
            m = re.search(r"\d+", t.name)
            ep_num = int(m.group(0)) if m else None
            folder_m = re.search(r"\d+", os.path.basename(t.folder_path))
            folder_ep_num = int(folder_m.group(0)) if folder_m else None
            if (t.name in allowed_names or
                os.path.basename(t.folder_path) in allowed_names or
                (ep_num is not None and ep_num in allowed_nums) or
                (folder_ep_num is not None and folder_ep_num in allowed_nums)):
                filtered_tasks.append(t)
        print(f"🎯 指定分集过滤 [{args.episodes}]：原任务 {len(tasks)} 个 -> 筛选保留 {len(filtered_tasks)} 个任务")
        tasks = filtered_tasks
        if not tasks:
            print(f"⚠️ 经过分集过滤 [{args.episodes}] 后未匹配到任何有效任务！")
            sys.exit(0)

    print(f"📊 成功加载 {len(tasks)} 个压制任务项:")
    for t in tasks:
        v_name = os.path.basename(t.video_path) if t.video_path else "❌ 缺失"
        pdf_name = os.path.basename(t.pdf_path) if t.pdf_path else "⚪ 无PDF"
        print(f"   [{t.id}] {t.name} -> 主视频: {v_name} | 课件: {pdf_name}")
    print("=" * 65)

    # 5. 实例化执行器并启动压制
    runner = BatchRunnerThread(tasks=tasks, config=cfg, output_dir=output_dir)

    # 挂接控制台实时日志打印
    def on_log(msg: str):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    def on_progress(tid: int, pct: int, msg: str):
        if pct % 10 == 0 or pct in [25, 45, 62, 85, 100]:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]   ⏳ 任务[{tid}] 进度 {pct}%: {msg}")

    def on_finished(tid: int, succ: bool, msg: str):
        tag = "✅ 成功" if succ else "❌ 失败"
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🏁 任务[{tid}] 执行完毕: {tag} ({msg})")

    def on_all_finished(succ_cnt: int, fail_cnt: int):
        print("\n" + "=" * 65)
        print(f"🎉 全部批处理任务执行完毕！成功: {succ_cnt} 个，失败: {fail_cnt} 个")
        print(f"📦 成品交付目录: {output_dir}")
        print("=" * 65 + "\n")

    runner.log_signal.emit = on_log
    runner.task_progress_signal.emit = on_progress
    runner.task_finished_signal.emit = on_finished
    runner.all_finished_signal.emit = on_all_finished

    # 启动同步阻塞式执行
    runner.run()

if __name__ == "__main__":
    main()
