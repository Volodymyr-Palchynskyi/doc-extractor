from io import BytesIO

import pypdfium2 as pdfium

DEFAULT_SCALE = 1.6  # 1.0 is 72 dpi; 1.6 is sharp enough to read small print on a laptop screen


def render_page_png(pdf: bytes, index: int, scale: float = DEFAULT_SCALE) -> bytes:
    """Render one page (0-based) to PNG. Raises IndexError for a page that does not exist."""
    document = pdfium.PdfDocument(pdf)
    try:
        if not 0 <= index < len(document):
            raise IndexError(f"page {index} is out of range for a {len(document)}-page document")
        image = document[index].render(scale=scale).to_pil()
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    finally:
        document.close()
