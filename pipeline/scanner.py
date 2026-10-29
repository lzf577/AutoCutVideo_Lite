import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".ts", ".webm", ".m4v"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
IGNORE_DIR_NAMES = {"output", "dist", "logs", "__pycache__", ".git", "temp", "tmp", "tmp_autocut", "tmp_render", "build"}

@dataclass
class ProjectTask:
    id: int
    name: str
    folder_path: str
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    pdf_path: Optional[str] = None
    cover_path: Optional[str] = None
    broll_path: Optional[str] = None
    logo_path: Optional[str] = None
    
    # 运行时状态
    status: str = "等待处理"  # 等待处理 | 处理中 | 已完成 | 失败 | 无效项目
    progress: int = 0
    message: str = "就绪"
    error_msg: str = ""
    output_video_path: Optional[str] = None
    
    def is_valid(self) -> bool:
        """必须包含可处理的主视频，或解说母带音频与视觉视频素材"""
        if self.video_path is not None and os.path.exists(self.video_path):
            return True
        if self.audio_path is not None and os.path.exists(self.audio_path) and (
            (self.broll_path is not None and os.path.exists(self.broll_path)) or 
            (self.cover_path is not None and os.path.exists(self.cover_path))
        ):
            return True
        return False

def _parse_folder_to_task(folder_path: str, task_id: int, project_name: Optional[str] = None) -> Optional[ProjectTask]:
    """尝试将单个文件夹解析为标准任务"""
    if not os.path.isdir(folder_path):
        return None
        
    try:
        all_entries = os.listdir(folder_path)
    except Exception:
        return None

    raw_videos = []
    audio_files = []
    pdf_files = []
    image_files = []
    broll_dirs = []
    logo_path = None
    cover_path = None
    audio_path = None

    for entry in all_entries:
        full = os.path.join(folder_path, entry)
        entry_l = entry.lower()
        if os.path.isdir(full):
            if any(k in entry_l for k in ["broll", "b_roll", "空镜", "虚晃", "背景", "素材"]):
                broll_dirs.append(full)
        elif os.path.isfile(full):
            ext = os.path.splitext(entry_l)[1]
            if ext in VIDEO_EXTENSIONS:
                if not entry_l.startswith("output_") and not entry_l.startswith("temp_") and not "_成片" in entry_l:
                    # 优先检测是否为视频 Logo (如 男logo.mp4, 女logo.mp4)
                    if any(k in entry_l for k in ["logo", "水印", "icon"]):
                        if not logo_path:
                            logo_path = full
                    else:
                        raw_videos.append(full)
            elif ext in AUDIO_EXTENSIONS:
                if not entry_l.startswith("temp_") and not entry_l.startswith("extracted_"):
                    audio_files.append(full)
            elif ext == ".pdf":
                pdf_files.append(full)
            elif ext in IMAGE_EXTENSIONS:
                image_files.append(full)

    if not raw_videos and not logo_path and not audio_files:
        return None

    # 1. 识别 母带解说音频 (如 EdgeTTS 生成的 第X集_母带音频.mp3)
    if audio_files:
        for af in audio_files:
            af_l = os.path.basename(af).lower()
            if any(k in af_l for k in ["母带", "音频", "audio", "voice", "tts", "master", "解说", "正文"]):
                audio_path = af
                break
        if not audio_path:
            audio_path = audio_files[0]

    # 2. 识别 Logo (若尚未从视频中识别出，则从图片中检测)
    if not logo_path:
        for img in image_files:
            img_l = os.path.basename(img).lower()
            if any(k in img_l for k in ["logo", "水印", "icon"]):
                logo_path = img
                break

    # 3. 识别 封面 (Cover)
    for img in image_files:
        if img == logo_path:
            continue
        img_l = os.path.basename(img).lower()
        if any(k in img_l for k in ["cover", "封面", "fm", "poster"]):
            cover_path = img
            break
    # 若没有明确关键词，则取第一张非 Logo 的图片作为封面
    if not cover_path and image_files:
        for img in image_files:
            if img != logo_path:
                cover_path = img
                break

    # 4. 区分 主视频 与 虚晃素材 (B-Roll)
    video_path = None
    broll_path = broll_dirs[0] if broll_dirs else None

    if raw_videos:
        def _normalize_name(s: str) -> str:
            s = s.lower().strip()
            cn_num_map = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10', '零': '0'}
            for cn, num in cn_num_map.items():
                s = s.replace(cn, num)
            return s

        pdf_stems = [_normalize_name(os.path.splitext(os.path.basename(p))[0]) for p in pdf_files]
        folder_norm = _normalize_name(os.path.basename(folder_path))

        # 候选优先级智能打分机制
        def get_main_video_score(v_path):
            stem_raw = os.path.splitext(os.path.basename(v_path))[0]
            stem_norm = _normalize_name(stem_raw)

            # 1. 绝对主视频：与 PDF 同名 (如 第一集.mp4 对应 第一集.pdf)
            if stem_norm in pdf_stems:
                return 1000
            
            # 2. 与文件夹名同名 (如 第1集/第一集.mp4 或 1/1.mp4)
            if stem_norm == folder_norm:
                return 800
            
            # 3. 明确的主视频标志词 (如 main, video, 原视频, 录屏, 解说, 正片, 复盘, 开篇, slide, overview)
            if any(k in stem_norm for k in ["main", "video", "原视频", "录屏", "解说", "正片", "source", "master", "开篇", "复盘", "overview", "slide", "全景", "台本", "剧本", "精选"]):
                return 500
            
            # 4. 集数标志词 (如 第1集, ep1, 01)
            if any(k in stem_norm for k in ["第", "ep", "episode", "part", "vol"]):
                return 400

            # 5. 带有明显空镜头/素材/赛事/集锦名称的降低得分
            if any(k in stem_norm for k in [
                "broll", "b_roll", "空镜", "虚晃", "背景", "素材", "英超", "西甲", "德甲", "意甲", 
                "法甲", "欧冠", "中超", "日超", "日本超", "日职", "美联", "美联职", "美职", 
                "德乙", "西乙", "法乙", "意乙", "荷甲", "葡超", "巴甲", "俄超", "阿甲", "沙特联",
                "集锦", "比赛", "录像", "highlight", "match", "game"
            ]) or re.match(r"^\d+[a-zA-Z\u4e00-\u9fa5]+", stem_raw):
                return 10

            # 6. 纯数字文件名
            if stem_raw.isdigit():
                return 100
            
            return 50 - len(stem_raw)

        # 按得分从高到低排序
        sorted_videos = sorted(raw_videos, key=get_main_video_score, reverse=True)
        top_score = get_main_video_score(sorted_videos[0])

        if len(raw_videos) == 1:
            # 关键保障：若只有单个视频 (如 1英超.mp4)，既作为背景画面流，又作为切片镜头池！
            video_path = sorted_videos[0]
            if not broll_path:
                broll_path = sorted_videos[0]
        else:
            # 多个视频时：
            if pdf_files and top_score <= 10:
                video_path = sorted_videos[0]
                if not broll_path:
                    broll_path = sorted_videos[0]
            else:
                video_path = sorted_videos[0]
                if not broll_path:
                    broll_path = sorted_videos[1]

    # 5. 识别 PDF
    pdf_path = pdf_files[0] if pdf_files else None

    name = project_name or os.path.basename(folder_path)
    return ProjectTask(
        id=task_id,
        name=name,
        folder_path=folder_path,
        video_path=video_path,
        audio_path=audio_path,
        pdf_path=pdf_path,
        cover_path=cover_path,
        broll_path=broll_path,
        logo_path=logo_path,
        status="等待处理",
        message="素材扫描完毕"
    )

