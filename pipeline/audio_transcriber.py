import os
import re
import subprocess
from typing import List, Dict, Tuple, Optional, Callable

try:
    from config import get_ffmpeg_exe
except ImportError:
    from ..config import get_ffmpeg_exe

def format_timestamp(seconds: float) -> str:
    """将秒数 float 转换为标准 SRT 时间戳 00:00:00,000"""
    millisec = int(round((seconds - int(seconds)) * 1000))
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisec:03d}"

def parse_time_str(time_str: str) -> float:
    """将 SRT 时间戳 '00:00:04,305' 转为秒数 float"""
    time_str = time_str.strip().replace('.', ',')
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s_ms = parts
        s_parts = s_ms.split(',')
        s = s_parts[0]
        ms = s_parts[1] if len(s_parts) > 1 else '0'
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    return 0.0

def parse_srt_file(srt_path: str) -> List[Dict]:
    """解析 SRT 文件，返回结构化字幕列表 [{index, start, end, text}, ...]"""
    if not os.path.exists(srt_path):
        return []
    with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n', content.strip())
    subtitles = []
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})')
    
    idx = 1
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        # 查找时间轴行
        time_match = None
        text_lines = []
        for line in lines:
            m = pattern.search(line)
            if m:
                time_match = m
            elif not line.isdigit() and time_match:
                text_lines.append(line)
        
        if time_match:
            start_sec = parse_time_str(time_match.group(1))
            end_sec = parse_time_str(time_match.group(2))
            text = " ".join(text_lines)
            subtitles.append({
                "index": idx,
                "start": start_sec,
                "end": end_sec,
                "start_str": time_match.group(1),
                "end_str": time_match.group(2),
                "text": text
            })
            idx += 1
    return subtitles

