import os
from typing import List, Optional, Callable
from PIL import Image

def extract_images_from_pdf(
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
    target_width: int = 1920,
    target_height: int = 1080,
    progress_cb: Optional[Callable[[str], None]] = None
) -> List[str]:
    """
    使用 PyMuPDF 极速将 PDF 每页渲染为高清图片，
    并自动适配/居中到标准 16:9 (默认 1920x1080) 画布上，便于直接作为视频画面。
    """
    if not os.path.exists(pdf_path):
        return []

    os.makedirs(output_dir, exist_ok=True)
    image_paths: List[str] = []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("缺少 PyMuPDF 库，请安装: pip install PyMuPDF")

    if progress_cb:
        progress_cb(f"正在解析并提取 PDF ({os.path.basename(pdf_path)}) 页面...")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    for i in range(total_pages):
        page = doc[i]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        raw_image_path = os.path.join(output_dir, f"raw_page_{i+1:03d}.png")
        pix.save(raw_image_path)

        # 尺寸归一化到 1920x1080 居中背景
        final_image_path = os.path.join(output_dir, f"slide_{i+1:03d}.png")
        _fit_image_to_canvas(raw_image_path, final_image_path, target_width, target_height)
        
        try:
            os.remove(raw_image_path)
        except OSError:
            pass

        image_paths.append(final_image_path)
        if progress_cb:
            page_pct = int(((i + 1) / total_pages) * 100)
            progress_cb(f"📄 [PDF提取 {page_pct}%] 已提取第 {i+1}/{total_pages} 页幻灯片高清图")

    doc.close()
    if progress_cb:
        progress_cb(f"✅ [PDF提取 100%] 提取完成，共获得 {len(image_paths)} 张幻灯片图片")

    return image_paths

def _fit_image_to_canvas(src_path: str, dst_path: str, target_w: int, target_h: int):
    """等比例缩放图片并居中贴在黑底/透明 16:9 画布上"""
    with Image.open(src_path) as img:
        src_w, src_h = img.size
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # 创建目标纯黑底画布
        canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        canvas.save(dst_path, "PNG", quality=95)
