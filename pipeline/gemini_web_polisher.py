"""
Gemini 网页版静默字幕校对引擎 (基于 Playwright 无头浏览器)
特点：
1. 0 API Key 消耗，终身免费，无需翻墙配置复杂的 API Key；
2. 纯文本 SRT 交互，6~10 秒完成全片错别字智能纠错；
3. 自动查找本地已安装的 Chrome / Edge 浏览器，会话持久保存在 tmp_gemini_profile 目录中。
"""

import os
import re
import time
from typing import Optional, Callable
from playwright.sync_api import sync_playwright

def find_browser_executable() -> tuple[str, str]:
    """智能查找系统中可用的 Chrome 或 Edge 浏览器路径"""
    candidates = [
        ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        ("chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ("chrome", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
        ("msedge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ("msedge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        ("msedge", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")),
    ]
    for channel, path in candidates:
        if os.path.exists(path):
            return channel, path
    return "msedge", ""

def polish_subtitles_with_gemini_web(
    input_srt_path: str,
    output_srt_path: str,
    headless: bool = True,
    profile_dir: Optional[str] = None,
    progress_cb: Optional[Callable[[str], None]] = None
) -> str:
    """
    通过 Gemini 网页版静默进行字幕错别字校对：
    - 读取 input_srt_path 的 SRT 文本
    - 在后台静默提交给 gemini.google.com
    - 提取校对后的 SRT 结果并写入 output_srt_path
    """
    if not os.path.exists(input_srt_path):
        return input_srt_path

    with open(input_srt_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_srt = f.read().strip()

    if not raw_srt:
        return input_srt_path

    if profile_dir is None:
        base_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profile_dir = os.path.join(base_root, "tmp_gemini_profile")
    os.makedirs(profile_dir, exist_ok=True)

    if progress_cb:
        progress_cb("🌐 正在连接 Gemini 网页版进行大模型字幕校对 (无头静默模式)...")

    channel_name, exe_path = find_browser_executable()
    
    prompt = (
        "你是一个专业的视频字幕错别字校对专家。请校对下面这段 SRT 字幕中的错别字，保持语言通顺流畅。\n"
        "【严格格式要求】\n"
        "1. 严禁合并或拆分字幕块！\n"
        "2. 绝对不能修改时间轴（如 00:00:00,000 --> 00:00:02,000）！\n"
        "3. 绝对不能删除或修改数字序号！\n"
        "4. 必须输出规范的普通话【简体中文】（zh-CN），严禁输出繁体字！\n"
        "5. 直接输出校对后的标准 SRT 文本内容，不要包含多余的闲聊废话。\n\n"
        f"{raw_srt}"
    )

    t_start = time.time()
    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "user_data_dir": profile_dir,
                "headless": headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--start-maximized"
                ],
                "viewport": None
            }
            if exe_path:
                launch_kwargs["executable_path"] = exe_path
            else:
                launch_kwargs["channel"] = channel_name

            context = p.chromium.launch_persistent_context(**launch_kwargs)
            page = context.pages[0] if context.pages else context.new_page()

            # 访问 Gemini 网页
            page.goto("https://gemini.google.com/app", timeout=60000)

            input_selector = 'div[role="textbox"], div.ql-editor[contenteditable="true"], rich-textarea div, textarea'
            page.wait_for_selector(input_selector, timeout=20000)

            # 聚焦并输入提示词
            input_box = page.locator(input_selector).first
            input_box.click()
            try:
                input_box.fill(prompt)
            except Exception:
                input_box.type(prompt, delay=2)
            time.sleep(0.5)

            # 提交任务
            send_btn_selector = 'button[aria-label*="发送"], button[aria-label*="Send"], button.send-button'
            try:
                send_btn = page.locator(send_btn_selector).first
                if send_btn.is_visible() and send_btn.is_enabled():
                    send_btn.click()
                else:
                    page.keyboard.press("Enter")
            except Exception:
                page.keyboard.press("Enter")

            if progress_cb:
                progress_cb("⚡ 提示词已发送，正在等待 Gemini 网页版输出校对结果...")

            # 等待生成完成（监听输出文本稳定）
            time.sleep(3)
            response_selector = 'div.model-response-text, div[data-test-id="model-response-text"], message-content'
            try:
                page.wait_for_selector(response_selector, timeout=60000)
            except Exception:
                pass

            last_text = ""
            stable_count = 0
            for _ in range(60):
                responses = page.locator(response_selector).all()
                if responses:
                    cur_text = responses[-1].inner_text()
                    if cur_text and cur_text == last_text:
                        stable_count += 1
                        if stable_count >= 4:
                            break
                    else:
                        stable_count = 0
                        last_text = cur_text
                time.sleep(0.5)

            context.close()

            # 清理 Markdown 代码块标记（如 ```srt 或 ```）
            cleaned_text = last_text.strip()
            if "-->" in cleaned_text:
                # 提取其中的 SRT 核心片段
                match = re.search(r"(\d+\s*\n\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->.*)", cleaned_text, re.DOTALL)
                if match:
                    cleaned_text = match.group(1).strip()
                    cleaned_text = re.sub(r"```.*$", "", cleaned_text).strip()

                try:
                    import zhconv
                    cleaned_text = zhconv.convert(cleaned_text, 'zh-cn')
                except Exception:
                    pass

                with open(output_srt_path, "w", encoding="utf-8") as f:
                    f.write(cleaned_text)

                t_cost = round(time.time() - t_start, 2)
                if progress_cb:
                    progress_cb(f"🎉 [Gemini 网页版] 字幕智能校对完成！(耗时: {t_cost} 秒)")
                return output_srt_path
            else:
                if progress_cb:
                    progress_cb("⚠️ 网页版返回内容未包含标准时间戳，自动回退使用原始识别字幕")
                return input_srt_path

    except Exception as e:
        if progress_cb:
            progress_cb(f"⚠️ Gemini 网页版校对异常 ({e})，使用原始转写字幕")
        return input_srt_path
