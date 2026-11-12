import logging
from dataclasses import dataclass
from io import BytesIO

logger = logging.getLogger(__name__)

_engine = None
_MIN_SIDE = 48
_MIN_SCORE = 0.5


def _ocr_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None
    regions: tuple


def ocr_image(data: bytes) -> str:
    """识别图片中的文字。过小的图标和无法打开的图片返回空字符串。"""
    return ocr_image_detail(data).text


def ocr_image_detail(data: bytes) -> OcrResult:
    if not data:
        return OcrResult("", None, ())
    try:
        from PIL import Image
        import numpy as np

        image = Image.open(BytesIO(data)).convert("RGB")
    except Exception:
        logger.info("跳过无法打开的图片")
        return OcrResult("", None, ())
    width, height = image.size
    if min(width, height) < _MIN_SIDE:
        return OcrResult("", None, ())
    try:
        result, _elapsed = _ocr_engine()(np.asarray(image))
    except Exception:
        logger.exception("图片文字识别失败")
        return OcrResult("", None, ())
    if not result:
        return OcrResult("", None, ())
    lines: list[str] = []
    regions: list[dict] = []
    scores: list[float] = []
    for item in result:
        if len(item) < 2:
            continue
        text = str(item[1]).replace("\x00", "").strip()
        score = float(item[2]) if len(item) > 2 else 1.0
        if not text or score < _MIN_SCORE:
            continue
        lines.append(text)
        scores.append(score)
        regions.append({"text": text, "score": round(score, 4), **_box(item[0])})
    confidence = round(sum(scores) / len(scores), 4) if scores else None
    return OcrResult("\n".join(lines), confidence, tuple(regions))


def _box(points) -> dict:
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    except (TypeError, IndexError, ValueError):
        return {}
    if not xs or not ys:
        return {}
    return {"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)}


def ocr_pdf_page(path, page_index: int) -> str:
    """把几乎没有文字层的 PDF 页渲染出来再识别。page_index 从 0 开始。"""
    return ocr_pdf_page_detail(path, page_index).text


def ocr_pdf_page_detail(path, page_index: int) -> OcrResult:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        page = pdf[page_index]
        bitmap = page.render(scale=2)
        image = bitmap.to_pil().convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return ocr_image_detail(buffer.getvalue())
    finally:
        pdf.close()
