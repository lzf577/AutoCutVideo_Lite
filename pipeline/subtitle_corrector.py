#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
《大号球场放大镜》字幕长期持久化自动校对与纠错中枢 (Subtitle Corrector Engine)
- 核心使命：
  1. 【真值剧本强制咬合 (Ground-Truth Script Alignment)】：
     自动寻找对应的《第X集_视频剧本.md》，以作者撰写的官方剧本作为绝对真值，
     保留 Whisper 的高精度起止时间戳，将识别出来的同音错字 100% 自动校准还原为剧本正文！
  2. 【领域专用错别字与术语过滤中枢 (Domain Vocab Dictionary)】：
     内置涵盖风控评级、盘面指标、涉彩净化、球队译名及浮点数末位0的完整字典，
     对所有 SRT 字幕进行全自动清洗。
  3. 【全自动零侵入】：
     在压制流程（批量压制/单集压制）中常态化自动触发，无需人工手动修复。
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ==============================================================================
# 1. 赛事风控专有名词与常见 ASR 同音错别字映射表 (永久持久化维护)
# ==============================================================================
GLOBAL_VOCAB_CORRECTIONS = [
    # (1) 核心风控指标与阻力/支撑术语
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
    
    # (2) 球队与球场专有名词
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
    
    # (3) 币种、数值与末位无效零规范
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

def clean_text_by_dict(text: str) -> str:
    """使用全局字典执行精确清洗"""
    for pattern, repl in GLOBAL_VOCAB_CORRECTIONS:
        if callable(repl):
            text = re.sub(pattern, repl, text)
        else:
            text = re.sub(pattern, repl, text)
    return text

# ==============================================================================
# 2. 真实剧本智能定位与正文提取引擎
# ==============================================================================
def find_associated_script(folder_path: str) -> Optional[Path]:
    """根据分集目录（如 04_待压制素材/第1集）智能搜寻 03_Notebook素材 中对应的视频剧本.md"""
    cur_p = Path(folder_path).resolve()
    ep_name = cur_p.name # 如 "第1集"
    m_ep = re.search(r"第(\d+)集", ep_name)
    if not m_ep:
        return None
    ep_num = m_ep.group(1) # "1"

    # 1. 检查当前目录内是否有 script.md 或 *视频剧本.md
    for f in cur_p.glob("*"):
        if "视频剧本" in f.name and f.suffix == ".md":
            return f
        if f.name.lower() in ["script.md", "剧本.md"]:
            return f

    # 2. 检查兄弟/父级目录下的 03_Notebook素材
    # 路径形式可能为: 每日生产/YYYY-MM-DD/04_待压制素材/第1集
    # 目标为: 每日生产/YYYY-MM-DD/03_Notebook素材/第1集_*_视频剧本.md
    daily_root = cur_p.parent.parent
    nb_dir = daily_root / "03_Notebook素材"
    if nb_dir.exists():
        for f in nb_dir.glob("*.md"):
            if f"第{ep_num}集" in f.name and "视频剧本" in f.name:
                return f

    return None

def extract_script_phrases(script_path: Path) -> List[str]:
    """从剧本 Markdown 中提取有序的纯台词文本短句列表"""
    content = script_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    phrases = []
    in_dialogue = False
    
    for l in lines:
        line_str = l.strip()
        if not line_str:
            continue
        # 跳过 YAML 参数与非台词说明
        if line_str.startswith("### 接口调用参数") or line_str.startswith("- artifact_type"):
            in_dialogue = False
            continue
        if line_str.startswith("### 【Slide") or line_str.startswith("### 【第"):
            in_dialogue = True
            continue
        if line_str.startswith("---"):
            continue
        if line_str.startswith("- 【") or line_str.startswith("【视觉风格") or line_str.startswith("【空间排版"):
            continue
            
        if in_dialogue:
            # 过滤标题残余（如 001 18:30 韩职 ...）
            clean_l = re.sub(r"^\d{3}\s+\d{2}:\d{2}.*", "", line_str).strip()
            if not clean_l:
                continue
            # 按逗号、句号、感叹号拆解为短句
            sub_phrases = re.split(r"[，。！？；!？;\n]+", clean_l)
            for sp in sub_phrases:
                sp_clean = sp.strip()
                # 过滤注释与过短碎片
                if len(sp_clean) >= 2 and not sp_clean.startswith("[") and not sp_clean.startswith("【"):
                    phrases.append(sp_clean)
                    
    return phrases

# ==============================================================================
# 3. 基于真实剧本的高精度模糊对齐引擎
# ==============================================================================
def align_srt_with_script(srt_lines: List[Dict], script_phrases: List[str]) -> Tuple[List[Dict], int]:
    """
    保留 Whisper 毫秒级时间戳，使用真实剧本短句对齐替换识别文本。
    返回: (校对后的字幕列表, 替换句数)
    """
    if not script_phrases:
        # 无剧本时退化为纯字典清洗
        modified = 0
        for s in srt_lines:
            old_t = s["text"]
            new_t = clean_text_by_dict(old_t)
            if new_t != old_t:
                s["text"] = new_t
                modified += 1
        return srt_lines, modified

    aligned_subs = []
    script_idx = 0
    num_phrases = len(script_phrases)
    matched_count = 0

    for s in srt_lines:
        cur_text = s["text"].strip()
        # 先做基础字典清洗
        cur_text = clean_text_by_dict(cur_text)
        
        # 在真实剧本周围的滑动窗口内寻找最佳匹配 (前2句 ~ 后6句)
        best_match_phrase = None
        best_ratio = 0.0
        best_idx = script_idx
        
        search_start = max(0, script_idx - 2)
        search_end = min(num_phrases, script_idx + 8)
        
        # 尝试单句匹配与相邻两句拼合匹配
        for i in range(search_start, search_end):
            p1 = script_phrases[i]
            r1 = SequenceMatcher(None, cur_text, p1).ratio()
            if r1 > best_ratio:
                best_ratio = r1
                best_match_phrase = p1
                best_idx = i
                
            # 相邻双句拼合
            if i + 1 < num_phrases:
                p2 = f"{p1} {script_phrases[i+1]}"
                r2 = SequenceMatcher(None, cur_text, p2).ratio()
                if r2 > best_ratio:
                    best_ratio = r2
                    best_match_phrase = p2
                    best_idx = i + 1

        # 若相似度达到较高阈值 (>= 0.60)，采用真实剧本正文
        if best_ratio >= 0.60 and best_match_phrase:
            s["text"] = best_match_phrase
            script_idx = best_idx + 1
            matched_count += 1
        else:
            s["text"] = cur_text

        aligned_subs.append(s)

    return aligned_subs, matched_count

# ==============================================================================
# 4. 主控入口：全自动持久化校验与落盘
# ==============================================================================
def auto_correct_srt(srt_file_path: str, progress_cb: Optional[callable] = None) -> bool:
    """
    全自动持久化执行：
    1. 自动定位对应的真实剧本；
    2. 执行剧本真值咬合 + 全局字典纠错；
    3. 覆盖写回 SRT 文件。
    """
    srt_p = Path(srt_file_path)
    if not srt_p.exists() or srt_p.stat().st_size < 10:
        return False

    def log(msg: str):
        if progress_cb: progress_cb(msg)
        else: sys.stdout.write(msg + "\n")

    # 1. 读取原 SRT
    content = srt_p.read_text(encoding="utf-8")
    blocks = re.split(r'\n\s*\n', content.strip())
    subtitles = []
    
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})')
    for b in blocks:
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        if len(lines) >= 3:
            idx = lines[0]
            m = pattern.search(lines[1])
            if m:
                txt = " ".join(lines[2:]).strip()
                subtitles.append({
                    "idx": idx,
                    "ts": lines[1],
                    "text": txt
                })

    if not subtitles:
        return False

    # 2. 搜寻剧本
    task_folder = srt_p.parent.parent if srt_p.parent.name == "tmp_autocut" else srt_p.parent
    script_p = find_associated_script(str(task_folder))
    
    script_phrases = []
    if script_p and script_p.exists():
        log(f"📖 [持久化校对] 成功锁定权威基准剧本: {script_p.name}")
        script_phrases = extract_script_phrases(script_p)
    else:
        log(f"💡 [持久化校对] 未发现直接关联剧本，启动全量专业风控字典清洗模式")

    # 3. 执行校对
    aligned_subs, corrected_count = align_srt_with_script(subtitles, script_phrases)

    # 4. 写回原文件
    out_lines = []
    for s in aligned_subs:
        out_lines.append(f"{s['idx']}\n{s['ts']}\n{s['text']}\n")
        
    final_srt_str = "\n".join(out_lines) + "\n"
    srt_p.write_text(final_srt_str, encoding="utf-8")
    
    log(f"✨ [持久化校对] 字幕优化完毕！已精准保障 {len(subtitles)} 条字幕，成功修正/对齐 {corrected_count} 处专业术语！")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        auto_correct_srt(sys.argv[1])
    else:
        print("用法: python subtitle_corrector.py <path_to_srt>")