# ==============================================================================
# 赛事与风控专用 ASR 错词清洗中枢 (Domain Vocabulary Auto-Correction)
# ==============================================================================
MATCH_VOCAB_CORRECTIONS = [
    # 1. 核心风控与阻力/支撑术语
    (r"低组设防|底阻设防", "低阻设防"),
    (r"超低组", "超低阻"),
    (r"超高组", "超高阻"),
    (r"低组", "低阻"),
    (r"高组", "高阻"),
    (r"前组诱客|浅组诱客", "浅阻诱客"),
    (r"前组|浅组", "浅阻"),
    (r"阻力调供|调供", "阻力调控"),
    (r"阻离位|组离位|阻力伟", "阻力位"),
    (r"极限直升位|直升位|直升阈值", "极限支撑位"),
    (r"支撑预值|支撑雨值", "支撑阈值"),
    (r"预值|雨值", "阈值"),
    (r"中局定性", "终局定性"),
    (r"中局期望", "终局期望"),
    (r"板场的中局", "本场的终局"),
    (r"板场的", "本场的"),
    (r"封控是中局", "风控与终局"),
    (r"封控|分控", "风控"),
    (r"助老丰功装甲|筑牢丰功装甲|助牢风控装甲", "筑牢风控护甲"),
    (r"助牢|助老", "筑牢"),
    (r"风控装甲", "风控护甲"),
    (r"单干客胜|单官客胜|单干主胜|单官主胜", lambda m: m.group(0).replace("单干", "单关").replace("单官", "单关")),
    (r"单干|单官", "单关"),
    (r"及时盘口|及时盘面|及时盘", "即时盘面"),
    (r"及时水位", "即时阻力"),
    (r"身盘", "深盘"),
    (r"下扛", "下盘"),
    (r"角杀战|中场角杀|角杀", "绞杀"),
    (r"站平对冲|占平对冲|打平对冲", "战平对冲"),
    (r"强制绑定站平|强制绑定占平", "强制绑定战平"),
    (r"商庭", "伤停"),
    (r"班球", "半球"),
    (r"半衣菌水射防|半一菌水射防|半衣均水设防", "半一均水设防"),
    (r"菌水|军水", "均水"),
    (r"射防", "设防"),
    (r"主让班球", "主让半球"),
    (r"克胜", "客胜"),
    (r"主升SP|主升", "主胜SP"),
    (r"同盘盈率|铜盘盈率|同盘赢率|铜盘赢率", "同盘赢率"),
    (r"盈率", "赢率"),
    (r"SOP值", "SP值"),
    (r"有势方只指|优势方只指", "优势方直指"),
    (r"有势方", "优势方"),
    (r"只指强势", "直指强势"),
    (r"极限焦灼|极度焦灼", "极限胶着"),
    (r"焦灼", "胶着"),
    (r"互成和", "护城河"),
    (r"绝对励志", "绝对理智"),
    (r"空间无限鼻子", "空间无限逼近"),
    (r"以西数两名", "已悉数亮相"),
    (r"晒是", "赛事"),
    (r"三目全景", "三幕全景"),
    (r"硬钢", "硬刚"),
    (r"魔鬼主唱", "魔鬼主场"),
    (r"先翻纸面", "掀翻纸面"),
    (r"晋级防欠看油", "近期防线堪忧"),
    (r"正在狂丢", "正赛狂丢"),
    (r"反击极度卸力", "反击极度犀利"),
    (r"刺刀剑红", "刺刀见红"),
    (r"刺金与指数", "资金与指数"),
    (r"机告的操盘", "机构的操盘"),
    (r"机告", "机构"),
    (r"出盘给深", "初盘给深"),
    (r"步步精心", "步步惊心"),
    (r"耗无悬念", "毫无悬念"),
    (r"普超刺激客栈深夺", "葡超次席客战争夺"),
    (r"普超", "葡超"),
    (r"压轴伸张", "压轴大战"),
    (r"5-5开", "五五开"),
    (r"兵点的20万", "冰点的20%"),
    (r"兵点", "冰点"),
    (r"泰山压底", "泰山压顶"),
    (r"无上缺", "无伤缺"),
    
    # 2. 球队与球场专有名词
    (r"费内巴切尔", "费内巴切"),
    (r"科某迎战莱比西", "科莫迎战莱比锡"),
    (r"科某", "科莫"),
    (r"莱比西红牛|莱比西", "莱比锡红牛"),
    (r"溢价新贵", "意甲新贵"),
    (r"败人慕尼黑|败人", "拜仁慕尼黑"),
    (r"鞍联球场", "安联球场"),
    (r"降维大集", "降维打击"),
    (r"阿玛多拉", "阿马多拉"),
    (r"布拉扎", "布拉加"),
    (r"德尔维叶", "德尔瓦耶"),
    (r"弗拉门格|弗拉门稿", "弗拉门戈"),
    (r"作用几多近3000米", "坐拥基多近3000米"),
    
    # 3. 币种与数字规范 (如 亿游 -> 亿欧, 升价 -> 身价, 末位0规范)
    (r"亿游", "亿欧"),
    (r"万元欧元身价", "万欧元身价"),
    (r"升价", "身价"),
    (r"9\.401欧", "9.4亿欧"),
    (r"(\d+\.\d*?)0+(亿|万|倍|%)", r"\1\2"),
    (r"(\d+)\.0+(亿|万|倍|%)", r"\1\2"),
    (r"(\d+)\.00(?=[^\d]|$)", r"\1.0"),
    (r"52\.0(?=[^\d%]|$)", "52%"),
    (r"55\.0盘", "55%"),
    (r"55\.0(?=[^\d%]|$)", "55%"),
    (r"50\.0%", "50%"),
    (r"9月10日(?= 大号球场)", "9月10号"),
]

def correct_match_text(text: str) -> str:
    """自动应用赛事风控专有名词与错别字字典修复"""
    for pattern, repl in MATCH_VOCAB_CORRECTIONS:
        if callable(repl):
            text = re.sub(pattern, repl, text)
        else:
            text = re.sub(pattern, repl, text)
    return text