def scan_batch_directory(batch_root_dir: str) -> List[ProjectTask]:
    """
    自适应扫描目录：
    1. 【单项目模式】：若所选根目录下直接包含主视频文件，则将当前目录直接识别为任务 1。
    2. 【多子文件夹批处理模式】：遍历一级子目录，将包含视频的每个子文件夹识别为一个项目。
    3. 【深层目录支持】：若一级子目录未找到视频，进一步递归寻找包含视频的叶子子目录。
    """
    tasks: List[ProjectTask] = []
    if not os.path.isdir(batch_root_dir):
        return tasks

    task_id = 1

    # 1. 检查根目录本身是否就是一个项目（直接包含视频）
    root_task = _parse_folder_to_task(batch_root_dir, task_id, project_name=os.path.basename(batch_root_dir))
    if root_task and root_task.is_valid():
        tasks.append(root_task)
        task_id += 1

    # 2. 扫描一级子目录
    try:
        entries = sorted(os.listdir(batch_root_dir))
    except Exception:
        return tasks

    sub_dirs_to_check = []
    for entry in entries:
        folder_path = os.path.join(batch_root_dir, entry)
        if os.path.isdir(folder_path) and entry.lower() not in IGNORE_DIR_NAMES:
            sub_dirs_to_check.append(folder_path)

    for sub_dir in sub_dirs_to_check:
        task = _parse_folder_to_task(sub_dir, task_id)
        if task and task.is_valid():
            tasks.append(task)
            task_id += 1
        else:
            # 3. 递归检查二级子目录
            try:
                second_entries = sorted(os.listdir(sub_dir))
                for s_entry in second_entries:
                    s_path = os.path.join(sub_dir, s_entry)
                    if os.path.isdir(s_path) and s_entry.lower() not in IGNORE_DIR_NAMES:
                        s_task = _parse_folder_to_task(s_path, task_id, project_name=f"{os.path.basename(sub_dir)}_{s_entry}")
                        if s_task and s_task.is_valid():
                            tasks.append(s_task)
                            task_id += 1
            except Exception:
                pass

    return tasks

def scan_and_append_directories(existing_tasks: List[ProjectTask], new_paths: List[str]) -> tuple[List[ProjectTask], int]:
    """
    智能解析并追加多个目录到任务列表（去重 + 智能识别单项目/多项目根目录）：
    - 返回：(更新后的任务列表, 本次新增的任务数量)
    """
    tasks = list(existing_tasks)
    existing_paths = {os.path.normpath(t.folder_path).lower() for t in tasks}
    added_count = 0

    for p in new_paths:
        if not os.path.exists(p):
            continue
        folder = p if os.path.isdir(p) else os.path.dirname(p)
        norm_folder = os.path.normpath(folder).lower()

        # 优先检查拖入的文件夹本身是否就是一个项目（直接包含主视频）
        single_task = _parse_folder_to_task(folder, len(tasks) + 1, project_name=os.path.basename(folder))
        if single_task and single_task.is_valid():
            if norm_folder not in existing_paths:
                tasks.append(single_task)
                existing_paths.add(norm_folder)
                added_count += 1
        else:
            # 否则作为包含多个子项目的总目录递归扫描
            sub_tasks = scan_batch_directory(folder)
            for st in sub_tasks:
                st_norm = os.path.normpath(st.folder_path).lower()
                if st_norm not in existing_paths:
                    tasks.append(st)
                    existing_paths.add(st_norm)
                    added_count += 1

    # 重新整理 ID 序号
    for idx, t in enumerate(tasks):
        t.id = idx + 1

    return tasks, added_count