def sanitize_srt_content(srt_content: str) -> str:
    """严格清洗 SRT 字幕时间轴，修复时间倒流、重叠与单条持续过长的死卡 Bug"""
    sub_matches = re.findall(r'(\d+)\n(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\n([^\n]+)', srt_content)
    if not sub_matches:
        return srt_content

    subs = []
    for item in sub_matches:
        idx, h1, m1, s1, ms1, h2, m2, s2, ms2, text = item
        t1 = int(h1)*3600 + int(m1)*60 + int(s1) + int(ms1)/1000.0
        t2 = int(h2)*3600 + int(m2)*60 + int(s2) + int(ms2)/1000.0
        subs.append({"idx": int(idx), "start": t1, "end": t2, "text": text.strip()})

    sanitized = []
    last_end = 0.0

    for i, s in enumerate(subs):
        st = s["start"]
        et = s["end"]
        txt = s["text"]

        # 1. 修复时间倒流与重叠
        if st < last_end:
            st = last_end + 0.05

        # 2. 限制单条字幕的最大合理持续时间 (根据字数预估，彻底杜绝死卡)
        max_reasonable_dur = max(2.0, min(5.5, len(txt) * 0.35 + 0.8))
        if et <= st or (et - st) > max_reasonable_dur:
            et = st + max_reasonable_dur

        # 3. 智能修复数字缺失小数点 (如 "1 49" -> "1.49", "33 3%" -> "33.3%", "1点49" -> "1.49")
        txt = re.sub(r'(\d+)[ \t]+(\d+)', r'\1.\2', txt)
        txt = re.sub(r'(\d+)点(\d+)', r'\1.\2', txt)
        
        # 4. 智能纠正赛事风控专有名词同音错别字与末位0
        txt = correct_match_text(txt)

        st = round(st, 3)
        et = round(et, 3)
        last_end = et

        sanitized.append({
            "idx": i + 1,
            "start": st,
            "end": et,
            "start_str": format_timestamp(st),
            "end_str": format_timestamp(et),
            "text": txt
        })

    out_lines = []
    for s in sanitized:
        out_lines.append(f"{s['idx']}")
        out_lines.append(f"{s['start_str']} --> {s['end_str']}")
        out_lines.append(s['text'])
        out_lines.append("")

    return "\n".join(out_lines)

def sanitize_and_export_srt(input_srt: str, output_srt: str):
    """读取、清洗并保存无重叠、无死卡的纯净单行 SRT"""
    if not os.path.exists(input_srt):
        return
    with open(input_srt, "r", encoding="utf-8") as f:
        content = f.read()
    clean_content = sanitize_srt_content(content)
    os.makedirs(os.path.dirname(os.path.abspath(output_srt)), exist_ok=True)
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(clean_content)

def write_srt_file(subtitles: List[Dict], srt_path: str):
    """将结构化字幕列表写入 SRT 文件 (写入时自动清洗)"""
    os.makedirs(os.path.dirname(os.path.abspath(srt_path)), exist_ok=True)
    raw_lines = []
    for idx, sub in enumerate(subtitles, start=1):
        start_str = sub.get("start_str") or format_timestamp(sub["start"])
        end_str = sub.get("end_str") or format_timestamp(sub["end"])
        text = sub.get("text", "").strip()
        raw_lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n\n")
    
    clean_srt = sanitize_srt_content("".join(raw_lines))
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(clean_srt)

def extract_audio(
    video_path: str,
    output_audio_path: str,
    trim_start: float = 0.0,
    trim_end: float = 0.0,
    progress_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """使用 FFmpeg 极速提取原视频音频为 16kHz 单声道 MP3 (支持去头去尾截取)"""
    if progress_cb:
        if trim_end > 0 or trim_start > 0:
            progress_cb(f"正在提取视频音轨 (截取: 前{trim_start}s ~ 尾{trim_end}s)...")
        else:
            progress_cb("正在提取视频音轨...")
    os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
    ffmpeg = get_ffmpeg_exe()
    
    cmd = [ffmpeg, "-y"]
    if trim_start > 0:
        cmd.extend(["-accurate_seek", "-ss", f"{trim_start:.3f}"])
        
    cmd.extend(["-i", video_path, "-vn"])

    try:
        from pipeline.broll_manager import get_media_duration
    except ImportError:
        from .broll_manager import get_media_duration

    raw_dur = get_media_duration(video_path)
    if raw_dur > 0:
        actual_dur = max(1.0, raw_dur - trim_start - trim_end)
        cmd.extend(["-t", f"{actual_dur:.3f}"])

    cmd.extend([
        "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        output_audio_path
    ])
    
    creation_flags = 0
    if os.name == 'nt':
        creation_flags = subprocess.CREATE_NO_WINDOW
        
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
    return res.returncode == 0 and os.path.exists(output_audio_path)

def normalize_whisper_model_name(raw_name: str) -> str:
    """标准化 Whisper 模型名称"""
    if not raw_name:
        return "small"
    name = raw_name.lower().strip()
    if "(" in name:
        name = name.split("(")[0].strip()
    for key in ["large-v3", "large-v2", "large-v1", "medium", "small", "base", "tiny"]:
        if key in name:
            return key
    return name

def is_valid_model_dir(dir_path: str) -> bool:
    """验证模型目录是否包含有效的权重与配置文件"""
    if not os.path.isdir(dir_path):
        return False
    has_cfg = os.path.exists(os.path.join(dir_path, "config.json")) or os.path.exists(os.path.join(dir_path, "preprocessor_config.json"))
    has_weights = os.path.exists(os.path.join(dir_path, "model.bin")) or os.path.exists(os.path.join(dir_path, "model.safetensors"))
    return has_cfg and has_weights

def resolve_or_download_whisper_model(
    model_name: str,
    auto_download: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None
) -> str:
    """
    智能解析 Whisper 模型路径：
    1. 优先使用本地已存在的离线模型 (Lite/models/[model_name])
    2. 若本地不存在且 auto_download=True，通过国内镜像源 (hf-mirror.com) 自动高速下载
    3. 若下载失败，自动平滑降级使用本地现存的可用模型 (如 small / base) 防崩溃
    """
    clean_name = normalize_whisper_model_name(model_name)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Lite 根目录
    parent_dir = os.path.dirname(base_dir) # 工作区根目录
    
    target_local_dir = os.path.join(base_dir, "models", clean_name)
    
    # 1. 检查指定模型是否已存在于本地
    candidates = [
        target_local_dir,
        os.path.join(parent_dir, "models", clean_name),
        os.path.join(os.getcwd(), "models", clean_name)
    ]
    for p in candidates:
        if is_valid_model_dir(p):
            return p

    def safe_log(msg: str):
        if not progress_cb:
            return
        try:
            progress_cb(msg)
        except Exception:
            try:
                sys.stdout.write(msg + "\n")
            except Exception:
                pass

    # 2. 本地不存在，尝试自动从国内极速源 (ModelScope / HF-Mirror) 高速下载
    if auto_download:
        safe_log(f"⬇️ 本地未检测到 Whisper [{clean_name}] 模型，正在通过国内极速源 (ModelScope / HF) 自动高速下载至 models/{clean_name}，请稍候...")
        
        os.makedirs(target_local_dir, exist_ok=True)
        download_success = False

        # 策略 A: 阿里 ModelScope 国内 CDN 直连极速下载
        try:
            repo_id = f"Systran/faster-whisper-{clean_name}"
            files = ["config.json", "tokenizer.json", "vocabulary.txt", "model.bin"]
            import urllib.request
            
            for fname in files:
                fpath = os.path.join(target_local_dir, fname)
                if os.path.exists(fpath) and os.path.getsize(fpath) > 100:
                    if fname == "model.bin" and os.path.getsize(fpath) > 10 * 1024 * 1024:
                        continue
                    elif fname != "model.bin":
                        continue
                
                file_url = f"https://modelscope.cn/api/v1/models/{repo_id}/repo?Revision=master&FilePath={fname}"
                safe_log(f"📦 正在下载 {clean_name} 模型核心组件: {fname}...")
                
                req = urllib.request.Request(file_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=45) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    block_size = 1024 * 1024 # 1MB
                    temp_fpath = fpath + ".tmp"
                    last_pct = -1
                    with open(temp_fpath, "wb") as f_out:
                        while True:
                            chunk = response.read(block_size)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and fname == "model.bin":
                                pct = int(downloaded * 100 / total_size)
                                if pct != last_pct and pct % 10 == 0:
                                    last_pct = pct
                                    mb_down = downloaded / (1024 * 1024)
                                    mb_tot = total_size / (1024 * 1024)
                                    safe_log(f"🚀 下载进度: {pct}% ({mb_down:.1f}MB / {mb_tot:.1f}MB)...")
                    
                    if os.path.exists(fpath):
                        os.remove(fpath)
                    os.rename(temp_fpath, fpath)

            if is_valid_model_dir(target_local_dir):
                safe_log(f"✅ Whisper [{clean_name}] 离线模型已成功下载并就绪！")
                return target_local_dir
        except Exception as ms_err:
            safe_log(f"⚠️ ModelScope 源下载受阻 ({ms_err})，正在尝试备用镜像源...")

        # 策略 B: HF-Mirror 备用下载
        try:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            from faster_whisper.utils import download_model
            download_model(clean_name, output_dir=target_local_dir)
            if is_valid_model_dir(target_local_dir):
                safe_log(f"✅ Whisper [{clean_name}] 离线模型已成功下载并就绪！")
                return target_local_dir
        except Exception as dl_err:
            safe_log(f"⚠️ 备用镜像源下载失败: {dl_err}，正在自动平滑回退到本地已有的其他模型...")

    # 3. 兜底策略：查找本地已有的任何可用离线模型 (如 small / base)
    for search_root in [os.path.join(base_dir, "models"), os.path.join(parent_dir, "models")]:
        if os.path.isdir(search_root):
            for sub in sorted(os.listdir(search_root)):
                sub_path = os.path.join(search_root, sub)
                if is_valid_model_dir(sub_path):
                    safe_log(f"⚡ [自动兜底] 已自动加载本地可用离线模型: {sub} ({sub_path})")
                    return sub_path

    # 4. 若本地完全无模型，则交由 Faster-Whisper 默认处理
    return clean_name

def resolve_whisper_model_path(model_name: str) -> str:
    """兼容旧接口"""
    return resolve_or_download_whisper_model(model_name, auto_download=True)

def transcribe_audio_to_srt(
    audio_path: str,
    output_srt_path: str,
    model_name: str = "base",
    device: str = "auto",
    language: str = "zh",
    progress_cb: Optional[Callable[[str], None]] = None
) -> Tuple[str, List[Dict]]:
    """使用 Faster-Whisper 进行高效语音转写"""
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    actual_model_path = resolve_or_download_whisper_model(model_name, auto_download=True, progress_cb=progress_cb)
    
    from faster_whisper import WhisperModel

    # 自动设备推断 (优先检测 ctranslate2/cuda，无需硬依赖 torch)
    has_cuda = False
    try:
        import ctranslate2
        has_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except Exception:
            has_cuda = False

    if device == "cuda":
        actual_device = "cuda"
        compute_type = "float16"
    elif device == "cpu":
        actual_device = "cpu"
        compute_type = "int8"
    else: # auto
        actual_device = "cuda" if has_cuda else "cpu"
        compute_type = "float16" if has_cuda else "int8"

    try:
        model = WhisperModel(actual_model_path, device=actual_device, compute_type=compute_type)
    except Exception as e:
        # 若 GPU/float16 初始化失败（例如系统缺少 cuDNN），自动平滑降级为 CPU 模式
        if actual_device == "cuda":
            if progress_cb:
                progress_cb(f"⚠️ CUDA 初始化异常 ({e})，正在自动切换至 CPU 模式运行...")
            actual_device = "cpu"
            compute_type = "int8"
            model = WhisperModel(actual_model_path, device="cpu", compute_type="int8")
        else:
            raise
    
    if progress_cb:
        progress_cb("正在加载音频并开始语音识别与时间戳定位...")

    # 引导模型输出纯正简体中文并开启词级时间戳定位
    transcribe_kwargs = {
        "language": language if language else "zh",
        "vad_filter": True,
        "vad_parameters": dict(min_silence_duration_ms=400),
        "initial_prompt": "以下是体育足球赛事大数据风控分析解说视频，涉及术语：大号球场放大镜、欧冠、葡超、意甲、德甲、韩职、拜仁慕尼黑、安联球场、罗马、曼联、费内巴切、莱红牛、科莫、布拉加、弗拉门戈、德尔瓦耶、初盘、即时盘面、均水、浅阻、均阻、低阻设防、超低阻、深盘、高阻、SP值、同盘赢率、核心阻力位、极限支撑阈值、终局定性、硬核实力局、暗流涌动局、五五开混沌局、极危黑名单、防线堪忧、刺刀见红、护城河、保持绝对理智、支持体育公益。请使用纯正规范的简体汉字输出，严禁错别字。",
        "word_timestamps": True
    }

    segments, info = model.transcribe(audio_path, **transcribe_kwargs)

    total_audio_dur = info.duration if (info and hasattr(info, 'duration') and info.duration > 0) else 1.0
    if progress_cb:
        progress_cb(f"开始转写音频内容 (总音频时长: {format_timestamp(total_audio_dur)})...")

    # 引入 zhconv 做 100% 繁转简防御保障
    try:
        import zhconv
        has_zhconv = True
    except ImportError:
        has_zhconv = False

    # 智能分句与黄金比例微碎片平滑合并算法 (8~18字单行)
    # 智能自然意群分句算法：按标点与词组完整聚合，绝不硬切断词汇、专有名词与小数点
    subtitles = []
    idx = 1

    for seg in segments:
        raw_text = seg.text.strip()
        if not raw_text:
            continue
        if has_zhconv:
            try:
                raw_text = zhconv.convert(raw_text, 'zh-cn')
            except Exception:
                has_zhconv = False

        # 1. 自动缝合原始转写中可能出现的数字空格或中文"点" (如 "1 49" -> "1.49", "1点49" -> "1.49")
        raw_text = re.sub(r'(\d+)[ \t]+(\d+)', r'\1.\2', raw_text)
        raw_text = re.sub(r'(\d+)点(\d+)', r'\1.\2', raw_text)

        # 2. 按标点/空格拆分成完整独立的语义短语
        # 严密保护数字内部的小数点 (如 1.49, 33.3%)，只有非数字前后的句号、逗号以及其它标点才作为切分符
        delim = r'[，。！？；、!\?]+|(?<!\d)[,\.]|[,\.](?!\d)|\s+'
        tokens = [t.strip() for t in re.split(delim, raw_text) if t.strip()]
        if not tokens:
            continue

        # 贪心收集完整词块，单行严格控制在 8 ~ 20 个汉字黄金长度
        lines = []
        cur_line = []
        cur_len = 0
        for tok in tokens:
            if cur_len + len(tok) <= 20:
                cur_line.append(tok)
                cur_len += len(tok)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                cur_line = [tok]
                cur_len = len(tok)
        if cur_line:
            lines.append(" ".join(cur_line))

        # 按字数比例分配每个短行的起止时间戳
        total_chars = sum(len(l) for l in lines) or 1
        dur = max(0.4, seg.end - seg.start)
        c_s = seg.start
        for l in lines:
            p_dur = (len(l) / total_chars) * dur
            c_e = c_s + p_dur
            clean_txt = re.sub(r'^[，。！？、；,\.!\?\s]+|(?<!\d)[，。！？、；,\.!\?\s]+$', '', l).strip()
            clean_txt = re.sub(r'(\d+)[ \t]+(\d+)', r'\1.\2', clean_txt)
            clean_txt = re.sub(r'(\d+)点(\d+)', r'\1.\2', clean_txt)
            if clean_txt:
                subtitles.append({
                    "index": idx,
                    "start": round(c_s, 3),
                    "end": round(c_e, 3),
                    "start_str": format_timestamp(c_s),
                    "end_str": format_timestamp(c_e),
                    "text": clean_txt
                })
                if progress_cb:
                    cur_pct = min(99, int((c_e / total_audio_dur) * 100))
                    progress_cb(f"🎙️ [语音转写 {cur_pct}%] {format_timestamp(c_e)}: {clean_txt}")
                idx += 1
            c_s = c_e

    write_srt_file(subtitles, output_srt_path)
    if progress_cb:
        progress_cb(f"✅ [转写 100%] 语音识别完成，共生成 {len(subtitles)} 条精美单行字幕")
        
    return output_srt_path, subtitles

def polish_subtitles_with_llm(
    input_srt_path: str,
    output_srt_path: str,
    api_key: str,
    base_url: str,
    model_name: str = "gemini-2.5-flash",
    progress_cb: Optional[Callable[[str], None]] = None
) -> str:
    """调用大模型（OpenAI / Gemini API 兼容）智能润色与校对错别字，支持多Key轮询与多模型容错"""
    if not api_key:
        return input_srt_path

    # 解析多个 API Key
    api_keys = [k.strip() for k in api_key.replace("，", ",").split(",") if k.strip()]
    if not api_keys:
        return input_srt_path

    # 确定候选模型列表 (Google AI Studio 全部 7 大活跃模型)
    fallback_models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3-flash",
        "gemini-robotics-er-1.6-preview"
    ]
    if "轮询" in model_name or "Round-Robin" in model_name:
        candidate_models = fallback_models
    else:
        candidate_models = [model_name] + [m for m in fallback_models if m != model_name]

    if progress_cb:
        progress_cb(f"正在调用大模型 ({candidate_models[0]}) 智能校对字幕错别字 (可用 Key 数: {len(api_keys)})...")

    try:
        from openai import OpenAI
        with open(input_srt_path, "r", encoding="utf-8") as f:
            raw_srt = f.read()

        system_prompt = (
            "你是一个专业的字幕校对专家。你的任务是修正语音识别生成的错别字，保持句子通顺。\n"
            "【最高优先级警告：格式严格性】\n"
            "1. 绝不允许合并或拆分相邻的字幕块！\n"
            "2. 绝对不能修改时间轴（如 00:00:00,000 --> 00:00:02,000）！\n"
            "3. 绝对不能删除或修改数字序号！\n"
            "4. 每个字幕块之间必须保留一个空行！\n"
            "请直接输出校对后的完整SRT文本，不要包含任何额外的解释或Markdown标记代码块。"
        )

        last_err = None
        for cur_key in api_keys:
            for cur_model in candidate_models:
                try:
                    client = OpenAI(api_key=cur_key, base_url=base_url.strip() if base_url else None)
                    response = client.chat.completions.create(
                        model=cur_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": raw_srt}
                        ],
                        temperature=0.2,
                        timeout=30
                    )
                    polished_content = response.choices[0].message.content.strip()
                    if polished_content.startswith("```"):
                        polished_content = re.sub(r"^```[a-zA-Z]*\n", "", polished_content)
                        polished_content = re.sub(r"\n```$", "", polished_content)

                    with open(output_srt_path, "w", encoding="utf-8") as f:
                        f.write(polished_content)

                    if progress_cb:
                        progress_cb(f"大模型校对成功！(模型: {cur_model})")
                    return output_srt_path

                except Exception as ex:
                    last_err = ex
                    continue

        if progress_cb:
            progress_cb(f"所有 API Key/模型尝试完毕，校对失败 ({last_err})，使用原始转写字幕")
        return input_srt_path

    except Exception as e:
        if progress_cb:
            progress_cb(f"大模型校对遇到异常: {e}，将使用原始识别字幕")
        return input_srt_path
